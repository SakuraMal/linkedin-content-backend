import os
import sys
import traceback
from flask import Flask, jsonify, send_from_directory, send_file, request
from flask_cors import CORS
import logging
from google.cloud import secretmanager, storage
import json
import firebase_admin
from firebase_admin import credentials, firestore
import tempfile
import gc
import platform
import requests
from datetime import datetime
import signal
import atexit

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    # Initialize Flask app with static files path
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.makedirs(static_folder, exist_ok=True)  # Ensure the directory exists
    logger.info(f"Static folder path: {static_folder}")

    app = Flask(__name__, 
               static_folder=static_folder,
               static_url_path='')

    # Configure CORS
    if os.environ.get('RENDER'):
        frontend_url = os.environ.get('FRONTEND_URL', 'https://paa-some-frontend.onrender.com')
        CORS(app, origins=[frontend_url])
        logger.info(f"CORS configured for frontend URL: {frontend_url}")
    else:
        CORS(app, origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','))
        logger.info("CORS configured for development (all origins allowed)")

    # Global flag for graceful shutdown
    app.config['IS_SHUTTING_DOWN'] = False

    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}. Starting graceful shutdown...")
        app.config['IS_SHUTTING_DOWN'] = True

    def cleanup():
        """Cleanup function to be called on shutdown"""
        logger.info("Performing cleanup before shutdown...")
        gc.collect()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)

    # Initialize system info flag
    app.config['SYSTEM_INFO_LOGGED'] = False

    @app.before_request
    def before_request():
        """Log system information on the first request"""
        if not app.config['SYSTEM_INFO_LOGGED']:
            log_system_info()
            app.config['SYSTEM_INFO_LOGGED'] = True

    @app.route('/health/live')
    def health_check_live():
        """Live health check endpoint for Fly.io"""
        try:
            if app.config['IS_SHUTTING_DOWN']:
                logger.warning("Health check called during shutdown")
                return jsonify({
                    "status": "shutting_down",
                    "message": "Server is shutting down"
                }), 503

            # Basic application check
            gc.collect()
            
            # Log the health check
            logger.info("Health check (live) endpoint called")
            
            return jsonify({
                "status": "healthy",
                "service": "linkedin-content-backend",
                "version": os.environ.get('VERSION', '1.0.0'),
                "timestamp": datetime.utcnow().isoformat(),
                "port": os.environ.get('PORT', '8080')
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 500

    @app.route('/health/ready')
    def health_check_ready():
        """Readiness check endpoint for Fly.io"""
        try:
            if app.config['IS_SHUTTING_DOWN']:
                logger.warning("Readiness check called during shutdown")
                return jsonify({
                    "status": "shutting_down",
                    "message": "Server is shutting down"
                }), 503

            # More comprehensive health check
            gc.collect()
            
            # Log the health check
            logger.info("Health check (ready) endpoint called")
            
            return jsonify({
                "status": "healthy",
                "service": "linkedin-content-backend",
                "version": os.environ.get('VERSION', '1.0.0'),
                "timestamp": datetime.utcnow().isoformat(),
                "port": os.environ.get('PORT', '8080')
            }), 200
        except Exception as e:
            logger.error(f"Readiness check failed: {str(e)}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e)
            }), 500

    return app

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting Flask app on port {port}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {platform.platform()}")
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)
