from flask import Blueprint, request, jsonify, current_app
from app.services.video.generator import VideoGenerator
from app.models.video import VideoRequest
from app.services.storage.file_validator import FileValidator
from app.services.storage.image_storage import image_storage_service
from app.models.image import ImageUploadResponse
import uuid
import logging
import json
from datetime import datetime, timedelta
import redis

bp = Blueprint('video', __name__)
video_generator = VideoGenerator()
file_validator = FileValidator()
logger = logging.getLogger(__name__)

def get_redis_client():
    """Get Redis client from Flask app context or create a new one."""
    if hasattr(current_app, 'redis_client'):
        return current_app.redis_client
    else:
        # Create a new Redis client if not available in app context
        redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        return redis.from_url(redis_url)

@bp.route('/test-setup', methods=['GET'])
def test_setup():
    """Test endpoint to verify Redis connection."""
    try:
        test_key = str(uuid.uuid4())
        current_app.redis_client.set(
            f"job:{test_key}:status",
            json.dumps({"status": "test", "timestamp": datetime.utcnow().isoformat()})
        )
        current_app.redis_client.delete(f"job:{test_key}:status")
        return jsonify({"status": "success", "message": "Redis connection successful"}), 200
    except Exception as e:
        logging.error(f"Error in test setup: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/upload-images', methods=['POST'])
def upload_images():
    """Upload images for video generation."""
    try:
        # Check if files were provided
        if 'images' not in request.files:
            return jsonify({"error": "No images provided"}), 400
            
        # Get files from request
        files = request.files.getlist('images')
        if not files or len(files) == 0:
            return jsonify({"error": "No images provided"}), 400
            
        # Get user ID from request (optional)
        user_id = request.form.get('user_id', None)
        
        # Validate files
        file_validator = FileValidator(
            max_files=3,  # Maximum 3 images
            max_file_size=2 * 1024 * 1024,  # 2MB per image
            allowed_types=['image/jpeg', 'image/png', 'image/jpg']
        )
        
        is_valid, validation_result = file_validator.validate_files(files)
        if not is_valid:
            logging.warning(f"File validation failed: {validation_result}")
            return jsonify({"error": validation_result["error"]}), 400
            
        # Upload images to Google Cloud Storage
        uploaded_images = image_storage_service.upload_images(files, user_id)
        if not uploaded_images:
            return jsonify({"error": "Failed to upload images"}), 500
            
        # Extract image IDs
        image_ids = [image["id"] for image in uploaded_images]
        
        return jsonify({
            "success": True,
            "message": f"Successfully uploaded {len(uploaded_images)} images",
            "images": uploaded_images,
            "image_ids": image_ids
        })
        
    except Exception as e:
        logging.error(f"Error uploading images: {str(e)}")
        return jsonify({"error": f"Error uploading images: {str(e)}"}), 500

@bp.route('/generate', methods=['POST'])
def generate_video():
    """Generate a video from content description."""
    try:
        # Parse request data
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "No request data provided"}), 400
            
        # Log the request
        logging.info(f"Received video generation request: {json.dumps(request_data)}")
        
        # Validate request using Pydantic model
        try:
            video_request = VideoRequest(**request_data)
        except Exception as e:
            logging.error(f"Invalid request data: {str(e)}")
            return jsonify({"error": f"Invalid request data: {str(e)}"}), 400
            
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Store job status in Redis
        redis_client = get_redis_client()
        job_status = {
            "id": job_id,
            "status": "queued",
            "step": 0,
            "step_message": "Job queued",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        redis_client.set(f"job:{job_id}:status", json.dumps(job_status))
        
        # Start video generation in background
        import threading
        thread = threading.Thread(
            target=video_generator.process_video_job,
            args=(job_id, video_request, redis_client)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "status": "queued",
            "message": "Video generation started"
        })
        
    except Exception as e:
        logging.error(f"Error generating video: {str(e)}")
        return jsonify({"error": f"Error generating video: {str(e)}"}), 500

@bp.route('/status/<job_id>', methods=['GET'])
def get_video_status(job_id: str):
    """Get the status of a video generation job."""
    try:
        job_data = current_app.redis_client.get(f"job:{job_id}:status")
        if not job_data:
            return jsonify({"status": "error", "message": "Job not found"}), 404
            
        job_info = json.loads(job_data)
        return jsonify({
            "status": "success",
            "data": {
                "status": job_info["status"],
                "progress": job_info.get("progress", 0),
                "video_url": job_info.get("video_url"),
                "created_at": job_info["created_at"],
                "updated_at": job_info["updated_at"],
                "error": job_info.get("error")
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error getting job status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500 