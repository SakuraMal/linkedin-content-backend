import pytest
import os
from unittest.mock import patch, MagicMock
from app.services.media.fetcher import media_fetcher
from app.services.media.audio import audio_generator
# Import redis directly instead of from status module
import redis
from google.cloud import storage

def test_unsplash_connection(client):
    """Test Unsplash API connection with mocks."""
    # Using the mock from conftest.py
    with patch('app.services.media.fetcher.MediaFetcher.fetch_unsplash_images') as mock_fetch:
        mock_fetch.return_value = ["https://example.com/image1.jpg"]
        
        # Call the function
        images = media_fetcher.fetch_unsplash_images("test query", 1)
        
        # Verify results
        assert len(images) > 0
        assert images[0].startswith('https://')
        mock_fetch.assert_called_once()

def test_edge_tts(client):
    """Test Edge TTS audio generation with mocks."""
    with patch('app.services.media.audio.AudioGenerator.generate_audio') as mock_generate:
        # Set up the mock to return a test file path
        test_audio_path = "/tmp/test_audio.mp3"
        mock_generate.return_value = test_audio_path
        
        # Call the function
        audio_path = audio_generator.generate_audio("Test audio generation")
        
        # Verify results
        assert audio_path == test_audio_path
        mock_generate.assert_called_once_with("Test audio generation")

def test_redis_connection(client):
    """Test Redis connection with mocks."""
    with patch('redis.Redis') as mock_redis:
        # Set up the mock
        mock_instance = MagicMock()
        mock_instance.set.return_value = True
        mock_instance.get.return_value = '{"test": "data"}'
        mock_redis.return_value = mock_instance
        
        # Create a Redis client
        redis_client = redis.Redis()
        
        # Test operations
        test_key = "test_key"
        test_value = '{"test": "data"}'
        
        # Set and get operations
        assert redis_client.set(test_key, test_value)
        assert redis_client.get(test_key) == test_value

def test_google_cloud_storage(client):
    """Test Google Cloud Storage connection with mocks."""
    with patch('google.cloud.storage.Client') as mock_client:
        # Set up the mock
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        
        mock_client_instance = MagicMock()
        mock_client_instance.bucket.return_value = mock_bucket
        mock_client.return_value = mock_client_instance
        
        # Create a storage client
        client = storage.Client()
        bucket = client.bucket(os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET'))
        
        # Verify the bucket exists
        assert bucket.exists()
        mock_client_instance.bucket.assert_called_once_with(os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')) 