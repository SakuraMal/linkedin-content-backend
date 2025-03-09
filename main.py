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

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def log_system_info():
    """Log detailed system information"""
    info = {
        "Python Version": sys.version,
        "Platform": platform.platform(),
        "Working Directory": os.getcwd(),
        "Environment Variables": {k: v for k, v in os.environ.items() if 'secret' not in k.lower()},
        "Static Folder": os.path.abspath('static') if os.path.exists('static') else 'not found',
        "Directory Contents": os.listdir('.'),
        "Render Info": {
            "Is Render": os.environ.get('RENDER', False),
            "Service Name": os.environ.get('RENDER_SERVICE_NAME', 'unknown'),
            "External URL": os.environ.get('RENDER_EXTERNAL_URL', 'unknown'),
            "Git Branch": os.environ.get('RENDER_GIT_BRANCH', 'unknown'),
            "Git Commit": os.environ.get('RENDER_GIT_COMMIT', 'unknown'),
            "Port": os.environ.get('PORT', '8080')
        }
    }
    logger.info(f"System Information: {json.dumps(info, indent=2)}")
    return info

# Log startup information
logger.info("Starting application initialization...")
system_info = log_system_info()

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

# Initialize Firebase lazily only when needed
firebase_app = None
db = None

def get_firebase():
    global firebase_app, db
    if not firebase_app:
        try:
            # Try environment variable first
            creds_json = os.environ.get('GOOGLE_CREDENTIALS')
            if creds_json:
                firebase_creds = json.loads(creds_json)
                logger.info("Using Firebase credentials from environment")
            else:
                # Fallback to Secret Manager
                secret_client = secretmanager.SecretManagerServiceClient()
                secret_name = f"projects/paa-some/secrets/firebase-credentials/versions/latest"
                response = secret_client.access_secret_version(request={"name": secret_name})
                firebase_creds = json.loads(response.payload.data.decode("UTF-8"))
                logger.info("Using Firebase credentials from Secret Manager")
            
            cred = credentials.Certificate(firebase_creds)
            firebase_app = firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            logger.error(traceback.format_exc())
    return db

def handle_api_route(path):
    """Handle API routes"""
    logger.info(f"Handling API route: {path}")
    return jsonify({"error": "API endpoint not implemented"}), 501

@app.route('/debug')
def debug():
    """Debug endpoint to check configuration"""
    try:
        static_files = []
        if os.path.exists(app.static_folder):
            static_files = os.listdir(app.static_folder)
        
        debug_info = {
            "system_info": system_info,
            "static_folder": app.static_folder,
            "static_files": static_files,
            "python_path": sys.executable,
            "module_path": __file__,
            "working_directory": os.getcwd(),
        }
        return jsonify(debug_info)
    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

# Serve static files from Next.js
@app.route('/_next/<path:path>')
def next_static(path):
    logger.info(f"Serving Next.js static file: {path}")
    return send_from_directory(os.path.join(static_folder, '_next'), path)

# Serve public files
@app.route('/public/<path:path>')
def public_files(path):
    logger.info(f"Serving public file: {path}")
    return send_from_directory(static_folder, path)

# Handle all other routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    logger.info(f"Handling route: {path}")
    
    # Handle API routes
    if path.startswith('api/'):
        return handle_api_route(path)
    
    # Try to serve as a static file first
    try:
        if os.path.exists(os.path.join(static_folder, path)):
            return send_from_directory(static_folder, path)
    except Exception as e:
        logger.error(f"Error serving static file: {str(e)}")
    
    # Default to serving index.html for client-side routing
    try:
        return send_file(os.path.join(static_folder, 'index.html'))
    except Exception as e:
        logger.error(f"Error serving index.html: {str(e)}")
        return jsonify({"error": "Page not found"}), 404

@app.route('/health')
def health_check():
    """Health check endpoint"""
    gc.collect()
    static_files = []
    try:
        if os.path.exists(app.static_folder):
            static_files = os.listdir(app.static_folder)
    except Exception as e:
        logger.error(f"Error listing static files: {str(e)}")
    
    return jsonify({
        "status": "healthy",
        "version": "2024.03.08.8",
        "environment": os.environ.get('ENVIRONMENT', 'unknown'),
        "render": {
            "is_render": os.environ.get('RENDER', False),
            "external_url": os.environ.get('RENDER_EXTERNAL_URL', 'unknown'),
            "service_name": os.environ.get('RENDER_SERVICE_NAME', 'unknown')
        },
        "gcs_bucket": os.environ.get('GOOGLE_CLOUD_STORAGE_BUCKET', 'unknown'),
        "tier": "free",
        "static_folder": app.static_folder,
        "static_files": static_files,
        "port": os.environ.get('PORT', '8080'),
        "working_directory": os.getcwd()
    })

@app.route('/test-gcs')
def test_gcs():
    try:
        # Initialize the client
        storage_client = storage.Client()
        
        # Get the bucket
        bucket_name = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET', 'paa-some-videos')
        bucket = storage_client.bucket(bucket_name)
        
        # List objects in the bucket
        bucket_contents = []
        blobs = bucket.list_blobs(max_results=5)
        for blob in blobs:
            bucket_contents.append(blob.name)
            
        # Try to upload a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            temp.write("GCS Test")
            temp_path = temp.name
            
        test_blob = bucket.blob('test/gcs_test.txt')
        test_blob.upload_from_filename(temp_path)
        
        # Clean up
        os.unlink(temp_path)
        test_blob.delete()
        gc.collect()  # Run garbage collection after operations
        
        return jsonify({
            'status': 'success',
            'message': 'GCS connection and operations successful',
            'bucket_name': bucket_name,
            'bucket_contents': bucket_contents
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check_api():
    return jsonify({
        'status': 'healthy',
        'service': 'linkedin-content-backend',
        'version': '1.0.0'
    })

@app.route('/health/live')
def health_check_live():
    """Live health check endpoint for Fly.io"""
    return jsonify({
        "status": "healthy",
        "service": "linkedin-content-backend",
        "version": os.environ.get('VERSION', '1.0.0')
    })

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting Flask app on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)
