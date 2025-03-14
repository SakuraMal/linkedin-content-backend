import pytest
from app.models.video import VideoRequest

@pytest.mark.asyncio
async def test_video_generation_endpoint(client, sample_request_data):
    """Test the video generation endpoint."""
    response = await client.post('/api/video/generate',
                               json=sample_request_data)
    assert response.status_code == 202
    data = await response.get_json()
    assert data["status"] == "success"
    assert "job_id" in data["data"]
    assert "estimated_duration" in data["data"]

@pytest.mark.asyncio
async def test_video_status_endpoint(client, sample_request_data):
    """Test the video status endpoint."""
    # First create a job
    response = await client.post('/api/video/generate',
                               json=sample_request_data)
    assert response.status_code == 202
    data = await response.get_json()
    job_id = data["data"]["job_id"]

    # Then check its status
    response = await client.get(f'/api/video/status/{job_id}')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "success"
    assert "status" in data["data"]
    assert "progress" in data["data"]

@pytest.mark.asyncio
async def test_video_generation_process(client, sample_request_data):
    """Test the complete video generation process."""
    # Create a job
    response = await client.post('/api/video/generate',
                               json=sample_request_data)
    assert response.status_code == 202
    data = await response.get_json()
    job_id = data["data"]["job_id"]

    # Check initial status
    response = await client.get(f'/api/video/status/{job_id}')
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "success"
    assert data["data"]["status"] in ["queued", "downloading", "processing", "finalizing", "completed", "failed"]

@pytest.mark.asyncio
async def test_invalid_request(client):
    """Test video generation with invalid request data."""
    # Missing required fields
    response = await client.post('/api/video/generate',
                               json={})
    assert response.status_code == 400
    data = await response.get_json()
    assert data["status"] == "error"

    # Invalid media type
    invalid_data = {
        "media": [
            {
                "type": "invalid",
                "url": "https://example.com/test1.jpg",
                "duration": 3.0
            }
        ],
        "audio": {
            "url": "https://example.com/test-audio.mp3"
        },
        "style": "professional"
    }
    response = await client.post('/api/video/generate',
                               json=invalid_data)
    assert response.status_code == 400
    data = await response.get_json()
    assert data["status"] == "error"

@pytest.mark.asyncio
async def test_nonexistent_job(client):
    """Test status check for non-existent job."""
    response = await client.get('/api/video/status/nonexistent-job')
    assert response.status_code == 404
    data = await response.get_json()
    assert data["status"] == "error"