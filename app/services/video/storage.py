import os
import logging
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
            # Create storage path
            date_prefix = datetime.now().strftime('%Y/%m/%d')
            storage_path = f"videos/{date_prefix}/{job_id}.mp4"
            
            # Upload file
            blob: Blob = self.bucket.blob(storage_path)
            blob.upload_from_filename(file_path)
            
            # Generate signed URL that's valid for 7 days
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(days=7),
                method="GET"
            )
            
            logger.info(f"Successfully uploaded video and generated signed URL")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading video for job {job_id}: {str(e)}")
            raise

    def delete_video(self, job_id: str) -> bool:
        """
        Delete a video from Google Cloud Storage.
        
        Args:
            job_id: Job ID of the video to delete
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            # List blobs with prefix
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=f"videos/"
            )
            
            # Find and delete the video
            target_suffix = f"/{job_id}.mp4"
            for blob in blobs:
                if blob.name.endswith(target_suffix):
                    blob.delete()
                    logger.info(f"Successfully deleted video for job {job_id}")
                    return True
            
            logger.warning(f"No video found for job {job_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting video for job {job_id}: {str(e)}")
            return False

    def get_video_url(self, job_id: str) -> Optional[str]:
        """
        Get a signed URL for a video.
        
        Args:
            job_id: Job ID of the video
            
        Returns:
            Optional[str]: Signed URL of the video if found
        """
        try:
            # List blobs with prefix
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=f"videos/"
            )
            
            # Find the video and generate signed URL
            target_suffix = f"/{job_id}.mp4"
            for blob in blobs:
                if blob.name.endswith(target_suffix):
                    url = blob.generate_signed_url(
                        version="v4",
                        expiration=timedelta(days=7),
                        method="GET"
                    )
                    return url
            
            logger.warning(f"No video found for job {job_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting video URL for job {job_id}: {str(e)}")
            return None

# Create a singleton instance
storage_service = StorageService() 