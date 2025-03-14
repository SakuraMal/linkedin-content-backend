import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Print loaded environment variables for debugging
print("Loaded environment variables:")
print(f"REDIS_URL: {os.getenv('REDIS_URL')}")
print(f"PORT: {os.getenv('PORT')}")

# Import and run the main application
from main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port) 