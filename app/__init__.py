from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS, cross_origin
import os
import logging
from dotenv import load_dotenv
import redis
from .routes.video import bp as video_bp
from .routes.post import bp as post_bp

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app(redis_client: redis.Redis = None, test_config=None):
    """Create and configure the app"""
    app = Flask(__name__, static_folder='../static')
    
    # CORS configuration for video generation architecture
    allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
    CORS(app, 
         origins=allowed_origins,
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'OPTIONS'])

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

    return app