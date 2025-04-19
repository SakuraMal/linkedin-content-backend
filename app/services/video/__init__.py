"""
Video generation services.
"""

from .media_processor import MediaProcessor
from .generator import VideoGenerator
from .caption_renderer import CaptionRenderer
from .storage import StorageService

# Create singleton instances
storage_service = StorageService()

__all__ = ['VideoGenerator', 'StorageService', 'MediaProcessor', 'CaptionRenderer']
