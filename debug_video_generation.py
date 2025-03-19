#!/usr/bin/env python3

"""
Debug script for video generation with custom images

This script helps diagnose issues with the video generation process,
particularly when using custom uploaded images.

Usage:
    python debug_video_generation.py --job_id <job_id>
    python debug_video_generation.py --last_jobs <number>
"""

import argparse
import json
import os
import sys
import redis
from datetime import datetime

# Configure Redis connection
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL)

def get_job_status(job_id):
    """Get detailed status for a specific job."""
    try:
        job_data = redis_client.get(f"job:{job_id}:status")
        if not job_data:
            print(f"No job data found for job ID: {job_id}")
            return None
        
        return json.loads(job_data)
    except Exception as e:
        print(f"Error retrieving job status: {e}")
        return None

def get_recent_jobs(count=5):
    """Get the most recent jobs from Redis."""
    try:
        # Get all job keys
        job_keys = redis_client.keys("job:*:status")
        
        # Get data for each job
        jobs = []
        for key in job_keys:
            job_data = redis_client.get(key)
            if job_data:
                job_info = json.loads(job_data)
                jobs.append(job_info)
        
        # Sort by creation date (newest first)
        sorted_jobs = sorted(
            jobs, 
            key=lambda x: datetime.fromisoformat(x.get('created_at', '1970-01-01T00:00:00')), 
            reverse=True
        )
        
        # Return the requested number of jobs
        return sorted_jobs[:count]
    except Exception as e:
        print(f"Error retrieving recent jobs: {e}")
        return []

def display_job_info(job_info):
    """Pretty print job information."""
    if not job_info:
        return
    
    print("\n" + "="*50)
    print(f"Job ID: {job_info.get('id', 'Unknown')}")
    print(f"Status: {job_info.get('status', 'Unknown')}")
    
    if job_info.get('error'):
        print(f"\nERROR: {job_info['error']}")
    
    print(f"\nProgress: {job_info.get('progress', 0)}%")
    print(f"Step: {job_info.get('step', 0)} - {job_info.get('step_message', 'Unknown')}")
    
    if job_info.get('video_url'):
        print(f"\nVideo URL: {job_info['video_url']}")
    
    print(f"\nCreated: {job_info.get('created_at', 'Unknown')}")
    print(f"Updated: {job_info.get('updated_at', 'Unknown')}")
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description='Debug video generation jobs')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--job_id', help='Specific job ID to check')
    group.add_argument('--last_jobs', type=int, help='Number of recent jobs to display')
    
    args = parser.parse_args()
    
    if args.job_id:
        job_info = get_job_status(args.job_id)
        if job_info:
            display_job_info(job_info)
        else:
            print(f"No data found for job ID: {args.job_id}")
    elif args.last_jobs:
        recent_jobs = get_recent_jobs(args.last_jobs)
        if recent_jobs:
            print(f"Displaying {len(recent_jobs)} most recent jobs:")
            for job in recent_jobs:
                display_job_info(job)
        else:
            print("No recent jobs found")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 