from flask import Flask, jsonify, request, send_from_directory
import os
import logging
from dotenv import load_dotenv
import redis
from .routes.video import bp as video_bp
from .routes.post import bp as post_bp
from .routes.stock_media import stock_media_bp

# DO NOT IMPORT FLASK-CORS - we'll handle CORS directly
# from flask_cors import CORS, cross_origin

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app(redis_client: redis.Redis = None, test_config=None):
    """Create and configure the app"""
    app = Flask(__name__, static_folder='../static')
    
    # CORS configuration for video generation architecture
    default_origins = 'http://localhost:3000,https://linkedin-content-frontend.vercel.app'
    allowed_origins = os.environ.get('CORS_ORIGINS', default_origins).split(',')
    logger.info(f"Configuring CORS with allowed origins: {allowed_origins}")

    # Add more verbose logging for CORS
    logger.debug("Setting up CORS with direct after_request handler")
    logger.debug(f"CORS parameters: allowed_origins={allowed_origins}")
    
    # Print each allowed origin for debugging
    for origin in allowed_origins:
        logger.debug(f"Allowed origin: '{origin}'")
    
    # Custom CORS handling without Flask-CORS
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        
        # Log request details for debugging
        logger.debug(f"Processing request: {request.method} {request.path}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Check if origin is present
        if origin:
            logger.debug(f"Request origin: '{origin}'")
            
            # Check if origin is allowed - use explicit string comparison
            is_allowed = False
            for allowed_origin in allowed_origins:
                # Trim any whitespace
                allowed_origin = allowed_origin.strip()
                logger.debug(f"Comparing '{origin}' with allowed origin '{allowed_origin}'")
                if origin == allowed_origin:
                    is_allowed = True
                    logger.debug(f"Origin match found: {origin} == {allowed_origin}")
                    break
            
            # If the origin is allowed, add CORS headers
            if is_allowed:
                logger.debug(f"Adding CORS headers for allowed origin: {origin}")
                
                # Standard CORS headers
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                
                # Add Vary header to signal that the response varies based on Origin
                response.headers['Vary'] = 'Origin'
                
                # For preflight requests
                if request.method == 'OPTIONS':
                    logger.debug("Handling OPTIONS request - adding preflight headers")
                    # Preflight requests don't need a body
                    return response
            else:
                logger.debug(f"Origin not allowed after comparison: '{origin}'")
        else:
            logger.debug("No Origin header in request")
                
        return response

    # No Flask-CORS middleware
    # No custom OPTIONS route handlers except the ones handled by after_request

    if test_config is None:
        app.config.from_mapping(
            SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
            REDIS_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379'),
            GOOGLE_CLOUD_PROJECT=os.environ.get('GOOGLE_CLOUD_PROJECT'),
            GOOGLE_CLOUD_STORAGE_BUCKET=os.environ.get('GOOGLE_CLOUD_STORAGE_BUCKET'),
            TESTING=False
        )
    else:
        app.config.update(test_config)

    # Store Redis client in app context
    app.redis_client = redis_client

    @app.route('/health', methods=['GET'])
    def health_check():
        try:
            # Check Redis connection
            app.redis_client.ping()
            return jsonify({
                "status": "healthy",
                "redis": "connected",
                "version": "1.0.0"
            }), 200
        except Exception as e:
            return jsonify({
                "status": "unhealthy",
                "redis": str(e),
                "version": "1.0.0"
            }), 500

    @app.route('/test')
    def test_page():
        return send_from_directory(app.static_folder, 'test.html')

    # Register blueprints
    app.register_blueprint(video_bp, url_prefix='/api/video')
    app.register_blueprint(post_bp, url_prefix='/api/post')
    app.register_blueprint(stock_media_bp)

    return app