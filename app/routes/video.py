from flask import Blueprint, jsonify, request
import os
from datetime import datetime
from typing import Optional
import uuid
import json
import redis
from urllib.parse import urlparse

video_routes = Blueprint('video', __name__)

# Initialize Redis client
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
parsed_url = urlparse(redis_url)
redis_client = redis.Redis(
    host=parsed_url.hostname or 'localhost',
    port=parsed_url.port or 6379,
    password=parsed_url.password,
    ssl=parsed_url.scheme == 'rediss',
    decode_responses=True
)

def validate_video_request(data: dict) -> tuple[bool, Optional[str]]:
    """Validate the video generation request data."""
    required_fields = ['content', 'style', 'duration']
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate style
    valid_styles = ['professional', 'casual', 'dynamic']
    if data['style'] not in valid_styles:
        return False, f"Invalid style. Must be one of: {', '.join(valid_styles)}"
    
    # Validate duration
    try:
        duration = int(data['duration'])
        if not (10 <= duration <= 300):
            return False, "Duration must be between 10 and 300 seconds"
    except (ValueError, TypeError):
        return False, "Duration must be a number"
    
    return True, None

@video_routes.route('/test-setup', methods=['GET'])
def test_video_setup():
    """Test endpoint to verify video generation setup."""
    try:
        # Test Redis connection
        redis_client.ping()
        redis_status = "connected"
    except redis.ConnectionError:
        redis_status = "disconnected"

    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'video-generation',
        'environment': os.getenv('FLASK_ENV', 'development'),
        'redis_status': redis_status
    })

@video_routes.route('/generate', methods=['POST'])
def generate_video():
    """Generate a video based on the provided content and parameters."""
    data = request.get_json()
    
    # Validate request
    is_valid, error_message = validate_video_request(data)
    if not is_valid:
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 400
    
    # Generate a unique ID for this video generation request
    generation_id = str(uuid.uuid4())
    
    # Store job information in Redis
    job_data = {
        'content': data['content'],
        'style': data['style'],
        'duration': data['duration'],
        'status': 'queued',
        'progress': 0,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'error': None
    }
    
    # Store in Redis with 24-hour expiration
    redis_client.setex(
        f'video_job:{generation_id}',
        86400,  # 24 hours in seconds
        json.dumps(job_data)
    )
    
    return jsonify({
        'status': 'success',
        'message': 'Video generation initiated',
        'data': {
            'generation_id': generation_id,
            'estimated_duration': data['duration'],
            'status': 'queued',
            'content_preview': data['content'][:100] + '...' if len(data['content']) > 100 else data['content'],
            'style': data['style'],
            'created_at': job_data['created_at']
        }
    }), 202

@video_routes.route('/status/<generation_id>', methods=['GET'])
def get_video_status(generation_id):
    """Get the status of a video generation job."""
    # Get job data from Redis
    job_data = redis_client.get(f'video_job:{generation_id}')
    
    if not job_data:
        return jsonify({
            'status': 'error',
            'message': 'Video generation job not found'
        }), 404
    
    job = json.loads(job_data)
    
    # For demo purposes, simulate progress
    if job['status'] == 'queued':
        job['status'] = 'processing'
        job['progress'] = 10
    elif job['status'] == 'processing' and job['progress'] < 100:
        job['progress'] += 20
        if job['progress'] >= 100:
            job['status'] = 'completed'
            job['progress'] = 100
    
    job['updated_at'] = datetime.now().isoformat()
    
    # Update job in Redis
    redis_client.setex(
        f'video_job:{generation_id}',
        86400,  # 24 hours in seconds
        json.dumps(job)
    )
    
    return jsonify({
        'status': 'success',
        'data': {
            'generation_id': generation_id,
            'status': job['status'],
            'progress': job['progress'],
            'style': job['style'],
            'created_at': job['created_at'],
            'updated_at': job['updated_at'],
            'error': job['error']
        }
    }) 