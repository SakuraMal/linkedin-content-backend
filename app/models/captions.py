"""
Models for video caption preferences and styling.
These models define the expected structure for caption data in video generation requests.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class CaptionChunk(BaseModel):
    """
    A segment of caption text with specific timing.
    """
    text: str = Field(..., description="The caption text to display")
    startTime: float = Field(..., description="Start time in seconds from video start")
    endTime: float = Field(..., description="End time in seconds from video start")

class CaptionTiming(BaseModel):
    """
    Timing information for a segment of captions.
    """
    type: Literal["intro", "main", "conclusion"] = Field(..., description="Type of the content segment")
    startTime: float = Field(..., description="Start time in seconds from video start")
    endTime: float = Field(..., description="End time in seconds from video start")
    duration: float = Field(..., description="Duration of the segment in seconds")
    captionChunks: List[CaptionChunk] = Field(default_factory=list, description="List of caption chunks within this segment")

class CaptionStyle(BaseModel):
    """
    Styling preferences for captions.
    """
    position: Literal["top", "bottom", "center"] = Field(default="bottom", description="Vertical position of captions")
    size: int = Field(default=24, ge=10, le=48, description="Font size in pixels")
    color: str = Field(default="#ffffff", description="Text color in hexadecimal format")
    font: Optional[str] = Field(default="Arial", description="Font name")
    backgroundColor: Optional[str] = Field(default="#000000", description="Background color in hexadecimal format")
    opacity: Optional[float] = Field(default=0.7, ge=0, le=1, description="Background opacity (0-1)")

class CaptionPreferences(BaseModel):
    """
    User preferences for caption display.
    """
    enabled: bool = Field(default=False, description="Whether captions are enabled")
    style: Optional[CaptionStyle] = Field(default=None, description="Caption styling preferences")
    timing: Optional[List[CaptionTiming]] = Field(default=None, description="Caption timing data for each segment")
    
    class Config:
        # Allow unknown fields for flexibility
        extra = "allow" 