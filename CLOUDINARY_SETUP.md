# Cloudinary Setup Guide

This project uses Cloudinary for image storage and management. All property images are stored on Cloudinary instead of local storage.

## Installation

1. Install the required packages:
```bash
pip install cloudinary django-cloudinary-storage
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

## Configuration

1. **Sign up for Cloudinary** (if you haven't already):
   - Go to https://cloudinary.com/
   - Create a free account
   - Get your credentials from the Dashboard

2. **Set Environment Variables**:
   
   Add these to your `.env` file or environment:
   ```bash
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

   Or set them directly in `settings.py` (not recommended for production):
   ```python
   CLOUDINARY_STORAGE = {
       'CLOUD_NAME': 'your_cloud_name',
       'API_KEY': 'your_api_key',
       'API_SECRET': 'your_api_secret',
   }
   ```

## Features

- **Automatic Image Optimization**: Cloudinary automatically optimizes images
- **CDN Delivery**: Images are delivered via Cloudinary's CDN for fast loading
- **Transformations**: Images can be transformed on-the-fly (resize, crop, etc.)
- **Storage Management**: All images stored in the cloud, no local storage needed

## Migration

After setting up Cloudinary credentials, run migrations:
```bash
python manage.py migrate
```

## Image URLs

Cloudinary images will have URLs like:
- `https://res.cloudinary.com/your_cloud_name/image/upload/v1234567890/properties/image.jpg`

The Django ORM will handle these URLs automatically - you can still use `property.image.url` in templates.

## Fallback

If Cloudinary is not configured, the system will fall back to local storage. Make sure to set your Cloudinary credentials before deploying to production.
