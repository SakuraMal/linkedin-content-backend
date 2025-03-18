import pytest
import io
import os
import tempfile
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
from google.cloud.storage import Blob, Bucket, Client
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_image_storage_service_upload():
    """Test the image storage service upload functionality."""
    from app.services.storage.image_storage import ImageStorageService
    
    # Create test files
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
    
    # Mock the GCS client and bucket
    mock_client = MagicMock(spec=Client)
    mock_bucket = MagicMock(spec=Bucket)
    mock_blob = MagicMock(spec=Blob)
    
    # Configure the mocks
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = "https://storage.example.com/test-signed-url"
    
    # Create a test instance with mocked components
    with patch('app.services.video.storage.StorageService') as mock_storage_service:
        # Configure the mock storage service
        mock_storage_service_instance = MagicMock()
        mock_storage_service_instance.client = mock_client
        mock_storage_service_instance.bucket = mock_bucket
        mock_storage_service_instance.bucket_name = "test-bucket"
        mock_storage_service.return_value = mock_storage_service_instance
        
        # Create the image storage service
        image_storage = ImageStorageService()
        
        # Test uploading images
        user_id = "test-user-123"
        result = image_storage.upload_images([test_image1, test_image2], user_id)
        
        # Verify the results
        assert len(result) == 2
        assert "id" in result[0]
        assert "filename" in result[0]
        assert "storage_path" in result[0]
        assert "url" in result[0]
        assert "content_type" in result[0]
        
        assert result[0]["filename"] == "test1.jpg"
        assert result[0]["content_type"] == "image/jpeg"
        assert result[0]["url"] == "https://storage.example.com/test-signed-url"
        
        assert result[1]["filename"] == "test2.png"
        assert result[1]["content_type"] == "image/png"
        
        # Verify the blob was created and uploaded
        assert mock_bucket.blob.call_count == 2
        mock_blob.upload_from_file.assert_called()
        mock_blob.generate_signed_url.assert_called()

@pytest.mark.asyncio
async def test_image_storage_service_get_url():
    """Test the image storage service get_image_url functionality."""
    from app.services.storage.image_storage import ImageStorageService
    
    # Mock the GCS client and bucket
    mock_client = MagicMock(spec=Client)
    mock_bucket = MagicMock(spec=Bucket)
    mock_blob = MagicMock(spec=Blob)
    
    # Configure the mocks
    mock_client.bucket.return_value = mock_bucket
    mock_client.list_blobs.return_value = [
        MagicMock(name="user_uploads/images/2024/03/17/test-user/test-image-id-1.jpg"),
        MagicMock(name="user_uploads/images/2024/03/17/test-user/test-image-id-2.png")
    ]
    mock_client.list_blobs.return_value[0].generate_signed_url.return_value = "https://storage.example.com/test-image-id-1.jpg"
    mock_client.list_blobs.return_value[1].generate_signed_url.return_value = "https://storage.example.com/test-image-id-2.png"
    
    # Create a test instance with mocked components
    with patch('app.services.video.storage.StorageService') as mock_storage_service:
        # Configure the mock storage service
        mock_storage_service_instance = MagicMock()
        mock_storage_service_instance.client = mock_client
        mock_storage_service_instance.bucket = mock_bucket
        mock_storage_service_instance.bucket_name = "test-bucket"
        mock_storage_service.return_value = mock_storage_service_instance
        
        # Create the image storage service
        image_storage = ImageStorageService()
        
        # Test getting image URL
        url = image_storage.get_image_url("test-image-id-1")
        
        # Verify the results
        assert url == "https://storage.example.com/test-image-id-1.jpg"
        mock_client.list_blobs.assert_called_once_with("test-bucket", prefix=image_storage.image_folder)

@pytest.mark.asyncio
async def test_image_storage_service_delete():
    """Test the image storage service delete_image functionality."""
    from app.services.storage.image_storage import ImageStorageService
    
    # Mock the GCS client and bucket
    mock_client = MagicMock(spec=Client)
    mock_bucket = MagicMock(spec=Bucket)
    
    # Create mock blobs
    mock_blob1 = MagicMock(name="user_uploads/images/2024/03/17/test-user/test-image-id-1.jpg")
    mock_blob2 = MagicMock(name="user_uploads/images/2024/03/17/test-user/test-image-id-2.png")
    
    # Configure the mocks
    mock_client.bucket.return_value = mock_bucket
    mock_client.list_blobs.return_value = [mock_blob1, mock_blob2]
    
    # Create a test instance with mocked components
    with patch('app.services.video.storage.StorageService') as mock_storage_service:
        # Configure the mock storage service
        mock_storage_service_instance = MagicMock()
        mock_storage_service_instance.client = mock_client
        mock_storage_service_instance.bucket = mock_bucket
        mock_storage_service_instance.bucket_name = "test-bucket"
        mock_storage_service.return_value = mock_storage_service_instance
        
        # Create the image storage service
        image_storage = ImageStorageService()
        
        # Test deleting an image
        result = image_storage.delete_image("test-image-id-1")
        
        # Verify the results
        assert result is True
        mock_client.list_blobs.assert_called_once_with("test-bucket", prefix=image_storage.image_folder)
        mock_blob1.delete.assert_called_once()
        assert not mock_blob2.delete.called 