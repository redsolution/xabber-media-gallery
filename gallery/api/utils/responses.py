from django.db.models import Sum, Q
from django.conf import settings
from django.db.models.functions import Coalesce
from pathlib import Path
from gallery.api.models import MediaFile, Quota
from .exceptions import MalformedData
from .generators import get_file_url
import os


def file_upload_response(
        media_file: MediaFile,
        avatar_thumbs: bool = False,
        max_size: int = settings.MAX_AVATAR_SIZE
) -> dict:

    response = {
        'id': media_file.id,
        'size': media_file.size,
        'media_type': media_file.media_type,
        'name': media_file.name,
        'slot_id': media_file.title,
        'created_at': media_file.created_at,
        'file': get_file_url(media_file.title, media_file.name),
        'hash': media_file.entity_file.hash,
        'used': media_file.user.quota.get_quota_used(),
        'quota': media_file.user.quota.get_size,
        'context': media_file.context
    }

    # optional attrs
    if media_file.metadata:
        metadata = media_file.metadata
        if metadata:
            response['metadata'] = metadata

    if media_file.media_type:
        media_type, format = media_file.media_type.split('/')

        if media_type in ['image', 'video']:

            if media_type == 'video':
                name = os.path.splitext(media_file.name)[0]
                name = 'thumb_{}.png'.format(name)
            else:
                name = 'thumb_{}'.format(media_file.name)

            response['thumbnail'] = {
                'url':  get_file_url(media_file.title, name),
                'width': settings.DEFAULT_THUMB_SIZE_TUPLE[0],
                'height': settings.DEFAULT_THUMB_SIZE_TUPLE[1],
            }

    if media_file.context == 'avatar' and avatar_thumbs:
        thumb_name = Path(media_file.name).stem
        response['thumbnails'] = [
            {
                'url': get_file_url(media_file.title, '%s_%s.webp' % (size, thumb_name)),
                'width': size,
                'height': size,
            } for size in settings.THUMBS_SIZE_LIST if size < max_size
        ]

    return response


def get_quota_response(quota: Quota) -> dict:
    response = {
        'quota': quota.get_size,
        'used': quota.used
    }
    return response


def stats_response(media_files, quota: int) -> dict:

    images = media_files.filter(media_type__startswith='image', context='file')
    avatars = media_files.filter(media_type__startswith='image', context='avatar')
    videos = media_files.filter(media_type__startswith='video')
    voices = media_files.filter(context='voice')
    audio = media_files.filter(media_type__startswith='audio')
    files = media_files.exclude(
        Q(media_type__contains='image')|
        Q(media_type__contains='video')|
        Q(context='voice')|
        Q(media_type__contains='audio')
    )

    response = {
        'images': {
            'count': images.count(),
            'used': images.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'avatars': {
            'count': avatars.count(),
            'used': avatars.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'videos': {
            'count': videos.count(),
            'used': videos.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'voices': {
            'count': voices.count(),
            'used': voices.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'audio': {
            'count': audio.count(),
            'used': audio.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'files': {
            'count': files.count(),
            'used': files.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'total': {
            'count': media_files.count(),
            'used': media_files.aggregate(size=Coalesce(Sum('size'), 0)).get('size')
        },
        'quota': quota
    }

    return response


# ----- ERROR RESPONSES ------
def serialize_data(serializer):
    if not serializer.is_valid(raise_exception=False):
        print(serializer.errors)
        raise MalformedData
    return serializer.data


