import pytest
import io
import os
import tempfile
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

def test_image_upload_endpoint(client):
    """Test the image upload endpoint."""
    # Create test image files
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
        
        # Verify the response
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "Successfully uploaded" in data["message"]
        assert "images" in data
        assert "image_ids" in data

def test_image_upload_validation_failure(client):
    """Test image upload validation failure."""
    # Create an oversized test image
    large_content = b"x" * (3 * 1024 * 1024)  # 3MB content (exceeds 2MB limit)
    oversized_image = FileStorage(
        stream=io.BytesIO(large_content),
        filename="oversized.jpg",
        content_type="image/jpeg"
    )
    
    # Mock the file validator to simulate validation failure
    with patch('app.services.storage.file_validator.FileValidator.validate_files') as mock_validate:
        mock_validate.return_value = (False, {"error": "File exceeds maximum size"})
        
        # Make the upload request with oversized image
        response = client.post(
            '/api/video/upload-images',
            data={
                'images': [oversized_image]
            },
            content_type='multipart/form-data'
        )
        
        # Verify the response indicates validation failure
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

def test_video_generation_with_custom_images(client, sample_request_with_images, mock_temp_files):
    """Test video generation with custom images."""
    # Mock the video generator to avoid actual processing
    with patch('app.services.video.generator.VideoGenerator.process_video_job'):
        # Make the video generation request
        response = client.post(
            '/api/video/generate',
            json=sample_request_with_images
        )
        
        # Verify the response
        assert response.status_code == 202
        data = response.get_json()
        assert "job_id" in data
        assert data["status"] == "queued"
        
        # Verify the process_video_job was called
        # mock_process.assert_called_once()

def test_file_validator():
    """Test the file validator service."""
    from app.services.storage.file_validator import FileValidator
    
    # Create test files
    valid_image = FileStorage(
        stream=io.BytesIO(b"valid image content"),
        filename="valid.jpg",
        content_type="image/jpeg"
    )
    
    invalid_type = FileStorage(
        stream=io.BytesIO(b"invalid file content"),
        filename="invalid.exe",
        content_type="application/octet-stream"
    )
    
    # Create validator with test settings
    validator = FileValidator(
        max_files=2,
        max_file_size=1024 * 1024,  # 1MB
        allowed_types=['image/jpeg', 'image/png']
    )
    
    # Test valid file
    with patch('magic.from_buffer', return_value='image/jpeg'):
        is_valid, result = validator.validate_files([valid_image])
        assert is_valid is True
        assert "successfully" in result["message"].lower()
    
    # Test invalid file type
    with patch('magic.from_buffer', return_value='application/octet-stream'):
        is_valid, result = validator.validate_files([invalid_type])
        assert is_valid is False
        assert "error" in result
        assert isinstance(result["error"], list) or isinstance(result["error"], str)
        
    # Test too many files
    too_many = [valid_image] * 3  # 3 files when max is 2
    with patch('magic.from_buffer', return_value='image/jpeg'):
        is_valid, result = validator.validate_files(too_many)
        assert is_valid is False
        assert "error" in result 