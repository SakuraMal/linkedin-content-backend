from flask import Blueprint, request, jsonify, current_app
from app.services.video.generator import VideoGenerator
from app.models.video import VideoRequest
import uuid
import logging
import json
from datetime import datetime, timedelta

bp = Blueprint('video', __name__)
video_generator = VideoGenerator()

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

@bp.route('/generate', methods=['POST'])
def generate_video():
    """Generate a video based on the provided content description."""
    try:
        data = request.get_json()
        video_request = VideoRequest(**data)
        job_id = str(uuid.uuid4())
        
        # Log the request
        logging.info(f"Received video generation request: {video_request.model_dump()}")
        
        # Store initial job status
        job_data = {
            "status": "queued",
            "progress": 0,
            "request": video_request.model_dump(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Set job data with 24-hour expiration
        current_app.redis_client.set(
            f"job:{job_id}:status",
            json.dumps(job_data),
            ex=int(timedelta(hours=24).total_seconds())
        )
        
        # Start video generation process in background
        video_generator.process_video_job(job_id, video_request, current_app.redis_client)
        
        return jsonify({
            "status": "success",
            "data": {
                "job_id": job_id,
                "status": "queued",
                "estimated_duration": video_request.duration
            }
        }), 202
        
    except Exception as e:
        logging.error(f"Error in video generation: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 400

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