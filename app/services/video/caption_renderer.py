"""
Caption rendering service for video generation.

This module provides functionality to add captions to videos
based on caption preferences and timing data.
"""

import os
import logging
import subprocess
import tempfile
from typing import Dict, List, Optional, Any
from ...config import is_feature_enabled
from ...models.captions import CaptionPreferences, CaptionTiming

logger = logging.getLogger(__name__)

class CaptionRenderer:
    """
    Service for rendering captions onto videos.
    
    This class handles the generation of captions based on
    caption preferences and timing data, and adds them to
    the generated video.
    """
    
    def __init__(self, captions_enabled: bool = False, caption_prefs: Optional[Dict[str, Any]] = None):
        """
        Initialize the caption renderer.
        
        Args:
            captions_enabled: Whether captions are enabled
            caption_prefs: Caption preferences including style and timing
        """
        # First check feature flag - if not enabled, captions will always be disabled
        self.feature_enabled = is_feature_enabled("ENABLE_CAPTIONS")
        
        # Only enable captions if both the feature flag and user preference are enabled
        self.enabled = self.feature_enabled and captions_enabled
        
        # Store caption preferences
        self.prefs = caption_prefs or {}
        
        logger.info(f"Caption renderer initialized. Feature enabled: {self.feature_enabled}, Captions enabled: {self.enabled}")
        
        if self.enabled:
            logger.info(f"Caption preferences: {self.prefs}")
    
    def generate_subtitle_file(self, timing_data: List[CaptionTiming], output_path: str) -> str:
        """
        Generate an SRT subtitle file from timing data.
        
        Args:
            timing_data: List of caption timing data
            output_path: Directory to save the subtitle file
            
        Returns:
            Path to the generated subtitle file
        """
        if not self.enabled:
            logger.info("Captions disabled, not generating subtitle file")
            return ""
            
        try:
            # Create subtitle file path
            subtitle_file = os.path.join(output_path, "captions.srt")
            
            # Format the subtitle content in SRT format
            with open(subtitle_file, "w") as f:
                subtitle_index = 1
                
                # Process all caption chunks from all timing segments
                for segment in timing_data:
                    for chunk in segment.captionChunks:
                        # Convert seconds to SRT time format (HH:MM:SS,mmm)
                        start_time = self._format_srt_time(chunk.startTime)
                        end_time = self._format_srt_time(chunk.endTime)
                        
                        # Write SRT entry
                        f.write(f"{subtitle_index}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{chunk.text}\n\n")
                        
                        subtitle_index += 1
            
            logger.info(f"Generated subtitle file at {subtitle_file}")
            return subtitle_file
            
        except Exception as e:
            logger.error(f"Error generating subtitle file: {str(e)}")
            # Return empty path but don't fail the video generation
            return ""
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        Convert seconds to SRT time format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        # Calculate hours, minutes, seconds and milliseconds
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        
        # Format as HH:MM:SS,mmm
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"
    
    def apply_captions_to_video(self, video_path: str, subtitle_file: str, output_path: str) -> str:
        """
        Apply captions to a video using ffmpeg.
        
        Args:
            video_path: Path to the input video
            subtitle_file: Path to the subtitle file
            output_path: Directory to save the output video
            
        Returns:
            Path to the output video with captions
        """
        if not self.enabled or not subtitle_file or not os.path.exists(subtitle_file):
            logger.info("Captions disabled or subtitle file not found, returning original video")
            return video_path
            
        try:
            # Extract style settings
            style = self.prefs.get("style", {})
            position = style.get("position", "bottom")
            size = style.get("size", 24)
            color = style.get("color", "#ffffff")
            bgcolor = style.get("backgroundColor", "#000000")
            opacity = style.get("opacity", 0.7)
            
            # Opacity is a float between 0-1, convert to hex alpha (00-FF)
            alpha_hex = hex(int(opacity * 255))[2:].zfill(2)
            bgcolor_with_alpha = f"{bgcolor}{alpha_hex}" if bgcolor.startswith("#") else bgcolor
            
            # Set vertical position
            if position == "top":
                v_position = "10"
            elif position == "bottom":
                v_position = "main_h-text_h-10"
            else:  # center
                v_position = "(main_h-text_h)/2"
            
            # Create output file path
            output_file = os.path.join(output_path, "captioned_video.mp4")
            
            # Setup ffmpeg command to burn subtitles into the video
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={subtitle_file}:force_style='FontSize={size},PrimaryColour=&H{color[1:]},BackColour=&H{bgcolor_with_alpha[1:]},Alignment=2,MarginV={v_position}'",
                "-c:a", "copy",
                output_file
            ]
            
            logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
            
            # Execute ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Error applying captions: {result.stderr}")
                return video_path  # Return original video if captioning fails
                
            logger.info(f"Successfully applied captions to video: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error applying captions to video: {str(e)}")
            return video_path  # Return original video if captioning fails

    def render_captions(self, video_path: str, caption_data: Dict[str, Any], work_dir: str) -> str:
        """
        Render captions onto a video.
        
        This is the main entry point for caption rendering.
        
        Args:
            video_path: Path to the input video
            caption_data: Dictionary containing caption preferences and timing data
            work_dir: Working directory for temporary files
            
        Returns:
            Path to the output video with captions
        """
        if not self.enabled:
            logger.info("Captions disabled, returning original video")
            return video_path
            
        try:
            # Extract timing data from caption data
            timing_data = caption_data.get("timing", [])
            
            if not timing_data:
                logger.warning("No caption timing data found, cannot add captions")
                return video_path
                
            # Log caption rendering start
            logger.info(f"Starting caption rendering for video: {video_path}")
            
            # Generate subtitle file
            subtitle_file = self.generate_subtitle_file(timing_data, work_dir)
            
            if not subtitle_file:
                logger.warning("Failed to generate subtitle file, returning original video")
                return video_path
                
            # Apply captions to video
            captioned_video = self.apply_captions_to_video(video_path, subtitle_file, work_dir)
            
            return captioned_video
            
        except Exception as e:
            logger.error(f"Error rendering captions: {str(e)}")
            return video_path  # Return original video if captioning fails 