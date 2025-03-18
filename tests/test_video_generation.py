import pytest
from unittest.mock import patch, MagicMock
from app.models.video import VideoRequest

def test_video_generation_endpoint(client, sample_request_data):
    """Test the video generation endpoint."""
    # Mock the video generator to avoid actual processing
    with patch('app.services.video.generator.VideoGenerator.process_video_job'):
        response = client.post('/api/video/generate',
                              json=sample_request_data)
        assert response.status_code == 202
        data = response.get_json()
        assert "job_id" in data
        assert data["status"] == "queued"

def test_video_status_endpoint(client, sample_request_data):
    """Test the video status endpoint."""
    # First create a job
    with patch('app.services.video.generator.VideoGenerator.process_video_job'):
        response = client.post('/api/video/generate',
                              json=sample_request_data)
        assert response.status_code == 202
        data = response.get_json()
        job_id = data["job_id"]

        # Mock Redis for status updates
        with patch('redis.Redis.get') as mock_redis_get:
            # Set up the mock to return status data
            mock_redis_get.return_value = '{"status": "processing", "progress": 50}'
            
            # Then check its status
            response = client.get(f'/api/video/status/{job_id}')
            assert response.status_code == 200
            data = response.get_json()
            assert "status" in data
            assert data["status"] == "success"
            assert "data" in data
            assert "status" in data["data"]
            assert "progress" in data["data"]

def test_video_generation_process(client, sample_request_data):
    """Test the complete video generation process."""
    # Create a job
    with patch('app.services.video.generator.VideoGenerator.process_video_job'):
        response = client.post('/api/video/generate',
                              json=sample_request_data)
        assert response.status_code == 202
        data = response.get_json()
        job_id = data["job_id"]

        # Mock Redis for status updates
        with patch('redis.Redis.get') as mock_redis_get:
            # Set up the mock to return completed status
            mock_redis_get.return_value = '{"status": "completed", "progress": 100, "video_url": "https://example.com/video.mp4"}'
            
            # Check status
            response = client.get(f'/api/video/status/{job_id}')
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "success"
            assert data["data"]["status"] == "completed"
            assert data["data"]["progress"] == 100
            assert "video_url" in data["data"]

def test_invalid_request(client):
    """Test video generation with invalid request data."""
    # Missing required fields
    with patch('app.models.video.VideoRequest') as mock_video_request:
        mock_video_request.side_effect = ValueError("Missing required field: content")
        
        response = client.post('/api/video/generate', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    # Invalid content (empty string)
    with patch('app.models.video.VideoRequest') as mock_video_request:
        mock_video_request.side_effect = ValueError("Content cannot be empty")
        
        invalid_data = {
            "content": "",
            "style": "professional",
            "duration": 15
        }
        response = client.post('/api/video/generate', json=invalid_data)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

def test_nonexistent_job(client):
    """Test status check for non-existent job."""
    # Mock Redis to return None for nonexistent job
    with patch('redis.Redis.get') as mock_redis_get:
        mock_redis_get.return_value = None
        
        response = client.get('/api/video/status/nonexistent-job')
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data["message"].lower()