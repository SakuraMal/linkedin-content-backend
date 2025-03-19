#!/usr/bin/env python3

import requests
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_cors_headers():
    """
    Test CORS headers for the backend API.
    This helps verify if the API is properly configured to accept cross-origin requests.
    """
    try:
        # Test the health endpoint with OPTIONS request
        api_url = "https://linkedin-content-backend.fly.dev/health"
        logger.info(f"Testing CORS headers for: {api_url}")
        
        # Send OPTIONS request with origin header
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        response = requests.options(api_url, headers=headers)
        
        # Log response headers
        logger.info(f"Response status: {response.status_code}")
        for header, value in response.headers.items():
            logger.info(f"{header}: {value}")
        
        # Check if CORS headers are present
        if 'Access-Control-Allow-Origin' in response.headers:
            logger.info("✅ CORS is correctly configured for the API")
            return True
        else:
            logger.error("❌ CORS headers are missing from the API response")
            return False
    
    except Exception as e:
        logger.error(f"Error testing CORS headers: {str(e)}")
        return False

def suggest_cors_fixes():
    """
    Provide suggestions to fix CORS issues in the backend.
    """
    logger.info("\n=== CORS FIX SUGGESTIONS ===")
    logger.info("1. Update the CORS configuration in app/__init__.py:")
    logger.info("""
    # Fix 1: Use CORS with resources instead of origins
    CORS(app, resources={r"/*": {"origins": allowed_origins}},
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'OPTIONS'])
    """)
    
    logger.info("\n2. Add CORS decorator to the video status route in app/routes/video.py:")
    logger.info("""
    @bp.route('/status/<job_id>', methods=['GET', 'OPTIONS'])
    @cross_origin()  # Add this decorator
    def get_video_status(job_id: str):
        # existing code...
    """)
    
    logger.info("\n3. Add these environment variables to your fly.toml config:")
    logger.info("""
    [env]
      CORS_ORIGINS = "http://localhost:3000,https://linkedin-content-frontend.vercel.app"
    """)
    
    logger.info("\n4. Update the frontend to add mode:'cors' to fetch requests:")
    logger.info("""
    const response = await fetch(
      `https://linkedin-content-backend.fly.dev/api/video/status/${jobId}`,
      {
        mode: 'cors',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    """)

if __name__ == "__main__":
    logger.info("Starting CORS header test for backend API")
    test_result = test_cors_headers()
    
    if not test_result:
        suggest_cors_fixes()
    
    logger.info("\nCORS test completed") 