from flask import Blueprint, request, jsonify
from http import HTTPStatus
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError
from ..services.openai import OpenAIService
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
bp = Blueprint('post', __name__, url_prefix='/api/post')
openai_service = OpenAIService()

class PostGenerationRequest(BaseModel):
    theme: str = Field(..., min_length=1, max_length=100)
    tone: str = Field(..., min_length=1, max_length=50)
    targetAudience: str = Field(..., min_length=1, max_length=100)
    length: int = Field(..., gt=0, lt=2000)  # Character length
    includeVideo: bool = Field(default=False)

def validate_request_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Validate request data using Pydantic model."""
    try:
        PostGenerationRequest(**data)
        return True, {}
    except ValidationError as e:
        logger.error(f"Validation error: {e.errors()}")
        return False, {"errors": e.errors()}

@bp.route('/generate', methods=['POST'])
def generate_post():
    """
    Generate a LinkedIn post based on provided parameters.
    
    Expected request body:
    {
        "theme": "Leadership & Management",
        "tone": "Professional",
        "targetAudience": "General Business Professionals",
        "length": 500,
        "includeVideo": true
    }
    """
    try:
        # Get request data
        data = request.get_json()
        logger.info(f"Received request data: {data}")
        
        if not data:
            logger.error("No request data provided")
            return jsonify({
                "success": False,
                "error": "No request data provided"
            }), HTTPStatus.BAD_REQUEST

        # Validate request data
        is_valid, validation_errors = validate_request_data(data)
        if not is_valid:
            logger.error(f"Invalid request data: {validation_errors}")
            return jsonify({
                "success": False,
                "error": "Invalid request data",
                "details": validation_errors
            }), HTTPStatus.BAD_REQUEST

        # Generate post
        result = openai_service.generate_post(
            theme=data['theme'],
            tone=data['tone'],
            target_audience=data['targetAudience'],
            length=data['length'],
            include_video=data.get('includeVideo', False)
        )

        return jsonify(result), HTTPStatus.OK

    except Exception as e:
        logger.error(f"Error generating post: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR 