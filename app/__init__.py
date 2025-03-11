from flask import Flask
from flask_cors import CORS
from .routes.post import post_routes

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "https://linkedin-content-frontend.vercel.app"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Register blueprints
    app.register_blueprint(post_routes, url_prefix='/api/post')
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        return {"status": "healthy"}, 200
    
    return app 