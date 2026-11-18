from gallery.api.models import MediaFile, EntityFile, Quota, Thumbnail
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import User

from .utils.generators import hash_sha1
from .utils.simlinks import create_symlink
from .utils.other import delete_files

from threading import Thread

from pathlib import Path
from shutil import rmtree


@receiver(post_save, sender=MediaFile)
def media_file_post_save(*args, **kwargs):

    """ Create symlinks on media file creating """

    media_file = kwargs.get('instance')
    created = kwargs.get('created')

    if created:
        # update quota and create symlink
        try:
            media_file.user.quota.update_quota_used()
        except Exception as e:
            print(e)
        create_symlink(media_file.entity_file.file.path, media_file.name, media_file.title)


@receiver(pre_save, sender=MediaFile)
def media_file_pre_save(*args, **kwargs):

    """ Generate fields info if it's not provided """

    instance = kwargs.get('instance')

    # generate fields on creation
    if not instance.size:
        instance.size = instance.entity_file.file.file.size


@receiver(post_delete, sender=MediaFile)
def media_file_post_delete(*args, **kwargs):

    """ Delete related files """

    media_file = kwargs.get('instance')

    # update quota
    try:
        media_file.user.quota.update_quota_used()
    except Exception as e:
        print(e)

    symlink_path = str(Path(settings.MEDIA_ROOT, settings.SYMLINKS_DIR, media_file.title))
    try:
        rmtree(symlink_path)
    except Exception as e:
        print(e)

    Thread(target=delete_files).start()


@receiver(pre_save, sender=EntityFile)
def entity_file_pre_save(*args, **kwargs):

    """ Generate fields info if it's not provided """

    instance = kwargs.get('instance')

    # Generate hash if it's not provided.
    # WARNING: It's better to provide hash in view.
    # That method can take a lot of time to upload file from storage.
    if not instance.hash:
        file = open(instance.file.path, 'rb')
        instance.hash = hash_sha1(file)


@receiver(post_delete, sender=EntityFile)
def entity_file_post_delete(*args, **kwargs):

    """ Delete files and thumbnails from storage"""

    entity_file = kwargs.get('instance')
    if entity_file.file.storage.exists(entity_file.file.name):
        entity_file.file.storage.delete(entity_file.file.name)


@receiver(post_delete, sender=Thumbnail)
def thumbnail_post_delete(*args, **kwargs):

    """ Delete thumbnails from storage"""

    thumbnail = kwargs.get('instance')
    if thumbnail.file and thumbnail.file.storage.exists(thumbnail.file.name):
        thumbnail.file.storage.delete(thumbnail.file.name)


@receiver(post_save, sender=User)
def user_post_save(*args, **kwargs):

    """ Create quota on user creation """

    created = kwargs.get('created')
    user = kwargs.get('instance')

    if created:
        Quota.objects.create(user=user)
