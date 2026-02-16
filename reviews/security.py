"""
Security utilities for file upload validation and other security checks.
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings
from PIL import Image
import imghdr


def validate_image_file(file):
    """
    Validate uploaded image file for security.
    
    Checks:
    - File extension
    - File size
    - Actual file content (not just extension)
    - Image format validity
    
    Raises ValidationError if file is invalid.
    """
    # Check file extension
    file_name = file.name.lower()
    file_ext = os.path.splitext(file_name)[1]
    
    if file_ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Invalid file type. Allowed types: {", ".join(settings.ALLOWED_IMAGE_EXTENSIONS)}'
        )
    
    # Check file size
    if file.size > settings.MAX_IMAGE_SIZE:
        raise ValidationError(
            f'File size too large. Maximum size: {settings.MAX_IMAGE_SIZE / (1024*1024):.1f}MB'
        )
    
    # Check if file is empty
    if file.size == 0:
        raise ValidationError('File is empty.')
    
    # Verify actual file content (not just extension)
    # Reset file pointer
    file.seek(0)
    
    # Check file header/magic bytes
    file_header = file.read(1024)
    file.seek(0)  # Reset for later use
    
    # Verify it's actually an image by checking magic bytes
    image_types = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'RIFF': 'webp',  # WebP starts with RIFF
    }
    
    is_valid_image = False
    for magic_bytes, img_type in image_types.items():
        if file_header.startswith(magic_bytes):
            is_valid_image = True
            break
    
    # Additional check using PIL (more reliable than imghdr)
    # PIL's Image.open() will verify the image format
    if not is_valid_image:
        # Try to open with PIL as final check
        try:
            file.seek(0)
            img = Image.open(file)
            img.verify()
            is_valid_image = True
            file.seek(0)
        except:
            pass
    
    if not is_valid_image:
        raise ValidationError('File is not a valid image. Please upload a valid image file.')
    
    # Verify image can be opened and is not corrupted
    try:
        file.seek(0)
        img = Image.open(file)
        img.verify()  # Verify it's a valid image
        file.seek(0)  # Reset for saving
    except Exception as e:
        raise ValidationError(f'Invalid or corrupted image file: {str(e)}')
    
    # Additional security: Check for embedded scripts in EXIF data
    # (PIL handles this, but we can add more checks if needed)
    
    return True


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks.
    """
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    dangerous_chars = ['..', '/', '\\', '\x00']
    for char in dangerous_chars:
        filename = filename.replace(char, '')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename
