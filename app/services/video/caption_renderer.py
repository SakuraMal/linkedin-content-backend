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
        
        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Caption renderer initialized. Feature enabled: {self.feature_enabled}, Captions enabled: {self.enabled}")
        
        if self.enabled:
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Caption preferences: {self.prefs}")
    
    def generate_subtitle_file(self, timing_data: List[Any], output_path: str) -> str:
        """
        Generate an SRT subtitle file from timing data.
        
        Args:
            timing_data: List of caption timing data (can be objects or dictionaries)
            output_path: Directory to save the subtitle file
            
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
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Timing data type: {type(timing_data)}")
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Timing data length: {len(timing_data)}")
            
            # Format the subtitle content in SRT format
            with open(subtitle_file, "w") as f:
                subtitle_index = 1
                total_chunks = 0
                
                # Process all caption chunks from all timing segments
                for segment in timing_data:
                    # Handle both object and dictionary formats
                    if isinstance(segment, dict):
                        segment_type = segment.get('type', 'unknown')
                        caption_chunks = segment.get('captionChunks', [])
                    else:
                        segment_type = getattr(segment, 'type', 'unknown')
                        caption_chunks = getattr(segment, 'captionChunks', [])
                    
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Processing segment type: {segment_type} with {len(caption_chunks)} chunks")
                    
                    for chunk in caption_chunks:
                        # Handle both object and dictionary formats for chunks
                        if isinstance(chunk, dict):
                            start_time = chunk.get('startTime', 0)
                            end_time = chunk.get('endTime', 0)
                            text = chunk.get('text', '')
                        else:
                            start_time = getattr(chunk, 'startTime', 0)
                            end_time = getattr(chunk, 'endTime', 0)
                            text = getattr(chunk, 'text', '')
                        
                        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Chunk {subtitle_index}: {start_time}-{end_time}: '{text}'")
                        
                        # Convert seconds to SRT time format (HH:MM:SS,mmm)
                        start_time_fmt = self._format_srt_time(start_time)
                        end_time_fmt = self._format_srt_time(end_time)
                        
                        # Write SRT entry
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
                
                # Log first few lines of the subtitle file for debugging
                with open(subtitle_file, 'r') as f:
                    first_lines = ''.join([next(f) for _ in range(10) if f])
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: First lines of subtitle file:\n{first_lines}")
                
                # Verify permissions on the file
                file_permissions = oct(os.stat(subtitle_file).st_mode)[-3:]
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Subtitle file permissions: {file_permissions}")
                
                # Make sure file is readable by ffmpeg
                os.chmod(subtitle_file, 0o644)
                new_permissions = oct(os.stat(subtitle_file).st_mode)[-3:]
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Updated subtitle file permissions: {new_permissions}")
                
                return subtitle_file
            else:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Subtitle file not created at {subtitle_file}")
                return ""
            
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error generating subtitle file: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
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

    def generate_timing_from_content(self, content: str) -> List[dict]:
        """
        Generate caption timing data from content text.
        
        This is used when timing data is not provided by the frontend.
        It splits the content into segments and generates timing information.
        
        Args:
            content: The content text for the video
            
        Returns:
            List of caption timing segments with caption chunks
        """
        logger.info("🎬 CAPTION DEBUG [RENDERER]: Generating caption timing data from content")
        
        # Constants for timing calculation
        words_per_second = 2.5  # Average reading speed
        max_words_per_caption = 10  # For readability
        
        # Split content into sentences
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            logger.warning("🎬 CAPTION DEBUG [RENDERER]: No sentences found in content")
            return []
        
        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Found {len(sentences)} sentences in content")
        
        # Simple algorithm to segment content
        total_sentences = len(sentences)
        segments = []
        current_time = 0.0
        
        # Create segments (intro, main, conclusion)
        segment_types = ["intro", "main", "conclusion"]
        
        # Calculate roughly how many sentences per segment
        if total_sentences < 3:
            # If very short content, just make everything main
            segment_distribution = [0, total_sentences, 0]
        else:
            # Approximately 20% intro, 60% main, 20% conclusion
            intro_count = max(1, int(total_sentences * 0.2))
            conclusion_count = max(1, int(total_sentences * 0.2))
            main_count = total_sentences - intro_count - conclusion_count
            segment_distribution = [intro_count, main_count, conclusion_count]
        
        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Segment distribution: {segment_distribution}")
        
        # Track sentence index
        sentence_index = 0
        
        # Create each segment
        for segment_type, sentence_count in zip(segment_types, segment_distribution):
            if sentence_count <= 0:
                continue
                
            # Get sentences for this segment
            segment_sentences = sentences[sentence_index:sentence_index+sentence_count]
            sentence_index += sentence_count
            
            if not segment_sentences:
                continue
                
            # Join sentences for this segment
            segment_text = ". ".join(segment_sentences)
            if not segment_text.endswith("."):
                segment_text += "."
                
            # Calculate timing
            words = segment_text.split()
            word_count = len(words)
            duration = word_count / words_per_second
            
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Segment '{segment_type}' with {word_count} words, duration: {duration:.2f}s")
            
            # Create caption chunks
            caption_chunks = []
            for i in range(0, word_count, max_words_per_caption):
                chunk_words = words[i:i+max_words_per_caption]
                chunk_text = " ".join(chunk_words)
                chunk_duration = len(chunk_words) / words_per_second
                chunk_start = current_time + (i / word_count) * duration
                chunk_end = chunk_start + chunk_duration
                
                caption_chunks.append({
                    "text": chunk_text,
                    "startTime": chunk_start,
                    "endTime": chunk_end
                })
                
                logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Chunk {i/max_words_per_caption}: {chunk_start:.2f}-{chunk_end:.2f}: '{chunk_text}'")
            
            # Add segment
            segments.append({
                "type": segment_type,
                "startTime": current_time,
                "endTime": current_time + duration,
                "duration": duration,
                "captionChunks": caption_chunks
            })
            
            # Update current time
            current_time += duration
        
        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Generated {len(segments)} segments with {sum(len(s['captionChunks']) for s in segments)} caption chunks")
        return segments
    
    def render_captions(self, video_path: str, caption_data: Dict[str, Any], work_dir: str, content: str = None) -> str:
        """
        Render captions onto a video.
        
        This is the main entry point for caption rendering.
        
        Args:
            video_path: Path to the input video
            caption_data: Dictionary containing caption preferences and timing data
            work_dir: Working directory for temporary files
            content: Optional content text for generating timing if not provided
            
        Returns:
            Path to the output video with captions
        """
        if not self.enabled:
            logger.info("🎬 CAPTION DEBUG [RENDERER]: Captions disabled, returning original video")
            return video_path
            
        try:
            # Log video path and directory for debugging
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Starting caption rendering for video: {video_path}")
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Work directory: {work_dir}")
            
            # Verify video exists and is playable
            if not os.path.exists(video_path):
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Video file does not exist: {video_path}")
                return video_path
                
            video_size = os.path.getsize(video_path)
            if video_size == 0:
                logger.error(f"🎬 CAPTION ERROR [RENDERER]: Video file is empty: {video_path}")
                return video_path
                
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Video file size: {video_size} bytes")
            
            # Extract video ID from path for VTT association
            video_id = os.path.basename(video_path).split('.')[0]
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Video ID for caption association: {video_id}")
            
            # Extract timing data from caption data
            timing_data = caption_data.get("timing", [])
            
            # If no timing data is provided but we have content, generate timing data
            if (not timing_data or len(timing_data) == 0) and content:
                logger.info("🎬 CAPTION DEBUG [RENDERER]: No caption timing data found, generating from content")
                timing_data = self.generate_timing_from_content(content)
                
            if not timing_data or len(timing_data) == 0:
                logger.warning("🎬 CAPTION DEBUG [RENDERER]: No caption timing data found and no content provided, cannot add captions")
                return video_path
                
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Starting caption rendering with {len(timing_data)} timing segments")
            
            # Generate subtitle file
            subtitle_file = self.generate_subtitle_file(timing_data, work_dir)
            
            if not subtitle_file:
                logger.warning("🎬 CAPTION DEBUG [RENDERER]: Failed to generate subtitle file, returning original video")
                return video_path
                
            # Apply captions to video
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Applying captions to video with subtitle file: {subtitle_file}")
            captioned_video = self.apply_captions_to_video(video_path, subtitle_file, work_dir)
            
            # If successful, also generate a standalone VTT file
            if captioned_video != video_path:
                # Generate VTT file with same base name as video
                vtt_file = os.path.join(work_dir, f"{video_id}.vtt")
                vtt_success = self._generate_vtt_from_srt(subtitle_file, vtt_file)
                
                if vtt_success:
                    logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Generated VTT file for streaming: {vtt_file}")
                    
                    # Copy VTT file to same directory as video
                    video_dir = os.path.dirname(captioned_video)
                    final_vtt_path = os.path.join(video_dir, f"{video_id}.vtt")
                    
                    try:
                        import shutil
                        shutil.copy2(vtt_file, final_vtt_path)
                        logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Copied VTT file alongside video: {final_vtt_path}")
                        
                        # Ensure VTT file is readable
                        os.chmod(final_vtt_path, 0o644)
                    except Exception as e:
                        logger.error(f"🎬 CAPTION ERROR [RENDERER]: Failed to copy VTT file: {str(e)}")
            
            # Return path to the captioned video
            logger.info(f"🎬 CAPTION DEBUG [RENDERER]: Caption rendering complete: {captioned_video}")
            return captioned_video
            
        except Exception as e:
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error rendering captions: {str(e)}")
            logger.error(f"🎬 CAPTION ERROR [RENDERER]: Error traceback: {traceback.format_exc()}")
            return video_path  # Return original video if captioning fails 