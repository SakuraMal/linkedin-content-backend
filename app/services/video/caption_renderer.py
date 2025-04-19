"""
Caption rendering service for video generation.

This module provides functionality to add captions to videos
based on caption preferences and timing data.
"""

import os
import logging
import subprocess
import tempfile
import re
import traceback
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
    
    def __init__(self, captions_enabled: bool = False, caption_prefs: Optional[Dict[str, Any]] = None, tts_text: Optional[str] = None):
        """
        Initialize the caption renderer.
        
        Args:
            captions_enabled: Whether captions are enabled
            caption_prefs: Caption preferences including style and timing
            tts_text: The text used for TTS generation, to be used directly for captions
        """
        # First check feature flag - if not enabled, captions will always be disabled
        self.feature_enabled = is_feature_enabled("ENABLE_CAPTIONS")
        
        # Only enable captions if both the feature flag and user preference are enabled
        self.enabled = self.feature_enabled and captions_enabled
        
        # Store caption preferences
        self.prefs = caption_prefs or {}
        
        # Store TTS text
        self.tts_text = tts_text
        
        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Caption renderer initialized. Feature enabled: {self.feature_enabled}, Captions enabled: {self.enabled}")
        
        if self.enabled:
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Caption preferences: {self.prefs}")
            if self.tts_text:
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: TTS text available for captions")
            else:
                logger.warning("🎬 CAPTION DEBUG [RENDERER]: No TTS text provided for captions")
    
    def generate_subtitle_file(self, timing_data: List[Any], output_path: str, processed_content: Optional[str] = None) -> str:
        """
        Generate an SRT subtitle file from timing data.
        
        Args:
            timing_data: List of caption timing data
            output_path: Directory to save the subtitle file
            processed_content: The exact TTS text used for audio generation
            
        Returns:
            Path to the generated subtitle file
        """
        if not self.enabled:
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Captions disabled, not generating subtitle file")
            return ""
            
        try:
            # Create subtitle file path
            subtitle_file = os.path.join(output_path, "captions.srt")
            
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Generating subtitle file at {subtitle_file}")
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: TTS text available: {bool(processed_content)}")
            
            # Format the subtitle content in SRT format
            with open(subtitle_file, "w") as f:
                subtitle_index = 1
                total_chunks = 0
                
                # Always use TTS text if available
                if processed_content:
                    logger.info("🎬 CAPTION DEBUG [RENDERER]: Using TTS text for captions")
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: TTS text length: {len(processed_content)}")
                    
                    # Split into sentences while preserving punctuation
                    sentences = re.split(r'(?<=[.!?])\s+', processed_content)
                    current_time = 0
                    
                    for sentence in sentences:
                        if not sentence.strip():
                            continue
                            
                        # Calculate duration based on sentence length (rough estimate)
                        # Average reading speed: ~3 words per second
                        words = len(sentence.split())
                        duration = max(2.0, min(5.0, words / 3.0))  # Min 2s, max 5s per sentence
                        
                        end_time = current_time + duration
                        start_time_fmt = self._format_srt_time(current_time)
                        end_time_fmt = self._format_srt_time(end_time)
                        
                        f.write(f"{subtitle_index}\n")
                        f.write(f"{start_time_fmt} --> {end_time_fmt}\n")
                        f.write(f"{sentence}\n\n")
                        
                        subtitle_index += 1
                        total_chunks += 1
                        current_time = end_time
                else:
                    logger.warning("🎬 CAPTION DEBUG [RENDERER]: No TTS text available, falling back to caption chunks")
                    # Fallback to using captionChunks with timing data
                    for segment in timing_data:
                        if isinstance(segment, dict):
                            caption_chunks = segment.get('captionChunks', [])
                        else:
                            caption_chunks = getattr(segment, 'captionChunks', [])
                        
                        for chunk in caption_chunks:
                            if isinstance(chunk, dict):
                                start_time = chunk.get('startTime', 0)
                                end_time = chunk.get('endTime', 0)
                                text = chunk.get('text', '')
                            else:
                                start_time = getattr(chunk, 'startTime', 0)
                                end_time = getattr(chunk, 'endTime', 0)
                                text = getattr(chunk, 'text', '')
                            
                            start_time_fmt = self._format_srt_time(start_time)
                            end_time_fmt = self._format_srt_time(end_time)
                            
                            f.write(f"{subtitle_index}\n")
                            f.write(f"{start_time_fmt} --> {end_time_fmt}\n")
                            f.write(f"{text}\n\n")
                            
                            subtitle_index += 1
                            total_chunks += 1
            
            # Verify the file was created and has content
            if os.path.exists(subtitle_file):
                file_size = os.path.getsize(subtitle_file)
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Subtitle file created successfully: {subtitle_file}")
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Subtitle file size: {file_size} bytes")
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Total caption chunks written: {total_chunks}")
                
                # Make sure file is readable by ffmpeg
                os.chmod(subtitle_file, 0o644)
                
                return subtitle_file
            else:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Subtitle file not created at {subtitle_file}")
                return ""
            
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error generating subtitle file: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
            return ""
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        Convert seconds to SRT time format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
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
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Captions disabled or subtitle file not found, returning original video")
            return video_path
            
        try:
            # Check if the subtitle file exists and has content
            if not os.path.exists(subtitle_file):
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Subtitle file does not exist: {subtitle_file}")
                return video_path
                
            file_size = os.path.getsize(subtitle_file)
            if file_size == 0:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Subtitle file is empty: {subtitle_file}")
                return video_path
                
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Using subtitle file: {subtitle_file} (size: {file_size} bytes)")
            
            # Extract style settings
            style = self.prefs.get("style", {})
            position = style.get("position", "bottom")
            size = style.get("size", 24)
            color = style.get("color", "#ffffff")
            bgcolor = style.get("backgroundColor", "#000000")
            opacity = style.get("opacity", 0.7)
            
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Applying caption style: position={position}, size={size}, color={color}")
            
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
            
            # Verify output directory exists and is writable
            output_dir = os.path.dirname(output_file)
            if not os.path.exists(output_dir):
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Creating output directory: {output_dir}")
                os.makedirs(output_dir, exist_ok=True)
                
            # Verify input video exists and has content
            if not os.path.exists(video_path):
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Input video does not exist: {video_path}")
                return video_path
                
            video_size = os.path.getsize(video_path)
            if video_size == 0:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Input video is empty: {video_path}")
                return video_path
                
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Input video: {video_path} (size: {video_size} bytes)")
            
            # Setup ffmpeg command to burn subtitles into the video
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={subtitle_file}:force_style='FontSize={size},PrimaryColour=&H{color[1:]},BackColour=&H{bgcolor_with_alpha[1:]},Alignment=2,MarginV={v_position}'",
                "-c:a", "copy",
                output_file
            ]
            
            cmd_str = ' '.join(cmd)
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Running ffmpeg command: {cmd_str}")
            
            # Execute ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Check the result
            if result.returncode != 0:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error applying captions: {result.stderr}")
                
                # Detailed ffmpeg error analysis
                if "No such file or directory" in result.stderr:
                    logger.error(f"🎬 CAPTION ERROR [RENDERER]: File not found error in ffmpeg")
                    # Check paths again
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Video path exists: {os.path.exists(video_path)}")
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Subtitle path exists: {os.path.exists(subtitle_file)}")
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Output directory exists: {os.path.exists(output_dir)}")
                
                if "Invalid data found when processing input" in result.stderr:
                    logger.error(f"🎬 CAPTION ERROR [RENDERER]: Invalid data in video or subtitle file")
                
                # Try alternative approach with absolute paths
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Trying alternative approach with absolute paths")
                cmd_alt = [
                    "ffmpeg", "-y",
                    "-i", os.path.abspath(video_path),
                    "-vf", f"subtitles={os.path.abspath(subtitle_file)}:force_style='FontSize={size},PrimaryColour=&H{color[1:]},BackColour=&H{bgcolor_with_alpha[1:]},Alignment=2,MarginV={v_position}'",
                    "-c:a", "copy",
                    os.path.abspath(output_file)
                ]
                
                cmd_alt_str = ' '.join(cmd_alt)
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Running alternative ffmpeg command: {cmd_alt_str}")
                
                # Try the alternative command
                result_alt = subprocess.run(cmd_alt, capture_output=True, text=True)
                
                if result_alt.returncode != 0:
                    logger.error(f"🎬 CAPTION ERROR [RENDERER]: Alternative command also failed: {result_alt.stderr}")
                    return video_path  # Return original video if captioning fails
                else:
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Alternative command succeeded")
                    
                    # Verify the output file was created
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Successfully created captioned video at {output_file}")
                        return output_file
                    else:
                        logger.error(f"🎬 CAPTION ERROR [RENDERER]: Output file not created or empty: {output_file}")
                        return video_path
            
            # Verify the output file was created
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                output_size = os.path.getsize(output_file)
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Successfully applied captions to video: {output_file} (size: {output_size} bytes)")
                
                # Also generate a VTT file for streaming captions
                vtt_file = os.path.join(output_path, f"{os.path.basename(video_path).split('.')[0]}.vtt")
                self._generate_vtt_from_srt(subtitle_file, vtt_file)
                
                return output_file
            else:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Output file not created or empty: {output_file}")
                return video_path  # Return original video if captioning fails
            
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error applying captions to video: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
            return video_path  # Return original video if captioning fails
    
    def _generate_vtt_from_srt(self, srt_file: str, vtt_file: str) -> bool:
        """
        Generate a WebVTT file from an SRT file for streaming captions.
        
        Args:
            srt_file: Path to the SRT file
            vtt_file: Path to the output VTT file
            
        Returns:
            bool: True if successful
        """
        try:
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Generating VTT file from SRT: {vtt_file}")
            
            # Check if source file exists
            if not os.path.exists(srt_file):
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: SRT file does not exist: {srt_file}")
                return False
            
            # Read SRT content
            with open(srt_file, 'r') as f:
                srt_content = f.read()
                
            # Write VTT header
            with open(vtt_file, 'w') as f:
                f.write("WEBVTT\n\n")
                
                # Convert SRT content to VTT format
                # SRT format: "00:00:00,000 --> 00:00:01,000"
                # VTT format: "00:00:00.000 --> 00:00:01.000"
                vtt_content = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', srt_content)
                
                # Add the converted content
                f.write(vtt_content)
            
            # Verify the file was created
            if os.path.exists(vtt_file) and os.path.getsize(vtt_file) > 0:
                vtt_size = os.path.getsize(vtt_file)
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Successfully created VTT file: {vtt_file} (size: {vtt_size} bytes)")
                
                # Set appropriate permissions
                os.chmod(vtt_file, 0o644)
                
                # Log VTT file path for reference
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: VTT file ready at: {vtt_file}")
                
                # Check if the file is alongside the video
                video_base = os.path.basename(vtt_file).split('.')[0]
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: VTT file associated with video: {video_base}")
                
                return True
            else:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: VTT file not created or empty: {vtt_file}")
                return False
                
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error generating VTT file: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
            return False

    def generate_timing_from_content(self, request) -> List[Dict]:
        """
        Generate timing data for captions from content.
        
        Args:
            request: The video request object containing content and timing information
            
        Returns:
            List of timing data dictionaries
        """
        try:
            # Use processed content if available, otherwise use original content
            content = getattr(request, 'processed_content', None)
            if content:
                logger.info("Using processed content for caption timing")
            else:
                content = request.content
                logger.info("Using original content for caption timing")
            
            # Split content into sentences
            sentences = [s.strip() for s in content.split('.') if s.strip()]
            
            # Calculate timing based on word count
            timing_data = []
            current_time = 0.0
            words_per_second = 2.5  # Standard speaking rate
            max_words_per_caption = 15  # Maximum words per caption
            
            for sentence in sentences:
                words = sentence.split()
                if not words:
                    continue
                
                # If sentence is too long, split it into chunks
                if len(words) > max_words_per_caption:
                    chunks = []
                    current_chunk = []
                    for word in words:
                        current_chunk.append(word)
                        if len(current_chunk) >= max_words_per_caption:
                            chunks.append(' '.join(current_chunk))
                            current_chunk = []
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                else:
                    chunks = [sentence]
                
                # Add timing for each chunk
                for chunk in chunks:
                    chunk_words = len(chunk.split())
                    duration = chunk_words / words_per_second
                    
                    timing_data.append({
                        'start': current_time,
                        'end': current_time + duration,
                        'text': chunk
                    })
                    
                    current_time += duration
            
            return timing_data
        except Exception as e:
            logger.error(f"Error generating timing from content: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def render_captions(self, video_path: str, caption_data: Dict[str, Any], work_dir: str, content: str = None, processed_content: str = None) -> str:
        """
        Render captions onto a video.
        
        Args:
            video_path: Path to the input video
            caption_data: Caption preferences and timing data
            work_dir: Working directory for temporary files
            content: Original content text
            processed_content: Processed TTS text used for audio generation
            
        Returns:
            Path to the video with captions
        """
        if not self.enabled:
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Captions disabled, skipping rendering")
            return video_path
            
        try:
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Starting caption rendering")
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Using processed_content: {processed_content is not None}")
            
            # Create temporary directory for caption files
            caption_dir = os.path.join(work_dir, "captions")
            os.makedirs(caption_dir, exist_ok=True)
            
            # Generate subtitle file using the exact TTS text
            subtitle_file = self.generate_subtitle_file(
                timing_data=caption_data.get('timing', []),
                output_path=caption_dir,
                processed_content=processed_content  # Use the exact TTS text
            )
            
            if not subtitle_file or not os.path.exists(subtitle_file):
                logger.error("🎬 CAPTION ERROR [RENDERER]: Failed to generate subtitle file")
                return video_path
                
            # Apply captions to video
            captioned_video = self.apply_captions_to_video(
                video_path=video_path,
                subtitle_file=subtitle_file,
                output_path=work_dir
            )
            
            if not captioned_video or not os.path.exists(captioned_video):
                logger.error("🎬 CAPTION ERROR [RENDERER]: Failed to apply captions to video")
                return video_path
                
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Successfully rendered captions")
            return captioned_video
            
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error rendering captions: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
            return video_path 