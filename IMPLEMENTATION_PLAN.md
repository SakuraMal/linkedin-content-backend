# Implementation Plan: Custom Image Upload for Videos

## Overview

This document outlines the implementation plan for adding support for user-uploaded images in video generation. The feature will allow users to upload up to 3 images (2MB per image, 6MB total) which will be used to create video segments with the provided content.

## Backend Changes

### 1. File Storage Setup

#### Google Cloud Storage Configuration

1. Create a new bucket for user uploads:
   ```bash
   gsutil mb -l us-central1 gs://linkedin-content-user-uploads
   ```

2. Set appropriate CORS configuration:
   ```bash
   gsutil cors set cors-config.json gs://linkedin-content-user-uploads
   ```

3. Configure lifecycle policies for automatic cleanup:
   ```bash
   gsutil lifecycle set lifecycle-config.json gs://linkedin-content-user-uploads
   ```

4. Update service account permissions if necessary.

#### Configuration Files

**cors-config.json**:
```json
[
  {
    "origin": ["https://linkedin-content-frontend.vercel.app", "http://localhost:3000"],
    "method": ["GET", "POST", "PUT", "DELETE"],
    "responseHeader": ["Content-Type", "Authorization"],
    "maxAgeSeconds": 3600
  }
]
```

**lifecycle-config.json**:
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 7
        }
      }
    ]
  }
}
```

### 2. File Validation Service

Create a new service for validating uploaded files:

**app/services/storage/file_validator.py**:
```python
import os
import magic
from typing import List, Tuple, Dict, Any
from werkzeug.datastructures import FileStorage

class FileValidator:
    def __init__(self, 
                 max_files: int = 3, 
                 max_file_size: int = 2 * 1024 * 1024,  # 2MB
                 allowed_types: List[str] = None):
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.allowed_types = allowed_types or ['image/jpeg', 'image/png', 'image/jpg']
        
    def validate_files(self, files: List[FileStorage]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate uploaded files against constraints
        
        Returns:
            Tuple[bool, Dict]: (is_valid, validation_result)
        """
        if not files:
            return False, {"error": "No files provided"}
            
        if len(files) > self.max_files:
            return False, {"error": f"Too many files. Maximum allowed: {self.max_files}"}
        
        total_size = 0
        validation_errors = []
        
        for file in files:
            # Check file size
            if file.content_length > self.max_file_size:
                validation_errors.append(f"File {file.filename} exceeds maximum size of {self.max_file_size / (1024 * 1024)}MB")
            
            total_size += file.content_length
            
            # Check file type using python-magic
            file_content = file.read(2048)  # Read first 2KB for MIME detection
            file.seek(0)  # Reset file pointer
            
            mime_type = magic.from_buffer(file_content, mime=True)
            if mime_type not in self.allowed_types:
                validation_errors.append(f"File {file.filename} has unsupported type: {mime_type}")
                
            # Additional security checks could be added here
            
        if total_size > (self.max_files * self.max_file_size):
            validation_errors.append(f"Total upload size exceeds maximum of {self.max_files * self.max_file_size / (1024 * 1024)}MB")
            
        if validation_errors:
            return False, {"error": validation_errors}
            
        return True, {"message": "Files validated successfully"}
```

### 3. Image Storage Service

Create a service for storing uploaded images:

**app/services/storage/image_storage.py**:
```python
import os
import uuid
import logging
from typing import List, Dict, Any
from google.cloud import storage
from werkzeug.datastructures import FileStorage

class ImageStorage:
    def __init__(self, bucket_name: str = "linkedin-content-user-uploads"):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.logger = logging.getLogger(__name__)
        
    def upload_images(self, files: List[FileStorage], user_id: str = None) -> List[Dict[str, Any]]:
        """
        Upload images to Google Cloud Storage
        
        Args:
            files: List of file objects
            user_id: Optional user ID for organizing uploads
            
        Returns:
            List of dictionaries with image details
        """
        uploaded_images = []
        
        for file in files:
            try:
                # Generate a unique ID for the image
                image_id = str(uuid.uuid4())
                
                # Create a safe filename
                original_filename = file.filename
                file_extension = os.path.splitext(original_filename)[1].lower()
                safe_filename = f"{image_id}{file_extension}"
                
                # Determine storage path
                storage_path = f"user_uploads/{user_id or 'anonymous'}/{safe_filename}"
                
                # Create a blob and upload the file
                blob = self.bucket.blob(storage_path)
                
                # Set metadata
                metadata = {
                    'original_filename': original_filename,
                    'content_type': file.content_type,
                }
                blob.metadata = metadata
                
                # Upload the file
                blob.upload_from_file(file)
                
                # Generate a signed URL for temporary access
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=60 * 60 * 24,  # 24 hours
                    method="GET"
                )
                
                # Add to uploaded images list
                uploaded_images.append({
                    "id": image_id,
                    "filename": original_filename,
                    "storage_path": storage_path,
                    "url": signed_url,
                    "content_type": file.content_type
                })
                
            except Exception as e:
                self.logger.error(f"Error uploading file {file.filename}: {str(e)}")
                # Continue with other files even if one fails
                continue
                
        return uploaded_images
        
    def get_image_url(self, image_id: str) -> str:
        """
        Get a signed URL for an image by ID
        
        Args:
            image_id: The image ID
            
        Returns:
            Signed URL for the image
        """
        # In a real implementation, you would look up the storage path from a database
        # For this example, we'll assume a simple pattern
        blobs = list(self.bucket.list_blobs(prefix=f"user_uploads/"))
        
        for blob in blobs:
            if image_id in blob.name:
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=60 * 60 * 24,  # 24 hours
                    method="GET"
                )
                return signed_url
                
        return None
```

### 4. Database Schema Updates

Add a new table for tracking uploaded images:

**app/models/image.py**:
```python
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Image(Base):
    __tablename__ = "images"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships could be added here
```

### 5. API Endpoint for Image Upload

Create a new endpoint for handling image uploads:

**app/routes/video.py** (add to existing file):
```python
@video_routes.route('/upload-images', methods=['POST'])
def upload_images():
    """
    Handle image uploads for video generation
    """
    try:
        # Get files from request
        if 'images[]' not in request.files:
            return jsonify({
                "success": False,
                "message": "No images provided"
            }), 400
            
        files = request.files.getlist('images[]')
        
        # Validate files
        from app.services.storage.file_validator import FileValidator
        validator = FileValidator()
        is_valid, validation_result = validator.validate_files(files)
        
        if not is_valid:
            return jsonify({
                "success": False,
                "message": "File validation failed",
                "errors": validation_result["error"]
            }), 400
            
        # Upload files to storage
        from app.services.storage.image_storage import ImageStorage
        storage = ImageStorage()
        
        # Get user ID from request if available
        user_id = request.headers.get('X-User-ID')
        
        # Upload images
        uploaded_images = storage.upload_images(files, user_id)
        
        # Store image metadata in database
        from app.models.image import Image
        from app.database import db_session
        
        image_ids = []
        for image in uploaded_images:
            db_image = Image(
                id=image["id"],
                user_id=user_id,
                original_filename=image["filename"],
                storage_path=image["storage_path"],
                content_type=image["content_type"]
            )
            db_session.add(db_image)
            image_ids.append(image["id"])
            
        db_session.commit()
        
        # Return success response with image IDs
        return jsonify({
            "success": True,
            "message": f"Successfully uploaded {len(uploaded_images)} images",
            "data": {
                "image_ids": image_ids,
                "images": uploaded_images
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error uploading images: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred while uploading images"
        }), 500
```

### 6. Update Video Generator

Modify the video generator to support user-uploaded images:

**app/services/media/video_generator.py** (update existing file):
```python
# Add to imports
from app.services.storage.image_storage import ImageStorage

# Update generate_video method
def generate_video(self, content, style="professional", duration=30, user_image_ids=None, **kwargs):
    """
    Generate a video from text content and optional user-provided images
    
    Args:
        content: The text content for the video
        style: The style of the video
        duration: Target duration in seconds
        user_image_ids: Optional list of user-uploaded image IDs
    """
    try:
        # Process text
        processed_text = self.text_processor.process_text(content, target_duration=duration)
        
        # Get images - either from user uploads or generate them
        if user_image_ids and len(user_image_ids) > 0:
            # Use user-provided images
            image_storage = ImageStorage()
            image_urls = []
            
            for image_id in user_image_ids:
                image_url = image_storage.get_image_url(image_id)
                if image_url:
                    image_urls.append(image_url)
            
            # If we couldn't get any valid image URLs, fall back to generated images
            if not image_urls:
                self.logger.warning("No valid user images found, falling back to generated images")
                image_urls = self.image_generator.generate_images(processed_text, style=style)
        else:
            # Generate images based on the text
            image_urls = self.image_generator.generate_images(processed_text, style=style)
        
        # Continue with existing video generation logic...
        # ...
    
    except Exception as e:
        self.logger.error(f"Error generating video: {str(e)}")
        raise
```

### 7. Update API Schema

Update the API schema to include user image IDs:

**app/schemas/video.py**:
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class VideoRequest(BaseModel):
    content: str
    style: str = "professional"
    duration: int = 30
    post_id: Optional[str] = None
    content_analysis: Optional[Dict[str, Any]] = None
    user_image_ids: Optional[List[str]] = None
    theme: Optional[str] = "business"
```

## Testing Plan

### Unit Tests

1. **File Validation Tests**:
   - Test file size validation
   - Test file type validation
   - Test file count validation

2. **Image Storage Tests**:
   - Test image upload
   - Test signed URL generation

3. **API Endpoint Tests**:
   - Test successful upload
   - Test validation errors
   - Test error handling

### Integration Tests

1. **End-to-End Flow**:
   - Upload images
   - Generate video with uploaded images
   - Verify video contains uploaded images

2. **Error Handling**:
   - Test with invalid files
   - Test with missing files
   - Test with too many files

## Deployment Checklist

1. Install required dependencies:
   ```bash
   pip install python-magic google-cloud-storage
   ```

2. Set up Google Cloud Storage credentials:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   ```

3. Create the GCS bucket and configure CORS and lifecycle policies.

4. Deploy the updated application:
   ```bash
   fly deploy
   ```

5. Test the deployed endpoints:
   ```bash
   curl -X POST -F "images[]=@test.jpg" https://linkedin-content-backend.fly.dev/api/video/upload-images
   ```

## Monitoring and Logging

1. Add specific logging for image uploads:
   ```python
   app.logger.info(f"User {user_id} uploaded {len(files)} images")
   ```

2. Monitor storage usage:
   ```bash
   gsutil du -s gs://linkedin-content-user-uploads
   ```

3. Set up alerts for storage quota limits.

## Security Considerations

1. Implement rate limiting for the upload endpoint.
2. Scan uploaded files for malware.
3. Validate file content beyond just MIME type.
4. Use signed URLs with short expiration times.
5. Implement proper access controls for the storage bucket.

## Recent Updates and Fixed Issues

### Custom Image Handling Fixes (March 2024)

#### Identified Issues

1. **Generator Logic Inconsistency**:
   - The `generate_video` method in `app/services/video/generator.py` was attempting to fetch media assets from Unsplash even when user images were provided but could not be fetched.
   - This behavior contradicted the documented functionality, which states that only user-uploaded images should be used when available.
   - The code would fall back to Unsplash images if user images were provided but couldn't be fetched, rather than failing with a clear error message.

2. **Inefficient Image URL Retrieval**:
   - The `get_image_url` method in `app/services/storage/image_storage.py` was inefficiently listing all blobs in the storage folder to find a specific image.
   - This approach could lead to timeouts and performance issues as the number of stored images grows.

#### Implemented Fixes

1. **Generator Fixes (Video Generation Logic)**:
   - Modified the video generation logic to strictly follow the behavior of only using user-uploaded images when provided.
   - Added explicit error handling and status updates when user images cannot be fetched.
   - Removed the fallback to Unsplash when user-provided images fail to load, instead failing with a clear error message.
   - Implemented clearer code structure using an if/else pattern to explicitly choose between user images and Unsplash images.

2. **Storage Service Fixes (Image Retrieval)**:
   - Improved the `get_image_url` method to use a more specific prefix that includes the image ID.
   - Implemented `next(blobs, None)` to efficiently retrieve the first matching blob without iterating through all blobs.
   - Added more detailed logging for both successful and unsuccessful image retrieval attempts.
   - Enhanced error handling for exceptions during the URL retrieval process.

#### Benefits of Changes

1. **For Video Generation**:
   - More predictable behavior: if user uploads images, only those images will be used.
   - Clearer error handling: descriptive error messages when user images cannot be fetched.
   - Better adherence to documented functionality.

2. **For Image Retrieval**:
   - Faster image URL retrieval due to more specific blob filtering.
   - Reduced memory usage by eliminating full blob list iteration.
   - Enhanced logging for better debugging and diagnostics.
   - More scalable solution as the number of stored images grows.

#### Remaining Work (Pending Testing)

While the fixes address the identified issues, thorough testing is required to confirm:

1. User-uploaded images are correctly used in video generation.
2. Appropriate error messages are displayed when user images cannot be fetched.
3. Performance improvements in image URL retrieval with larger datasets.
4. Proper cleanup of resources in all scenarios.

_Note: These fixes have been deployed but should be considered provisional until verified through complete testing._ 