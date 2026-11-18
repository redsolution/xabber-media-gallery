from io import BytesIO
from django.core.files.base import ContentFile
from typing import Tuple
from ..models import EntityFile, Thumbnail, MediaFile
from pathlib import Path
from django.conf import settings
from .simlinks import create_symlink
import subprocess
import os


def create_image_thumb(upload: str, name: str) -> Tuple[str, ContentFile]:
    """
    Create image thumbnail using ImageMagick's convert command
    Returns tuple of (filename, ContentFile)
    """
    thumb_io = BytesIO()
    
    # Use ImageMagick to create thumbnail
    convert_cmd = [
        'convert',
        upload,
        '-thumbnail', '{}x{}^'.format(settings.DEFAULT_THUMB_SIZE_TUPLE[0],settings.DEFAULT_THUMB_SIZE_TUPLE[1]),
        '-gravity', 'center',
        '-extent', '{}x{}'.format(settings.DEFAULT_THUMB_SIZE_TUPLE[0],settings.DEFAULT_THUMB_SIZE_TUPLE[1]),
        '-quality', '60',
        '-auto-orient',
        '-strip',  # Remove metadata
        '-interlace', 'Plane',  # Progressive JPEG if applicable
        '-colorspace', 'sRGB',
        '-define', 'jpeg:dct-method=float',  # Better quality
        '-',  # Output to stdout
    ]
    
    try:
        thumb_data = subprocess.check_output(convert_cmd)
        thumb_io.write(thumb_data)
        thumb_io.seek(0)
        return "thumb_{}".format(name), ContentFile(thumb_io.getvalue(), name)
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to create image thumbnail: {}".format(e))
    except Exception as e:
        raise Exception("Error processing image thumbnail: {}".format(e))


def create_video_thumb(upload: str, name: str) -> Tuple[str, ContentFile]:
    """
    Create video thumbnail using ffmpeg and ImageMagick
    Returns tuple of (filename, ContentFile)
    """
    thumb_io = BytesIO()
    
    # First extract a frame with ffmpeg
    try:
        # Use ffmpeg to extract a frame (trying at 1 second, then 5 seconds)
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite without asking
            '-ss', '1',  # Seek to 1 second
            '-i', upload,
            '-vf', 'thumbnail,scale=w=iw:h=ih:force_original_aspect_ratio=decrease',
            '-frames:v', '1',
            '-f', 'image2pipe',
            '-vcodec', 'png',
            '-'
        ]
        
        frame_data = subprocess.check_output(ffmpeg_cmd, stderr=subprocess.PIPE, timeout=10)
        
        # If frame is mostly black (mean < 10), try again at 5 seconds
        if len(frame_data) > 0:
            identify_cmd = [
                'identify',
                '-format', '%[mean]',
                'png:-'
            ]
            mean = float(subprocess.check_output(identify_cmd, input=frame_data).decode('utf-8').strip())

            if mean < 10:
                ffmpeg_cmd[3] = '5'  # Change seek to 5 seconds
                frame_data = subprocess.check_output(ffmpeg_cmd, stderr=subprocess.PIPE, timeout=10)
        
        # Process the frame with ImageMagick
        if len(frame_data) > 0:
            convert_cmd = [
                'convert',
                'png:-',
                '-thumbnail', '{}x{}^'.format(settings.DEFAULT_THUMB_SIZE_TUPLE[0],
                                              settings.DEFAULT_THUMB_SIZE_TUPLE[1]),
                '-gravity', 'center',
                '-extent', '{}x{}'.format(settings.DEFAULT_THUMB_SIZE_TUPLE[0],
                                          settings.DEFAULT_THUMB_SIZE_TUPLE[1]),
                '-quality', '60',
                'png:-'
            ]
            
            thumb_data = subprocess.check_output(convert_cmd, input=frame_data)
            thumb_io.write(thumb_data)
            thumb_io.seek(0)
            return "thumb_{}.png".format(Path(name).stem), ContentFile(thumb_io.getvalue(),
                                                                       "thumb_{}.png".format(Path(name).stem))
        else:
            raise Exception("Failed to extract video frame")
            
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to create video thumbnail: {}".format(e.stderr.decode('utf-8')))
    except subprocess.TimeoutExpired:
        raise Exception("Video thumbnail generation timed out")
    except Exception as e:
        raise Exception("Error processing video thumbnail: {}".format(e))


def create_avatar_thumbs(entity_file: EntityFile, media_file: MediaFile) -> list:
    from PIL import Image
    
    name = Path(entity_file.file.name).stem
    symlink_name = Path(media_file.name).stem
    image = Image.open(entity_file.file)
    for size in settings.THUMBS_SIZE_LIST:
        if image.size[0] > size:
            thumbnail, created = entity_file.thumbnail_set.get_or_create(
                is_avatar=True,
                side_size=size
            )
            if created:
                thumbnail.file.save(*resize_avatar(image, name, size))
            create_symlink(
                path=thumbnail.file.path,
                file_name="{}_{}.webp".format(size, symlink_name),
                title=media_file.title,
            )


def create_avatar_thumbs(entity_file: EntityFile, media_file: MediaFile) -> list:
    """
    Create avatar thumbnails using ImageMagick
    """
    name = Path(entity_file.file.name).stem
    symlink_name = Path(media_file.name).stem
    
    for size in settings.THUMBS_SIZE_LIST:
        # Check if original image is larger than the thumbnail size we want to create
        identify_cmd = ['identify', '-format', '%w', entity_file.file.path]
        try:
            original_width = int(subprocess.check_output(identify_cmd).decode('utf-8').strip())
            if original_width < size:
                continue
        except subprocess.CalledProcessError:
            continue
        
        thumbnail, created = entity_file.thumbnail_set.get_or_create(
            is_avatar=True,
            side_size=size
        )
        
        if created:
            try:
                filename, content_file = resize_avatar(entity_file.file.path, name, size)
                thumbnail.file.save(filename, content_file)
            except Exception as e:
                print("Error creating thumbnail: {}".format(e))
                continue
        
        create_symlink(
            path=thumbnail.file.path,
            file_name="{}_{}.webp".format(size, symlink_name),
            title=media_file.title,
        )


def resize_avatar(image_path: str, name: str, size: int) -> Tuple[str, ContentFile]:
    """
    Resize avatar using ImageMagick's convert command
    Returns tuple of (filename, ContentFile)
    """
    # Create in-memory file
    thumb_io = BytesIO()
    
    # Use ImageMagick to resize and convert to webp
    convert_cmd = [
        'convert',
        image_path,
        '-resize', '{size}x{size}'.format(size=size),
        '-quality', '100',
        '-define', 'webp:lossless=true',
        '-define', 'webp:method=1',
        'webp:-'
    ]
    
    try:
        webp_data = subprocess.check_output(convert_cmd)
        thumb_io.write(webp_data)
        thumb_io.seek(0)
        return '{}_{}'.format(size, name), ContentFile(thumb_io.getvalue(), '{}_{}.webp'.format(size, name))
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to resize avatar: {}".format(e))


def create_thumbnails(media_file: MediaFile, avatar_thumbs: bool = False) -> None:

    """ Create thumbnails and symlinks for media file """

    # try, except for using threading
    try:
        entity_file = media_file.entity_file
        media_type, _format = media_file.media_type.split('/')

        if media_type in ['image', 'video']:

            thumbnail, created = Thumbnail.objects.get_or_create(
                entity_file=entity_file,
                is_avatar=False
            )

            if created:
                if media_type == 'image':
                    thumb = create_image_thumb(entity_file.file.path, entity_file.get_filename())
                else:
                    thumb = create_video_thumb(entity_file.file.path, entity_file.get_filename())
                thumbnail.file.save(*thumb)

            if media_type == 'video':
                name = os.path.splitext(media_file.name)[0]
                name = 'thumb_{}.png'.format(name)
            else:
                name = 'thumb_{}'.format(media_file.name)

            create_symlink(
                path=thumbnail.file.path,
                file_name=name,
                title=media_file.title,
            )

        if media_file.context == 'avatar' and avatar_thumbs and media_type == 'image':
            create_avatar_thumbs(entity_file, media_file)
    except Exception as e:
        print(e)


def crop_avatar(file) -> dict:
    """
    Crop avatar using ImageMagick's convert command
    Returns dict with max_size of the cropped image
    """
    temp_path = file.temporary_file_path()
    
    # Get original dimensions using ImageMagick's identify
    identify_cmd = ['identify', '-format', '%wx%h', '{}[0]'.format(temp_path)]
    try:
        dimensions = subprocess.check_output(identify_cmd).decode('utf-8').strip()
        width, height = map(int, dimensions.split('x'))
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to get image dimensions: {}".format(e))
    
    # Determine new size
    new_size = width
    if not width == height or width >= settings.MAX_AVATAR_SIZE:
        max_dim = max(width, height)
        min_dim = min(width, height)
        new_size = settings.MAX_AVATAR_SIZE if max_dim >= settings.MAX_AVATAR_SIZE else min_dim
        
        # Crop command
        convert_cmd = [
            'convert',
            temp_path,
            '-gravity', 'center',
            '-background', 'transparent',
            '-extent', '{new_size}x{new_size}'.format(new_size=new_size),
            temp_path
        ]
        
        try:
            subprocess.run(convert_cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise Exception("Failed to crop image: {}".format(e))
    
    return {
        "max_size": new_size
    }
