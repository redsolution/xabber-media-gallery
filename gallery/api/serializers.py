from rest_framework import serializers
from django.contrib.auth.models import User
from django.conf import settings
from pathlib import Path
from jid_validation.jid import JID

from .models import MediaFile, EntityFile, Token, WhiteList, BlackList, Quota
from .utils.validators import MimeTypeValidator
from .utils.generators import get_file_url

import os


# todo: make validators
def make_jid_obj(value, param_name):
    try:
        return JID(value)
    except Exception:
        raise serializers.ValidationError("{} is invalid: {}".format(param_name, value))


def validate_full_jid_func(value, param_name='jid'):
    jid_obj = make_jid_obj(value, param_name)
    return jid_obj.full()


def validate_jid_func(value, param_name='jid'):
    jid_obj = make_jid_obj(value, param_name)
    return jid_obj.userhost()


def validate_users_func(host, value):
    users = []
    for user in value:
        try:
            jid_obj = JID(user)
            if jid_obj.host != host:
                raise serializers.ValidationError("host mismatch for user: {}".format(user))
            users.append(jid_obj.userhost())
        except Exception as e:
            raise serializers.ValidationError("users is invalid: {}".format(value))
    return users


class SlotSerializer(serializers.HyperlinkedModelSerializer):

    hash = serializers.CharField(source='entity_file.hash')
    name = serializers.CharField(required=True)
    size = serializers.IntegerField(required=True)

    class Meta:
        model = MediaFile
        fields = ['size', 'hash', 'name']


class FilesSerializer(serializers.HyperlinkedModelSerializer):

    hash = serializers.ReadOnlyField(source='entity_file.hash')
    file = serializers.SerializerMethodField(method_name='get_file_url', read_only=True)
    thumbnail = serializers.SerializerMethodField(read_only=True)
    thumbnails = serializers.SerializerMethodField(read_only=True)
    slot_id = serializers.ReadOnlyField(source='title')
    jid = serializers.CharField(required=False)

    class Meta:
        model = MediaFile
        fields = ['id', 'size', 'media_type', 'name', 'slot_id', 'file', 'created_at',
                  'hash', 'thumbnail', 'metadata', 'context', 'thumbnails', 'jid']

    def validate_jid(self, value):
        return validate_jid_func(value)

    def get_file_url(self, media_file):
        return get_file_url(media_file.title, media_file.name)

    def get_thumbnail(self, media_file, *args, **kwargs):

        """ Customize thumbnail field """

        if media_file.media_type:

            media_type, format = media_file.media_type.split('/')

            if media_type == 'video':
                name = os.path.splitext(media_file.name)[0]
                name = 'thumb_{}.png'.format(name)
            else:
                name = 'thumb_{}'.format(media_file.name)
        else:
            name = media_file.name

        thumbnail_info = {
            'url': get_file_url(media_file.title, name),
            'width': settings.DEFAULT_THUMB_SIZE_TUPLE[0],
            'height': settings.DEFAULT_THUMB_SIZE_TUPLE[1],
        }
        return thumbnail_info

    def get_thumbnails(self, media_file, *args, **kwargs):

        """ Customize thumbnails field """

        thumbnails_info = []
        if media_file.avatar_thumbs:
            thumb_name = Path(media_file.name).stem
            thumbnails_info = [
                {
                    'url': get_file_url(media_file.title, '%s_%s.webp' % (thumbnail.side_size, thumb_name)),
                    'width': thumbnail.side_size,
                    'height': thumbnail.side_size,
                } for thumbnail in media_file.entity_file.thumbnail_set.filter(is_avatar=True)
            ]
        return thumbnails_info


class FilesUploadSerializer(serializers.HyperlinkedModelSerializer):

    hash = serializers.ReadOnlyField()
    media_type = serializers.CharField(help_text=u'Example: image/png',
                                       validators=[MimeTypeValidator()], required=False)
    size = serializers.IntegerField(required=False)
    create_thumbnails = serializers.BooleanField(default=True)
    metadata = serializers.JSONField(required=False)
    context = serializers.ChoiceField(required=False, choices=MediaFile.CONTEXT_CHOICES)

    class Meta:
        model = EntityFile
        fields = ['file', 'size', 'hash', 'media_type', 'create_thumbnails', 'metadata', 'context']


class XmppCodeSerializer(serializers.Serializer):

    jid = serializers.CharField(required=True)
    type = serializers.CharField(required=False, initial='message')

    def validate_jid(self, value):
        return validate_full_jid_func(value)


class XmppAuthSerializer(serializers.HyperlinkedModelSerializer):

    jid = serializers.CharField(source='user.username', required=True)
    code = serializers.IntegerField(required=True)

    class Meta:
        model = Token

        fields = ['jid', 'code', 'device', 'client']


class TokensSerializer(serializers.HyperlinkedModelSerializer):

    token_id = serializers.IntegerField(source='id', required=True)

    class Meta:
        model = Token
        fields = ['token_id', 'device', 'client', 'created_at', 'expires']


class AccountListSerializer(serializers.HyperlinkedModelSerializer):

    jid = serializers.ReadOnlyField(source='username')
    quota = serializers.ReadOnlyField(source='quota.get_size', read_only=True)
    used = serializers.ReadOnlyField(source='quota.used')
    quota_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ['jid', 'quota', 'used', 'quota_size']


class AccountSerializer(serializers.HyperlinkedModelSerializer):

    jid = serializers.CharField(source='username', required=True)
    code = serializers.CharField(source='verification_code__value', required=False)

    class Meta:
        model = User
        fields = ['jid', 'code']


class QuotaSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Quota
        fields = ['value', 'jid']

    jid = serializers.CharField(required=False)
    value = serializers.IntegerField(required=False)

    def validate_jid(self, value):
        return validate_jid_func(value)


class DefaultQuotaSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Quota
        fields = ['host', 'size']

    host = serializers.CharField(required=True)

    def validate_host(self, value):
        return validate_jid_func(value, 'host')


class WhiteListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = WhiteList
        fields = ['host', 'users', 'all_users']

    users = serializers.ListField(
        child=serializers.CharField(),
        source='get_users',
        required=False
    )

    def validate_host(self, value):
        return validate_jid_func(value, 'host')

    def validate_users(self, value):
        host = self.initial_data.get('host')
        all_users = self.initial_data.get('all_users')
        users = []
        if not all_users:
            users = validate_users_func(host, value)

        return users


class BlackListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = BlackList
        fields = ['host', 'users', 'all_users']

    users = serializers.ListField(
        child=serializers.CharField(),
        source='get_users',
        required=False
    )

    def validate_host(self, value):
        return validate_jid_func(value, 'host')

    def validate_users(self, value):
        host = self.initial_data.get('host')
        all_users = self.initial_data.get('all_users')
        users = []
        if not all_users:
            users = validate_users_func(host, value)

        return users
