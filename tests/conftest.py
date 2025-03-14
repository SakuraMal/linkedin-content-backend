import pytest
from app import create_app
import os
import tempfile
from unittest.mock import AsyncMock, patch

@pytest.fixture
def app():
    """Create and configure a test app."""
    app = create_app({
        'TESTING': True,
        'REDIS_URL': 'redis://localhost:6379'
    })
    return app

@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()

@pytest.fixture
def sample_request_data():
    """Sample video generation request data."""
    return {
        "media": [
            {
                "type": "image",
                "url": "https://example.com/test1.jpg",
                "duration": 3.0
            }
        ],
        "audio": {
            "url": "https://example.com/test-audio.mp3"
        },
        "style": "professional"
    }

@pytest.fixture(autouse=True)
async def mock_media_operations():
    """Mock media operations to avoid actual HTTP requests and file operations."""
    # Create temporary files that will be "downloaded"
    temp_dir = tempfile.mkdtemp(prefix='test_video_')
    image_path = os.path.join(temp_dir, 'test_image.jpg')
    audio_path = os.path.join(temp_dir, 'test_audio.mp3')
    
    # Create empty files
    open(image_path, 'a').close()
    open(audio_path, 'a').close()
    
    with patch('app.services.media.fetcher.MediaFetcher.download_media_files') as mock_download:
        mock_download.return_value = AsyncMock(return_value={
            'images': [image_path],
            'audio': audio_path
        })()
        
        with patch('app.services.media.processor.MediaProcessor.create_video_segments') as mock_segments:
            mock_segments.return_value = []
            
            with patch('app.services.media.processor.MediaProcessor.combine_with_audio') as mock_combine:
                mock_combine.return_value = os.path.join(temp_dir, 'output.mp4')
                yield
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir) 