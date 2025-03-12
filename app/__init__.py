from flask import Flask
from flask_cors import CORS
from .routes.post import post_routes
from .routes.video import video_routes

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "https://linkedin-content-frontend.vercel.app"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # Register blueprints
    app.register_blueprint(post_routes, url_prefix='/api/post')
    app.register_blueprint(video_routes, url_prefix='/api/video')
    
    # Health check endpoint
    @app.route('/health/live', methods=['GET'])
    def health_check():
        return {"status": "healthy"}, 200
    
    return app 