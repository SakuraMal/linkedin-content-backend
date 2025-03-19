from flask import Blueprint, request, jsonify
from http import HTTPStatus
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError
from ..services.openai import OpenAIService
import logging
import sentry_sdk
import traceback

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

class ContentAnalysisRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

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

@bp.route('/analyze-content', methods=['POST'])
def analyze_content():
    """
    Analyze content to extract keywords, sentiment, and other useful metadata.
    
    Expected request body:
    {
        "content": "Your content to analyze"
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "keywords": ["keyword1", "keyword2", ...],
            "sentiment": "positive|negative|neutral",
            "entities": [...],
            "topics": [...]
        }
    }
    """
    try:
        # Add more context to Sentry for this request
        sentry_sdk.set_context("endpoint", {"name": "analyze-content"})
        
        # Get request data
        data = request.get_json()
        logger.info(f"Received content analysis request")
        
        if not data:
            logger.error("No request data provided")
            return jsonify({
                "success": False,
                "error": "No request data provided"
            }), HTTPStatus.BAD_REQUEST

        # Add breadcrumb for request validation
        sentry_sdk.add_breadcrumb(
            category="request",
            message="Validating content analysis request",
            level="info"
        )
        
        # Validate request data
        try:
            analysis_request = ContentAnalysisRequest(**data)
        except ValidationError as e:
            logger.error(f"Invalid request data: {e.errors()}")
            sentry_sdk.capture_message("Content analysis validation error")
            return jsonify({
                "success": False,
                "error": "Invalid request data",
                "details": e.errors()
            }), HTTPStatus.BAD_REQUEST

        # Add context about the content being analyzed
        content_length = len(analysis_request.content)
        sentry_sdk.set_context("content", {
            "length": content_length,
            "sample": analysis_request.content[:100] + "..." if content_length > 100 else analysis_request.content
        })
        
        # Add breadcrumb before calling analyze_content
        sentry_sdk.add_breadcrumb(
            category="analysis",
            message="Calling OpenAI service analyze_content method",
            level="info"
        )
        
        # Analyze content
        try:
            result = openai_service.analyze_content(
                content=analysis_request.content
            )
            
            # Add breadcrumb for successful analysis
            sentry_sdk.add_breadcrumb(
                category="analysis",
                message="Content analysis completed successfully",
                level="info"
            )
            
            return jsonify(result), HTTPStatus.OK
            
        except Exception as analysis_error:
            # Capture specific exception for content analysis
            logger.error(f"Error in content analysis: {str(analysis_error)}")
            logger.error(traceback.format_exc())
            
            # Set error context for Sentry
            sentry_sdk.set_context("error_details", {
                "type": type(analysis_error).__name__,
                "message": str(analysis_error),
                "trace": traceback.format_exc()
            })
            
            # Capture the exception with Sentry
            sentry_sdk.capture_exception(analysis_error)
            
            return jsonify({
                "success": False,
                "error": f"Content analysis error: {str(analysis_error)}"
            }), HTTPStatus.INTERNAL_SERVER_ERROR

    except Exception as e:
        # Capture any other unexpected exceptions
        logger.error(f"Unexpected error analyzing content: {str(e)}")
        logger.error(traceback.format_exc())
        
        sentry_sdk.capture_exception(e)
        
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), HTTPStatus.INTERNAL_SERVER_ERROR 