import pytest
import os
from app.services.media.fetcher import media_fetcher
from app.services.media.audio import audio_generator
from app.services.video.status import redis_service
from google.cloud import storage

@pytest.mark.asyncio
async def test_unsplash_connection():
    """Test Unsplash API connection."""
    try:
        images = await media_fetcher.fetch_unsplash_images("test query", 1)
        assert len(images) > 0
        assert images[0].startswith('https://')
    except Exception as e:
        pytest.fail(f"Unsplash connection failed: {str(e)}")

@pytest.mark.asyncio
async def test_edge_tts():
    """Test Edge TTS audio generation."""
    try:
        audio_path = await audio_generator.generate_audio("Test audio generation")
        assert os.path.exists(audio_path)
        assert os.path.getsize(audio_path) > 0
    except Exception as e:
        pytest.fail(f"Edge TTS failed: {str(e)}")
    finally:
        audio_generator.cleanup()

@pytest.mark.asyncio
async def test_redis_connection():
    """Test Redis connection."""
    try:
        test_key = "test_key"
        test_value = {"test": "data"}
        success = await redis_service.create_job(test_key, test_value)
        assert success
        
        job_data = await redis_service.get_job_status(test_key)
        assert job_data is not None
        assert job_data.get("test") == "data"
        
        await redis_service.delete_job(test_key)
    except Exception as e:
        pytest.fail(f"Redis connection failed: {str(e)}")

def test_google_cloud_storage():
    """Test Google Cloud Storage connection."""
    try:
        client = storage.Client()
        bucket = client.bucket(os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET'))
        assert bucket.exists()
    except Exception as e:
        pytest.fail(f"Google Cloud Storage connection failed: {str(e)}") 