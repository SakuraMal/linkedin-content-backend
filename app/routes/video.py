from flask import Blueprint, request, jsonify, current_app
from ..services.video import VideoGenerator
from ..models import VideoRequest, ImageUploadResponse
from ..services.storage import FileValidator, image_storage_service
import uuid
import logging
import json
from datetime import datetime, timedelta
import redis
import traceback
import sentry_sdk

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
        
        # Add context to Sentry
        sentry_sdk.set_context("video_generation", {
            "content_length": len(request_data.get("content", "")),
            "user_image_count": len(request_data.get("user_image_ids", [])) if request_data.get("user_image_ids") else 0,
            "has_content_analysis": "content_analysis" in request_data
        })
        
        # Add breadcrumb for request validation
        sentry_sdk.add_breadcrumb(
            category="video_generation",
            message="Validating video generation request",
            level="info"
        )
        
        # Check for required fields
        if not request_data.get("content"):
            return jsonify({"error": "Content field is required"}), 400
            
        # Check if user_image_ids is provided but empty
        if "user_image_ids" in request_data and not request_data["user_image_ids"]:
            logging.warning("user_image_ids field is present but empty - will use API-generated images")
            
        # Check if user_image_ids contains valid IDs
        if request_data.get("user_image_ids"):
            logging.info(f"Video request includes {len(request_data['user_image_ids'])} custom images")
            
        # Handle possible field mapping issues for backward compatibility
        try:
            # Ensure the request data conforms to the VideoRequest model
            # The model expects certain fields like audioPreferences but frontend might send audio_preferences
            request_data_normalized = {}
            
            # Direct field mappings
            for key in ["content", "style", "duration", "voice", "user_image_ids", "theme"]:
                if key in request_data:
                    request_data_normalized[key] = request_data[key]
            
            # Handle nested structures and camelCase vs snake_case issues
            if "audioPreferences" in request_data:
                request_data_normalized["audioPreferences"] = request_data["audioPreferences"]
            elif "audio_preferences" in request_data:
                request_data_normalized["audioPreferences"] = request_data["audio_preferences"]
                
            if "transitionPreferences" in request_data:
                request_data_normalized["transitionPreferences"] = request_data["transitionPreferences"]
            elif "transition_preferences" in request_data:
                request_data_normalized["transitionPreferences"] = request_data["transition_preferences"]
                
            # Handle content_analysis field which might use different structures
            if "content_analysis" in request_data:
                # Store original content analysis in Sentry for debugging
                sentry_sdk.add_breadcrumb(
                    category="video_generation",
                    message="Processing content_analysis from request",
                    level="info",
                    data={"content_analysis": request_data["content_analysis"]}
                )
            
            sentry_sdk.add_breadcrumb(
                category="video_generation",
                message="Request data normalized",
                level="info",
                data={"normalized_data": request_data_normalized}
            )
            
            # Validate request using Pydantic model
            video_request = VideoRequest(**request_data_normalized)
            
        except Exception as e:
            logging.error(f"Invalid request data: {str(e)}")
            sentry_sdk.capture_exception(e)
            
            # Add detailed error context
            sentry_sdk.set_context("validation_error", {
                "error": str(e),
                "trace": traceback.format_exc(),
                "request_data": request_data
            })
            
            return jsonify({
                "error": f"Invalid request data: {str(e)}", 
                "details": str(e)
            }), 400
            
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
        
        # Log job creation
        logging.info(f"Created video generation job {job_id}, mode: {'custom images' if request_data.get('user_image_ids') else 'auto images'}")
        
        # Add breadcrumb for job creation
        sentry_sdk.add_breadcrumb(
            category="video_generation",
            message=f"Video generation job created with ID: {job_id}",
            level="info"
        )
        
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
        logging.error(traceback.format_exc())
        
        # Capture exception in Sentry
        sentry_sdk.capture_exception(e)
        
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

@bp.route('/cors-test', methods=['GET', 'OPTIONS'])
def cors_test():
    """Test endpoint for CORS configuration"""
    from flask import request, jsonify, current_app
    
    # Log request details for debugging
    current_app.logger.debug(f"CORS test request received")
    current_app.logger.debug(f"Request headers: {dict(request.headers)}")
    current_app.logger.debug(f"Request method: {request.method}")
    
    # If this is an OPTIONS request, it will be handled by Flask-CORS
    # Just return a successful response for GET
    if request.method == 'GET':
        response = jsonify({
            "success": True,
            "message": "CORS is configured correctly if you can see this message",
            "request_headers": dict(request.headers),
            "cors_settings": {
                "allowed_origins": current_app.config.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
            }
        })
        
        # Explicitly add CORS headers for debugging
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        
        return response
    
    # OPTIONS requests are handled by Flask-CORS, but add a fallback
    return "", 204 