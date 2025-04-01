from pydantic import BaseModel, Field, HttpUrl
from typing import List, Literal, Optional, Dict, Any, Union
from enum import Enum
from .captions import CaptionPreferences

class MediaItem(BaseModel):
    type: Literal["image"] = "image"
    url: HttpUrl
    duration: float = Field(gt=0, le=10)  # Max 10 seconds per media item

class AudioPreferences(BaseModel):
    fadeInDuration: float = Field(default=2.0, ge=0, le=5, description="Audio fade in duration in seconds")
    fadeOutDuration: float = Field(default=2.0, ge=0, le=5, description="Audio fade out duration in seconds")

class TransitionStyle(str, Enum):
    CROSSFADE = "crossfade"
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    ZOOM = "zoom"

class TransitionPreferences(BaseModel):
    useAI: bool = Field(default=True, description="Whether to use AI for transition selection")
    defaultStyle: TransitionStyle = Field(default=TransitionStyle.CROSSFADE, description="Default transition style if not using AI")
    duration: float = Field(default=0.5, ge=0.2, le=2.0, description="Transition duration in seconds")

class VideoStyle(str, Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    DYNAMIC = "dynamic"

# Define a generic content analysis model to accept different formats
class ContentAnalysis(BaseModel):
    # Make all fields optional with Any type to handle variety of formats
    keywords: Optional[List[str]] = None
    entities: Optional[Union[List[str], Dict[str, Any]]] = None
    sentiment: Optional[str] = None
    topics: Optional[List[str]] = None
    
    # Allow extra fields for flexibility with different frontend implementations
    class Config:
        extra = "allow"

class VideoPreferences(BaseModel):
    """Video generation preferences including styling, transitions, and captions."""
    requirePexelsVideo: Optional[bool] = Field(default=True, description="Whether to require Pexels videos")
    minVideoSegments: Optional[int] = Field(default=2, description="Minimum number of video segments")
    transitionStyle: Optional[str] = Field(default="crossfade", description="Style of transitions between segments")
    audio: Optional[Dict[str, Any]] = Field(default=None, description="Audio preferences")
    captions: Optional[CaptionPreferences] = Field(default=None, description="Caption preferences and styling")
    
    class Config:
        extra = "allow"

class VideoRequest(BaseModel):
    """Request model for video generation."""
    content: str = Field(..., description="Text description of the video content")
    style: VideoStyle = Field(default=VideoStyle.PROFESSIONAL, description="Style of the video")
    duration: int = Field(default=10, ge=5, le=120, description="Duration of the video in seconds")
    voice: Optional[str] = Field(default=None, description="Optional voice ID for text-to-speech")
    audioPreferences: Optional[AudioPreferences] = Field(default=None, description="Audio fade in/out preferences")
    transitionPreferences: Optional[TransitionPreferences] = Field(default=None, description="Video transition preferences")
    user_image_ids: Optional[List[str]] = Field(default=None, description="List of IDs for user-uploaded images to use in the video")
    content_analysis: Optional[ContentAnalysis] = Field(default=None, description="Content analysis results for better video generation")
    contentAnalysis: Optional[ContentAnalysis] = Field(default=None, description="Alternative field name for content analysis")
    theme: Optional[str] = Field(default="business", description="Theme of the content")
    # Add explicit fields for stock media URLs mapping (supporting both naming conventions)
    stockMediaUrls: Optional[Dict[str, str]] = Field(default=None, description="Mapping of stock media IDs to their URLs")
    stockImageUrls: Optional[Dict[str, str]] = Field(default=None, description="Alternative name for stockMediaUrls")
    # Add videoPreferences field that will contain caption preferences
    videoPreferences: Optional[VideoPreferences] = Field(default=None, description="Video styling and caption preferences")
    
    class Config:
        # Allow unknown fields to handle different frontend formats
        extra = "allow"
        schema_extra = {
            "example": {
                "content": "This is a professional video about business growth strategies.",
                "style": "professional",
                "duration": 30,
                "voice": "en-US-Neural2-F",
                "user_image_ids": ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001"]
            }
        } 