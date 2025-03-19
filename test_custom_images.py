#!/usr/bin/env python3

"""
Test script for custom image video generation

This script helps test the end-to-end flow of:
1. Uploading custom images
2. Generating a video with those images
3. Checking the status until completion

Usage:
    python test_custom_images.py --images image1.jpg image2.jpg --content "Your video content here"
"""

import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime

# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:5000/api')
MAX_WAIT_TIME = 300  # Maximum wait time in seconds (5 minutes)
POLL_INTERVAL = 5    # Status check interval in seconds

def upload_images(image_paths):
    """Upload images to the API and return the image IDs."""
    print(f"Uploading {len(image_paths)} images...")
    
    # Prepare form data with images
    files = []
    for i, image_path in enumerate(image_paths):
        if not os.path.exists(image_path):
            print(f"Error: Image file not found: {image_path}")
            sys.exit(1)
            
        files.append(('images', (os.path.basename(image_path), open(image_path, 'rb'), 'image/jpeg')))
    
    # Make upload request
    try:
        response = requests.post(
            f"{API_BASE_URL}/video/upload-images",
            files=files
        )
        
        if response.status_code != 200:
            print(f"Error uploading images: {response.text}")
            sys.exit(1)
        
        result = response.json()
        image_ids = result.get('image_ids', [])
        
        if not image_ids:
            print("No image IDs were returned from the upload")
            sys.exit(1)
        
        print(f"Successfully uploaded {len(image_ids)} images")
        return image_ids
        
    except Exception as e:
        print(f"Error during upload: {e}")
        sys.exit(1)

def generate_video(image_ids, content):
    """Generate a video using the uploaded images."""
    print(f"Generating video with {len(image_ids)} images...")
    
    # Prepare request payload
    payload = {
        "content": content,
        "user_image_ids": image_ids,
        "style": "professional",
        "duration": 15,  # 15 seconds video
        "voice": "en-US-Neural2-F"
    }
    
    # Make generation request
    try:
        response = requests.post(
            f"{API_BASE_URL}/video/generate",
            json=payload
        )
        
        if response.status_code != 200:
            print(f"Error generating video: {response.text}")
            sys.exit(1)
        
        result = response.json()
        job_id = result.get('job_id')
        
        if not job_id:
            print("No job ID was returned from the generation request")
            sys.exit(1)
        
        print(f"Video generation started with job ID: {job_id}")
        return job_id
        
    except Exception as e:
        print(f"Error during video generation: {e}")
        sys.exit(1)

def check_job_status(job_id):
    """Check the status of a video generation job."""
    try:
        response = requests.get(f"{API_BASE_URL}/video/status/{job_id}")
        
        if response.status_code != 200:
            print(f"Error checking job status: {response.text}")
            return None
        
        result = response.json()
        
        if result.get('status') != 'success':
            print(f"Error in status response: {result}")
            return None
        
        return result.get('data', {})
        
    except Exception as e:
        print(f"Error checking status: {e}")
        return None

def wait_for_completion(job_id):
    """Wait for job completion and show progress updates."""
    print(f"Waiting for job {job_id} to complete...")
    
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < MAX_WAIT_TIME:
        job_data = check_job_status(job_id)
        
        if not job_data:
            time.sleep(POLL_INTERVAL)
            continue
        
        status = job_data.get('status')
        progress = job_data.get('progress', 0)
        
        # Show progress update if changed
        if progress != last_progress:
            if status == 'failed':
                print(f"Job failed: {job_data.get('error', 'Unknown error')}")
                return None
                
            print(f"Status: {status} ({progress}%)")
            last_progress = progress
        
        # Check if complete
        if status == 'completed':
            video_url = job_data.get('video_url')
            print(f"Video generation completed in {int(time.time() - start_time)} seconds!")
            print(f"Video URL: {video_url}")
            return video_url
            
        # Wait before checking again
        time.sleep(POLL_INTERVAL)
    
    print(f"Timeout waiting for job completion after {MAX_WAIT_TIME} seconds")
    return None

def main():
    parser = argparse.ArgumentParser(description='Test custom image video generation')
    parser.add_argument('--images', nargs='+', required=True, help='Paths to image files')
    parser.add_argument('--content', required=True, help='Content for the video narration')
    
    args = parser.parse_args()
    
    if len(args.images) > 3:
        print("Warning: Maximum 3 images supported, using the first 3 only")
        args.images = args.images[:3]
    
    # Run the end-to-end test flow
    print("\n=== CUSTOM IMAGE VIDEO GENERATION TEST ===\n")
    print(f"Content: {args.content}")
    print(f"Images: {', '.join(args.images)}")
    print("")
    
    # Step 1: Upload images
    image_ids = upload_images(args.images)
    print(f"Image IDs: {image_ids}")
    print("")
    
    # Step 2: Generate video
    job_id = generate_video(image_ids, args.content)
    print("")
    
    # Step 3: Wait for completion
    wait_for_completion(job_id)

if __name__ == "__main__":
    main() 