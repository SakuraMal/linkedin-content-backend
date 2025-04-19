import os
import logging
import time
import traceback
from datetime import datetime, timedelta
from google.cloud import storage
from google.cloud.storage import Blob
from google.oauth2 import service_account
from typing import Optional

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        """Initialize the Google Cloud Storage service."""
        try:
            self.bucket_name = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')
            if not self.bucket_name:
                raise ValueError("GOOGLE_CLOUD_STORAGE_BUCKET environment variable not set")
            
            # Load credentials from service account file
            credentials_path = os.path.abspath('google_credentials.json')
            logger.info(f"Loading GCS credentials from: {credentials_path}")
            
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Initialize client with credentials
            self.client = storage.Client(credentials=credentials, project=credentials.project_id)
            self.bucket = self.client.bucket(self.bucket_name)
            
            logger.info(f"Initialized StorageService with bucket: {self.bucket_name}")
            logger.info(f"Using project: {self.client.project}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {str(e)}")
            raise

    def upload_video(self, file_path: str, job_id: str) -> str:
        """
        Upload a video file to Google Cloud Storage.
        
        Args:
            file_path: Path to the video file
            job_id: Job ID to use in the storage path
            
        Returns:
            str: Public URL of the uploaded video
        """
        try:
            # Generate a unique filename using job_id and timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{job_id}_{timestamp}.mp4"
            blob_path = f"videos/{filename}"
            
            # Upload the file
            blob = self.bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
            
            # Make the blob publicly accessible
            blob.make_public()
            
            # Get the public URL
            url = blob.public_url
            
            logger.info(f"Video uploaded successfully to: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload video: {str(e)}")
            raise

    def delete_video(self, job_id: str) -> bool:
        """
        Delete a video from Google Cloud Storage.
        
        Args:
            job_id: Job ID of the video to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # List all blobs in the videos directory
            blobs = self.bucket.list_blobs(prefix="videos/")
            
            # Find and delete the blob with matching job_id
            for blob in blobs:
                if job_id in blob.name:
                    blob.delete()
                    logger.info(f"Deleted video: {blob.name}")
                    return True
            
            logger.warning(f"No video found for job {job_id}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete video: {str(e)}")
            return False

    def get_video_url(self, job_id: str) -> Optional[str]:
        """
        Get the public URL of a video by job_id.
        
        Args:
            job_id: Job ID of the video
            
        Returns:
            Optional[str]: Public URL of the video if found, None otherwise
        """
        try:
            # List all blobs in the videos directory
            blobs = self.bucket.list_blobs(prefix="videos/")
            
            # Find the blob with matching job_id
            for blob in blobs:
                if job_id in blob.name:
                    # Make sure the blob is publicly accessible
                    if not blob.public_url:
                        blob.make_public()
                    
                    url = blob.public_url
                    logger.info(f"Found video URL: {url}")
                    return url
            
            logger.warning(f"No video found for job {job_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting video URL for job {job_id}: {str(e)}")
            return None 