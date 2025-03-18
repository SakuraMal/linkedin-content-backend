import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import sys

# Set environment variables for testing
os.environ['TESTING'] = 'True'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['GOOGLE_CLOUD_STORAGE_BUCKET'] = 'test-bucket'
os.environ['OPENAI_API_KEY'] = 'test-openai-key'
os.environ['PEXELS_API_KEY'] = 'test-pexels-key'
os.environ['UNSPLASH_ACCESS_KEY'] = 'test-unsplash-key'

# Mock the magic module
sys.modules['magic'] = MagicMock()
sys.modules['magic'].from_buffer = MagicMock(return_value='image/jpeg')

# Create a mock for PexelsFetcher
class MockPexelsFetcher:
    def __init__(self):
        pass
    
    def fetch_relevant_videos(self, keywords, count=1):
        return []

# Add the mock to sys.modules to prevent the real module from being imported
sys.modules['app.services.media.pexels_fetcher'] = MagicMock()
sys.modules['app.services.media.pexels_fetcher'].pexels_fetcher = MockPexelsFetcher()
sys.modules['app.services.media.pexels_fetcher'].PexelsFetcher = MockPexelsFetcher

# Now import the app
from app import create_app

@pytest.fixture
def app():
    """Create and configure a test app."""
    app = create_app({
        'TESTING': True,
        'REDIS_URL': 'redis://localhost:6379/0'
    })
    
    # Apply global mocks for external services
    with patch('app.services.video.storage.StorageService') as mock_storage, \
         patch('app.services.storage.image_storage.ImageStorageService') as mock_image_storage, \
         patch('app.services.media.fetcher.MediaFetcher') as mock_media_fetcher, \
         patch('openai.OpenAI') as mock_openai, \
         patch('redis.Redis') as mock_redis, \
         patch('app.services.media.fetcher.MediaFetcher.fetch_unsplash_images') as mock_unsplash, \
         patch('app.routes.video.get_redis_client') as mock_get_redis:
        
        # Configure mock storage service
        mock_storage_instance = MagicMock()
        mock_storage_instance.upload_video.return_value = "https://storage.example.com/test-video.mp4"
        mock_storage.return_value = mock_storage_instance
        
        # Configure mock image storage service
        mock_image_storage_instance = MagicMock()
        mock_image_storage_instance.upload_images.return_value = [
            {
                "id": "test-image-id-1",
                "filename": "test1.jpg",
                "storage_path": "user_uploads/images/test/test-image-id-1.jpg",
                "url": "https://storage.example.com/test-image-id-1.jpg",
                "content_type": "image/jpeg"
            }
        ]
        mock_image_storage_instance.get_image_url.return_value = "https://storage.example.com/test-image.jpg"
        mock_image_storage.return_value = mock_image_storage_instance
        
        # Configure mock media fetcher
        mock_media_fetcher_instance = MagicMock()
        mock_media_fetcher_instance.fetch_media.return_value = {
            'images': ['/tmp/test_image.jpg'],
            'videos': []
        }
        mock_media_fetcher_instance.download_file.return_value = '/tmp/test_downloaded_file.jpg'
        mock_media_fetcher.return_value = mock_media_fetcher_instance
        
        # Configure mock Unsplash
        mock_unsplash.return_value = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
        
        # Configure mock OpenAI
        mock_openai_instance = MagicMock()
        mock_openai_completion = MagicMock()
        mock_openai_completion.choices = [MagicMock(message=MagicMock(content='{"image_ratio": 0.7, "video_ratio": 0.3}'))]
        mock_openai_instance.chat.completions.create.return_value = mock_openai_completion
        mock_openai.return_value = mock_openai_instance
        
        # Configure mock Redis
        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = '{"status": "queued", "progress": 0}'
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        # Configure mock get_redis_client
        mock_get_redis.return_value = mock_redis_instance
        
        yield app

@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()

@pytest.fixture
def sample_request_data():
    """Sample video generation request data."""
    return {
        "content": "Test content for video generation",
        "style": "professional",
        "duration": 15,
        "voice": "en-US-Neural2-F"
    }

@pytest.fixture
def sample_request_with_images():
    """Sample video generation request data with user images."""
    return {
        "content": "Test content for video generation with custom images",
        "style": "professional",
        "duration": 15,
        "voice": "en-US-Neural2-F",
        "user_image_ids": ["test-image-id-1", "test-image-id-2"]
    }

@pytest.fixture
def mock_temp_files():
    """Create temporary files for testing."""
    temp_dir = tempfile.mkdtemp(prefix='test_video_')
    image_path = os.path.join(temp_dir, 'test_image.jpg')
    audio_path = os.path.join(temp_dir, 'test_audio.mp3')
    video_path = os.path.join(temp_dir, 'test_video.mp4')
    
    # Create empty files
    open(image_path, 'a').close()
    open(audio_path, 'a').close()
    open(video_path, 'a').close()
    
    yield {
        'temp_dir': temp_dir,
        'image_path': image_path,
        'audio_path': audio_path,
        'video_path': video_path
    }
    
    # Clean up
    try:
        os.remove(image_path)
        os.remove(audio_path)
        os.remove(video_path)
        os.rmdir(temp_dir)
    except:
        pass 