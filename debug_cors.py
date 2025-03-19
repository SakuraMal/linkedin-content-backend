#!/usr/bin/env python3
import os
from google.cloud import storage
from google.oauth2 import service_account
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_cors_for_bucket():
    """Set up CORS on GCS bucket to allow video content to be loaded from any origin."""
    try:
        # Load credentials
        credentials_path = os.path.abspath('google_credentials.json')
        logger.info(f"Loading GCS credentials from: {credentials_path}")
        
        # Make sure credentials file exists
        if not os.path.exists(credentials_path):
            logger.error(f"Credentials file not found at {credentials_path}")
            return False
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Initialize client with credentials
        client = storage.Client(credentials=credentials, project=credentials.project_id)
        
        # Get bucket name - using hardcoded value from logs
        # Found in the video URL: https://storage.googleapis.com/paa-some-videos/videos/...
        bucket_name = 'paa-some-videos'
        logger.info(f"Setting up CORS for bucket: {bucket_name}")
        
        # Get bucket
        bucket = client.bucket(bucket_name)
        
        # Define CORS configuration
        cors_config = [
            {
                "origin": ["*"],  # Allow access from any origin
                "method": ["GET", "HEAD", "OPTIONS"],
                "responseHeader": [
                    "Content-Type", 
                    "Content-Length", 
                    "Content-Disposition",
                    "Access-Control-Allow-Origin"
                ],
                "maxAgeSeconds": 3600  # Cache for 1 hour
            }
        ]
        
        # Apply CORS configuration
        bucket.cors = cors_config
        bucket.update()
        
        logger.info(f"CORS configuration applied successfully to bucket {bucket_name}")
        logger.info(f"CORS configuration: {json.dumps(cors_config, indent=2)}")
        
        # Check if it was applied correctly
        bucket = client.bucket(bucket_name)
        logger.info(f"Current CORS configuration: {json.dumps(bucket.cors, indent=2)}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting up CORS: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting CORS setup for GCS bucket")
    success = setup_cors_for_bucket()
    if success:
        logger.info("CORS setup completed successfully!")
    else:
        logger.error("CORS setup failed!") 