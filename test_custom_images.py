#!/usr/bin/env python3

"""
Test script for generating videos with custom images.
This script helps diagnose issues with the custom image video generation process.

Usage:
    python test_custom_images.py --image_ids <id1> <id2> <id3>
"""

import os
import sys
import json
import time
import logging
import argparse
import traceback
from redis import Redis

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("custom_images_test")

def setup_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Test video generation with custom images')
    parser.add_argument('--image_ids', type=str, nargs='+', required=True, 
                      help='Image IDs to use for the video (required)')
    parser.add_argument('--text', type=str, 
                      default="This is a test video using custom images. We're testing the video generation process with user-uploaded images.", 
                      help='Text content for the video')
    parser.add_argument('--duration', type=int, default=15, help='Video duration in seconds')
    parser.add_argument('--style', type=str, default='professional', help='Video style')
    return parser.parse_args()

def main():
    """Main execution function"""
    args = setup_args()
    
    if not args.image_ids:
        logger.error("No image IDs provided. Use --image_ids to specify one or more image IDs.")
        sys.exit(1)
    
    logger.info(f"Testing video generation with {len(args.image_ids)} custom images")
    logger.info(f"Image IDs: {args.image_ids}")
    
    # Import where needed to avoid circular imports
    from app.models.video import VideoGenerationRequest
    from app.services.video.generator import VideoGenerator
    import uuid
    
    # Create a unique job ID
    job_id = str(uuid.uuid4())
    logger.info(f"Created test job ID: {job_id}")
    
    # Connect to Redis
    redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    
    # Initialize video generator
    video_generator = VideoGenerator()
    
    # Create video request
    request = VideoGenerationRequest(
        content=args.text,
        style=args.style,
        duration=args.duration,
        user_image_ids=args.image_ids
    )
    
    logger.info(f"Video request: {json.dumps(request.model_dump(), indent=2)}")
    
    start_time = time.time()
    
    try:
        # Generate video
        logger.info("Starting video generation process")
        video_url = video_generator.process_video(job_id, request, redis_client)
        
        # Calculate duration
        duration = time.time() - start_time
        
        logger.info(f"Video generation completed in {duration:.2f} seconds")
        logger.info(f"Video URL: {video_url}")
        
        return True
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Calculate duration
        duration = time.time() - start_time
        logger.info(f"Video generation failed after {duration:.2f} seconds")
        
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 