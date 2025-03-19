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
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check file exists and has content
                if not os.path.exists(file_path):
                    logger.error(f"File does not exist: {file_path}")
                    raise FileNotFoundError(f"File does not exist: {file_path}")
                
                file_size = os.path.getsize(file_path)
                logger.info(f"Uploading video file: {file_path} (size: {file_size / (1024 * 1024):.2f} MB)")
                
                if file_size == 0:
                    logger.error(f"File is empty: {file_path}")
                    raise ValueError(f"File is empty: {file_path}")
                
                # Create storage path
                date_prefix = datetime.now().strftime('%Y/%m/%d')
                storage_path = f"videos/{date_prefix}/{job_id}.mp4"
                
                # Upload file with more detailed logging
                logger.info(f"Starting upload to {storage_path} (attempt {attempt+1}/{max_retries})")
                blob: Blob = self.bucket.blob(storage_path)
                
                # Increase chunk size for more efficient uploads
                blob.chunk_size = 5 * 1024 * 1024  # 5MB chunks
                
                # Start upload
                start_time = time.time()
                blob.upload_from_filename(file_path)
                upload_time = time.time() - start_time
                
                logger.info(f"Upload completed in {upload_time:.2f} seconds")
                
                # Generate signed URL that's valid for 7 days
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=7),
                    method="GET"
                )
                
                logger.info(f"Successfully uploaded video and generated signed URL")
                return url
                
            except Exception as e:
                logger.error(f"Error uploading video for job {job_id} (attempt {attempt+1}/{max_retries}): {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                if attempt == max_retries - 1:
                    # This was the last attempt
                    logger.error(f"All {max_retries} upload attempts failed for job {job_id}")
                    raise
                
                # Wait before retrying with exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
        
        # This shouldn't be reached due to the raise in the loop, but just in case
        raise Exception(f"Failed to upload video after {max_retries} attempts")

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