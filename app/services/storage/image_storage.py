import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from werkzeug.datastructures import FileStorage
from google.cloud import storage
from google.cloud.storage import Blob

# Import the existing storage service
from app.services.video.storage import StorageService

logger = logging.getLogger(__name__)

class ImageStorageService:
    """
    Service for storing and retrieving user-uploaded images in Google Cloud Storage.
    
    This service extends the existing StorageService functionality to handle image uploads.
    """
    
    def __init__(self):
        """Initialize the image storage service using the existing GCS configuration."""
        # Reuse the existing StorageService for GCS access
        self.storage_service = StorageService()
        self.client = self.storage_service.client
        self.bucket = self.storage_service.bucket
        self.bucket_name = self.storage_service.bucket_name
        
        # Set up image-specific configuration
        self.image_folder = "user_uploads/images"
        logger.info(f"Initialized ImageStorageService with bucket: {self.bucket_name}")
        
    def upload_images(self, files: List[FileStorage], user_id: str = None) -> List[Dict[str, Any]]:
        """
        Upload multiple images to Google Cloud Storage.
        
        Args:
            files: List of file objects to upload
            user_id: Optional user ID for organizing uploads
            
        Returns:
            List of dictionaries with image details
        """
        uploaded_images = []
        
        # Create a folder structure with date for better organization
        date_prefix = datetime.now().strftime('%Y/%m/%d')
        user_folder = user_id or 'anonymous'
        
        for file in files:
            try:
                # Generate a unique ID for the image
                image_id = str(uuid.uuid4())
                
                # Create a safe filename
                original_filename = file.filename
                file_extension = os.path.splitext(original_filename)[1].lower()
                safe_filename = f"{image_id}{file_extension}"
                
                # Determine storage path
                storage_path = f"{self.image_folder}/{date_prefix}/{user_folder}/{safe_filename}"
                
                # Create a blob and upload the file
                blob = self.bucket.blob(storage_path)
                
                # Set metadata
                metadata = {
                    'original_filename': original_filename,
                    'content_type': file.content_type,
                    'user_id': user_id or 'anonymous',
                    'upload_date': datetime.now().isoformat()
                }
                blob.metadata = metadata
                
                # Upload the file
                blob.upload_from_file(file)
                
                # Generate a signed URL for temporary access (valid for 1 day)
                signed_url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=1),
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
                
                logger.info(f"Successfully uploaded image {image_id} to {storage_path}")
                
            except Exception as e:
                logger.error(f"Error uploading file {file.filename}: {str(e)}")
                # Continue with other files even if one fails
                continue
                
        return uploaded_images
        
    def get_image_url(self, image_id: str) -> Optional[str]:
        """
        Get a signed URL for an image by ID.
        
        Args:
            image_id: The image ID
            
        Returns:
            Optional[str]: Signed URL for the image if found
        """
        try:
            # List blobs with prefix
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=self.image_folder
            )
            
            # Find the image and generate signed URL
            for blob in blobs:
                # Check if the image ID is in the blob name
                if image_id in blob.name:
                    url = blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(days=1),
                        method="GET"
                    )
                    return url
            
            logger.warning(f"No image found with ID {image_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting image URL for ID {image_id}: {str(e)}")
            return None
            
    def delete_image(self, image_id: str) -> bool:
        """
        Delete an image from Google Cloud Storage.
        
        Args:
            image_id: ID of the image to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            # List blobs with prefix
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=self.image_folder
            )
            
            # Find and delete the image
            for blob in blobs:
                if image_id in blob.name:
                    blob.delete()
                    logger.info(f"Successfully deleted image with ID {image_id}")
                    return True
            
            logger.warning(f"No image found with ID {image_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting image with ID {image_id}: {str(e)}")
            return False

# Create a singleton instance
image_storage_service = ImageStorageService() 