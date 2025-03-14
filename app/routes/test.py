from flask import Blueprint, jsonify
from flask_cors import cross_origin

test_bp = Blueprint('test', __name__)

@test_bp.route('/test-cors', methods=['POST', 'OPTIONS'])
@cross_origin()
def test_cors():
    """Simple endpoint to test CORS functionality."""
    return jsonify({
        "status": "success",
        "message": "CORS test successful",
        "data": {
            "received": True,
            "cors_enabled": True
        }
    }), 200 