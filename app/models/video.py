from pydantic import BaseModel, Field, HttpUrl
from typing import List, Literal, Optional
from enum import Enum

class MediaItem(BaseModel):
    type: Literal["image"] = "image"
    url: HttpUrl
    duration: float = Field(gt=0, le=10)  # Max 10 seconds per media item

class AudioPreferences(BaseModel):
    fadeInDuration: float = Field(default=2.0, ge=0, le=5, description="Audio fade in duration in seconds")
    fadeOutDuration: float = Field(default=2.0, ge=0, le=5, description="Audio fade out duration in seconds")

class VideoStyle(str, Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    DYNAMIC = "dynamic"

class VideoRequest(BaseModel):
    """Request model for video generation."""
    content: str = Field(..., description="Text description of the video content")
    style: VideoStyle = Field(default=VideoStyle.PROFESSIONAL, description="Style of the video")
    duration: int = Field(default=10, ge=5, le=30, description="Duration of the video in seconds")
    voice: Optional[str] = Field(default=None, description="Optional voice ID for text-to-speech")
    audioPreferences: Optional[AudioPreferences] = Field(default=None, description="Audio fade in/out preferences") 