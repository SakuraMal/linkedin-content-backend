from flask import Blueprint, request, jsonify
from http import HTTPStatus
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError
from ..services.openai import OpenAIService

# Create Blueprint
bp = Blueprint('post', __name__)
openai_service = OpenAIService()

class PostGenerationRequest(BaseModel):
    theme: str = Field(..., min_length=1, max_length=100)
    tone: str = Field(..., min_length=1, max_length=50)
    length: str = Field(..., min_length=1, max_length=50)

def validate_request_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Validate request data using Pydantic model."""
    try:
        PostGenerationRequest(**data)
        return True, {}
    except ValidationError as e:
        return False, {"errors": e.errors()}

@bp.route('/generate', methods=['POST'])
def generate_post():
    """
    Generate a LinkedIn post based on provided parameters.
    
    Expected request body:
    {
        "theme": "Leadership & Management",
        "tone": "Professional",
        "length": "Medium (500-1000 characters)"
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No request data provided"
            }), HTTPStatus.BAD_REQUEST

        # Validate request data
        is_valid, validation_errors = validate_request_data(data)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": "Invalid request data",
                "details": validation_errors
            }), HTTPStatus.BAD_REQUEST

        # Generate post
        result = openai_service.generate_post(
            theme=data['theme'],
            tone=data['tone'],
            length=data['length']
        )

        return jsonify(result), HTTPStatus.OK

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR 