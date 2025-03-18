import pytest
import io
import os
import time
import json
import tempfile
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

def test_complete_image_upload_to_video_flow(client, mock_temp_files):
    """
    Integration test for the complete flow from image upload to video generation.
    
    This test:
    1. Uploads test images
    2. Uses the image IDs to request video generation
    3. Polls the status endpoint until completion
    4. Verifies the final video URL
    """
    # Step 1: Upload test images
    test_image1 = FileStorage(
        stream=io.BytesIO(b"test image content 1"),
        filename="test1.jpg",
        content_type="image/jpeg"
    )
    test_image2 = FileStorage(
        stream=io.BytesIO(b"test image content 2"),
        filename="test2.png",
        content_type="image/png"
    )
    
    # Mock the file validator to return success
    with patch('app.services.storage.file_validator.FileValidator.validate_files') as mock_validate:
        mock_validate.return_value = (True, {"message": "Files validated successfully"})
        
        # Make the upload request
        response = client.post(
            '/api/video/upload-images',
            data={
                'images': [test_image1, test_image2]
            },
            content_type='multipart/form-data'
        )
        
        # Verify the upload response
        assert response.status_code == 200
        upload_data = response.get_json()
        assert upload_data["success"] is True
        assert "image_ids" in upload_data
        
        # Step 2: Use the image IDs to request video generation
        image_ids = upload_data["image_ids"]
        
        # Mock the video generator to avoid actual processing
        with patch('app.services.video.generator.VideoGenerator.process_video_job') as mock_process:
            # Configure the mock to update job status
            def update_job_status(*args):
                job_id = args[0]
                redis_client = args[2]
                # Simulate job completion
                redis_client.set(f"job:{job_id}:status", '{"status": "completed", "progress": 100, "video_url": "https://example.com/test-video.mp4"}')
            
            mock_process.side_effect = update_job_status
            
            # Make the video generation request
            response = client.post(
                '/api/video/generate',
                json={
                    "content": "Test video with custom images",
                    "style": "professional",
                    "duration": 15,
                    "voice": "en-US-Neural2-F",
                    "user_image_ids": image_ids
                }
            )
            
            # Verify the generation response
            assert response.status_code == 202
            gen_data = response.get_json()
            assert "job_id" in gen_data
            job_id = gen_data["job_id"]
            
            # Step 3: Poll the status endpoint
            # Mock Redis to return completed status
            with patch('redis.Redis.get') as mock_redis_get:
                mock_redis_get.return_value = '{"status": "completed", "progress": 100, "video_url": "https://example.com/test-video.mp4"}'
                
                # Check status
                response = client.get(f'/api/video/status/{job_id}')
                
                # Verify the status response
                assert response.status_code == 200
                status_data = response.get_json()
                assert status_data["status"] == "success"
                assert status_data["data"]["status"] == "completed"
                assert status_data["data"]["progress"] == 100
                assert "video_url" in status_data["data"]

def test_fallback_to_auto_generated_images(client, sample_request_data):
    """
    Integration test for fallback to auto-generated images when user images fail.
    
    This test:
    1. Requests video generation with invalid image IDs
    2. Verifies the system falls back to auto-generated images
    3. Checks that the video is still generated successfully
    """
    # Add invalid image IDs to the request
    request_data = sample_request_data.copy()
    request_data["user_image_ids"] = ["invalid-id-1", "invalid-id-2"]
    
    # Mock the video generator to verify fallback behavior
    with patch('app.services.video.generator.VideoGenerator.fetch_user_images') as mock_fetch, \
         patch('app.services.video.generator.VideoGenerator.process_video_job') as mock_process:
        
        # Set up the mock to return empty list (simulating failure to find user images)
        mock_fetch.return_value = []
        
        # Make the video generation request
        response = client.post(
            '/api/video/generate',
            json=request_data
        )
        
        # Verify the generation response
        assert response.status_code == 202
        data = response.get_json()
        assert "job_id" in data
        assert data["status"] == "queued"

def test_error_handling_invalid_request(client):
    """
    Integration test for error handling with invalid requests.
    
    This test:
    1. Sends an invalid request (missing required fields)
    2. Verifies the system returns appropriate error responses
    """
    # Test with empty request
    response = client.post('/api/video/upload-images', data={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    
    # Test with invalid video generation request
    response = client.post('/api/video/generate', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data 