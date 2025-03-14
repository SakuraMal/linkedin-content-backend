import os
import sys
import platform
import traceback
import logging
from datetime import datetime
from dotenv import load_dotenv
import redis

# Load environment variables from .env file
load_dotenv()

# Print available environment variables
print("Available environment variables:", list(os.environ.keys()))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

from app import create_app

# Create the Flask application
app = create_app(redis_client)

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting Flask app on port {port}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Redis URL: {redis_url}")
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=os.getenv('ENVIRONMENT') == 'development'
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)
