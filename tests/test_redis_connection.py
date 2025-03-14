import os
import redis
from dotenv import load_dotenv
from urllib.parse import urlparse

def test_redis_connection():
    # Load environment variables
    load_dotenv('.env.test')
    
    # Get Redis URL from environment
    redis_url = os.getenv('REDIS_URL')
    parsed_url = urlparse(redis_url)
    
    print(f"Testing connection to Redis...")
    
    try:
        # Create Redis client
        r = redis.Redis(
            host=parsed_url.hostname,
            port=parsed_url.port or 6379,
            password=parsed_url.password,
            ssl=True,
            ssl_cert_reqs=None,
            decode_responses=True
        )
        
        # Test connection with ping
        response = r.ping()
        print(f"Redis connection successful! Ping response: {response}")
        
        # Test basic operations
        test_key = "test_key"
        test_value = "test_value"
        
        # Set a value
        r.set(test_key, test_value)
        print(f"Successfully set test value")
        
        # Get the value
        retrieved_value = r.get(test_key)
        print(f"Successfully retrieved test value: {retrieved_value}")
        
        # Clean up
        r.delete(test_key)
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error connecting to Redis: {str(e)}")
        raise

if __name__ == "__main__":
    test_redis_connection() 