#!/usr/bin/env python3

"""
Debug script for monitoring video generation process.
Run this script to generate a test video with detailed debugging information.
"""

import os
import sys
import json
import time
import logging
import psutil
import traceback
import argparse
from pathlib import Path
from pprint import pprint

# Set up environment
os.environ["DEBUG_VIDEO"] = "true"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("video_debug")

def setup_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Debug video generation process')
    parser.add_argument('--images', type=str, nargs='+', help='Image IDs to use for the video')
    parser.add_argument('--text', type=str, default="This is a test video to debug the video generation process. We're monitoring memory usage and performance at each step.", 
                        help='Text content for the video')
    parser.add_argument('--duration', type=int, default=15, help='Video duration in seconds')
    parser.add_argument('--style', type=str, default='professional', help='Video style')
    return parser.parse_args()

def monitor_process():
    """Monitor the current process for memory usage"""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    logger.info(f"Memory usage: {memory_mb:.2f} MB")
    return memory_mb

def generate_test_video(args):
    """
    Generate a test video with the provided parameters
    """
    # Import where needed to avoid circular imports
    from app.models.video import VideoGenerationRequest
    from app.services.video.generator import VideoGenerator
    from redis import Redis
    import uuid
    
    # Create a unique job ID
    job_id = str(uuid.uuid4())
    logger.info(f"Starting debug video generation with job ID: {job_id}")
    
    # Monitor resources before starting
    start_memory = monitor_process()
    start_time = time.time()
    
    # Connect to Redis
    redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    
    # Initialize video generator
    video_generator = VideoGenerator()
    
    # Create video request
    request = VideoGenerationRequest(
        content=args.text,
        style=args.style,
        duration=args.duration,
        user_image_ids=args.images if args.images else None
    )
    
    logger.info(f"Video request: {json.dumps(request.model_dump(), indent=2)}")
    
    try:
        # Generate video
        logger.info("Starting video generation process")
        video_url = video_generator.process_video(job_id, request, redis_client)
        
        # Calculate final stats
        end_time = time.time()
        end_memory = monitor_process()
        duration = end_time - start_time
        
        logger.info(f"Video generation completed in {duration:.2f} seconds")
        logger.info(f"Memory usage: initial={start_memory:.2f} MB, final={end_memory:.2f} MB, delta={end_memory-start_memory:.2f} MB")
        logger.info(f"Video URL: {video_url}")
        
        return video_url
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Calculate final stats even on error
        end_time = time.time()
        try:
            end_memory = monitor_process()
            duration = end_time - start_time
            logger.info(f"Video generation failed after {duration:.2f} seconds")
            logger.info(f"Memory usage: initial={start_memory:.2f} MB, final={end_memory:.2f} MB, delta={end_memory-start_memory:.2f} MB")
        except:
            pass
        
        return None

if __name__ == "__main__":
    logger.info("Debug video generation script starting")
    args = setup_args()
    
    # Log system information
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Total system memory: {psutil.virtual_memory().total / (1024 * 1024 * 1024):.2f} GB")
    logger.info(f"Available system memory: {psutil.virtual_memory().available / (1024 * 1024 * 1024):.2f} GB")
    
    # Generate test video
    result = generate_test_video(args)
    
    if result:
        logger.info("Video generation succeeded!")
    else:
        logger.error("Video generation failed!")
        sys.exit(1) 