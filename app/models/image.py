from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Image(BaseModel):
    """Model for tracking uploaded images."""
    id: str
    user_id: Optional[str] = None
    original_filename: str
    storage_path: str
    content_type: str
    url: str
    created_at: datetime = Field(default_factory=datetime.now)


class ImageUploadResponse(BaseModel):
    """Response model for image upload API."""
    success: bool
    message: str
    images: Optional[List[Image]] = None
    errors: Optional[List[str]] = None


class VideoRequestWithImages(BaseModel):
    """Extended video request model that includes user-uploaded image IDs."""
    content: str
    style: str = "professional"
    duration: int = 30
    voice: str = "en-US-Neural2-F"
    user_image_ids: Optional[List[str]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "content": "A video about cloud computing",
                "style": "professional",
                "duration": 30,
                "voice": "en-US-Neural2-F",
                "user_image_ids": ["image-id-1", "image-id-2"]
            }
        } 