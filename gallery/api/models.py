from django.db import models
from django_jsonfield_backport.models import JSONField
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from jid_validation.jid import JID

from .utils.generators import get_upload_entity, get_upload_thumb, get_token_lifetime, get_code_lifetime, generate_uuid, generate_title
from .utils.validators import MimeTypeValidator

import os


class EntityFile(models.Model):

    file = models.FileField(
        upload_to=get_upload_entity,
        max_length=500
    )
    hash = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.get_filename()

    def get_filename(self):
        return os.path.basename(self.file.file.name)


class MediaFile(models.Model):
    CONTEXT_CHOICES = [
        ('file', 'file'),
        ('avatar', 'avatar'),
        ('voice', 'voice'),
        ('gif', 'gif'),
        ('call', 'call')
    ]
    entity_file = models.ForeignKey(EntityFile, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    avatar_thumbs = models.BooleanField(default=False)
    size = models.IntegerField(blank=True)
    media_type = models.CharField(
        max_length=255,
        validators=[MimeTypeValidator()],
        blank=True,
        null=True
    )
    name = models.CharField(max_length=255, blank=True)
    title = models.CharField(
        max_length=255,
        unique=True,
        default=generate_title
    )
    metadata = JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    context = models.CharField(
        default='file',
        choices=CONTEXT_CHOICES,
        max_length=10
    )

    def __str__(self):
        return self.title


class Thumbnail(models.Model):

    entity_file = models.ForeignKey(EntityFile, on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_upload_thumb)
    is_avatar = models.BooleanField(default=False)
    side_size = models.IntegerField(default=settings.DEFAULT_THUMB_SIZE_TUPLE[0])

    def __str__(self):
        return self.get_filename()

    def get_filename(self):
        try:
            return os.path.basename(self.file.file.name)
        except:
            return ''


class Quota(models.Model):

    """ A quota can be global if a host is specified, or specific to an individual user. """

    class Meta:
        ordering = ['user__username']

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='quota',
        blank=True,
        null=True
    )
    host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True
    )
    size = models.BigIntegerField(
        default=0,
        null=True,
        blank=True
    )
    used = models.BigIntegerField(
        default=0,
        null=True,
        blank=True,
        editable=False
    )

    @property
    def get_size(self):
        if self.size:
            return self.size
        else:
            global_quota = Quota.objects.exclude(models.Q(host=None) | models.Q(host='')).filter(host=self.get_user_host, user=None).first()
            if global_quota and global_quota.size:
                return global_quota.size
            else:
                return settings.DEFAULT_QUOTA_SIZE

    @property
    def get_user_host(self):
        if not self.user:
            return ''
        try:
            jid_obj = JID(self.user.username)
            return jid_obj.host
        except:
            return ''

    def get_quota_used(self):
        summ = 0
        mediafiles = MediaFile.objects.filter(user=self.user).aggregate(models.Sum('size'))
        if mediafiles.get('size__sum'):
            summ = mediafiles.get('size__sum')
        return summ

    def update_quota_used(self):
        self.used = self.get_quota_used()
        self.save()

    def update_quota_value(self, value):
        self.size = value
        self.save()

    def quota_available(self, size):
        return int(size) < (self.get_size - self.used)

    def __str__(self):
        if self.user:
            return self.user.username
        elif self.host:
            return self.host
        else:
            return 'Empty quota object'


class Token(models.Model):

    key = models.CharField(max_length=255, default=generate_uuid)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device = models.CharField(max_length=255, null=True, blank=True)
    client = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    expires = models.DateTimeField(default=get_token_lifetime)
    scope = models.TextField(blank=True, null=True, help_text="FULL SCOPE: global, PER HOST: example.com, LIST OF HOSTS: example.com, example2.com, LIST OF USERS: user@example.com, user2@example.com")

    def __str__(self):
        return self.user.username


class VerificationCode(models.Model):
    value = models.IntegerField(blank=True, unique=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_code')
    expires = models.DateTimeField(default=get_code_lifetime)

    def __str__(self):
        return str(self.expires)

    def check_expires(self):
        if timezone.now() > self.expires:
            self.delete()
            return False
        return True


class WhiteList(models.Model):
    host = models.CharField(
        max_length=255
    )
    users = models.ManyToManyField(
        'ListUser',
        related_name='white_list',
        blank=True
    )
    all_users = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ['host']

    def __str__(self):
        return self.host

    def get_users(self):
        return self.users.values_list('jid', flat=True)


class BlackList(models.Model):

    host = models.CharField(
        max_length=255
    )
    users = models.ManyToManyField(
        'ListUser',
        related_name='black_list',
        blank=True
    )
    all_users = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ['host']

    def __str__(self):
        return self.host

    def get_users(self):
        return self.users.values_list('jid', flat=True)


class ListUser(models.Model):

    jid = models.CharField(
        max_length=256,
        unique=True
    )

    def __str__(self):
        return self.jid