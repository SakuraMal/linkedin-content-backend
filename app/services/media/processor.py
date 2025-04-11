import os
import logging
from typing import List, Dict, Tuple, Literal, Union, Optional
from PIL import Image, ImageFile
from PIL.Image import Resampling
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, vfx, VideoFileClip, ColorClip, AudioClip
)
import tempfile
import numpy as np
import math
from ...models.video import VideoStyle, TransitionStyle
import traceback
import psutil
import shutil

# Prevent truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)

class MediaProcessor:
    # LinkedIn recommended resolutions
    RESOLUTIONS = {
        'square': (1080, 1080),      # 1:1 - Most common, ~40% of videos
        'landscape': (1920, 1080),   # 16:9 - Great for desktop
        'portrait': (1080, 1350),    # 4:5 - Optimal for mobile
        'vertical': (1080, 1920)     # 9:16 - Full vertical
    }

    # Available transition effects - FIXED with more pronounced transitions
    TRANSITIONS = {
        TransitionStyle.CROSSFADE: lambda clip, duration: clip.crossfadein(duration),
        TransitionStyle.FADE: lambda clip, duration: clip.fadein(duration),
        TransitionStyle.SLIDE_LEFT: lambda clip, duration: clip.set_position(lambda t: ((1-min(1, t/duration))*clip.w, 0) if t < duration*1.5 else (0,0)),
        TransitionStyle.SLIDE_RIGHT: lambda clip, duration: clip.set_position(lambda t: ((-min(1, t/duration)*clip.w, 0) if t < duration*1.5 else (0,0))),
        TransitionStyle.ZOOM: lambda clip, duration: clip.set_position('center').resize(lambda t: max(0.7, min(1, 0.7 + 0.3*t/duration)) if t < duration*1.5 else 1)
    }

    # Style-based transition preferences
    STYLE_TRANSITIONS = {
        VideoStyle.PROFESSIONAL: [TransitionStyle.CROSSFADE, TransitionStyle.FADE],
        VideoStyle.CASUAL: [TransitionStyle.SLIDE_LEFT, TransitionStyle.SLIDE_RIGHT],
        VideoStyle.DYNAMIC: [TransitionStyle.ZOOM, TransitionStyle.SLIDE_LEFT, TransitionStyle.SLIDE_RIGHT]
    }
    
    def __init__(self, 
                 aspect_ratio: Literal['square', 'landscape', 'portrait', 'vertical'] = 'square',
                 transition_duration: float = 0.5):
        """
        Initialize the MediaProcessor service.
        
        Args:
            aspect_ratio: The target aspect ratio for the video. Defaults to 'square' (1:1)
                        as it's the most commonly used format on LinkedIn.
            transition_duration: Default duration of transition effects in seconds.
        """
        # Create a base temp directory if it doesn't exist
        base_temp_dir = '/tmp/processed_media'
        if not os.path.exists(base_temp_dir):
            try:
                os.makedirs(base_temp_dir, mode=0o777, exist_ok=True)
                logger.info(f"Created base temporary directory: {base_temp_dir}")
            except Exception as e:
                logger.error(f"Failed to create base temporary directory: {str(e)}")
                raise

        # Create a unique subdirectory for this processor instance
        self.temp_dir = tempfile.mkdtemp(prefix='processed_', dir=base_temp_dir)
        
        # Ensure the directory has proper permissions
        try:
            os.chmod(self.temp_dir, 0o777)
            logger.info(f"Set permissions on temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to set permissions on temporary directory: {str(e)}")
            raise

        self.target_resolution = self.RESOLUTIONS[aspect_ratio]
        self.transition_duration = transition_duration
        logger.info(f"Initialized MediaProcessor with resolution: {self.target_resolution}, "
                   f"default transition duration: {transition_duration}s, "
                   f"temp directory: {self.temp_dir}")

    def select_transition(self, 
                        index: int, 
                        total_clips: int, 
                        video_style: VideoStyle,
                        content_type: Optional[str] = None) -> TransitionStyle:
        """
        Select an appropriate transition based on content context and video style.
        
        Args:
            index: Current clip index
            total_clips: Total number of clips
            video_style: Style of the video (professional, casual, dynamic)
            content_type: Optional content type hint for the current segment
            
        Returns:
            TransitionStyle: Selected transition style
        """
        # Get available transitions for the current style
        available_transitions = self.STYLE_TRANSITIONS[video_style]
        
        if video_style == VideoStyle.PROFESSIONAL:
            # Professional style: Consistent transitions
            return available_transitions[0]  # Always use crossfade
            
        elif video_style == VideoStyle.CASUAL:
            # Casual style: Alternate between slide directions
            return (TransitionStyle.SLIDE_LEFT if index % 2 == 0 
                   else TransitionStyle.SLIDE_RIGHT)
            
        else:  # DYNAMIC
            # Dynamic style: Mix transitions based on position
            if index == 0:  # First transition
                return TransitionStyle.FADE
            elif index == total_clips - 1:  # Last transition
                return TransitionStyle.FADE
            else:  # Middle transitions
                # Randomly select from available transitions, excluding fade
                transitions = [t for t in available_transitions if t != TransitionStyle.FADE]
                return transitions[index % len(transitions)]

    def process_image(self, image_path: str, duration: float) -> ImageClip:
        """
        Process an image for video creation.
        - Resizes to target resolution
        - Adds duration
        - Centers the image
        - Maintains aspect ratio with letterboxing/pillarboxing if needed
        
        Args:
            image_path: Path to the image file
            duration: Duration in seconds this image should appear
            
        Returns:
            ImageClip: Processed image clip ready for video
        """
        try:
            # Open and process image with PIL
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate resize dimensions maintaining aspect ratio
                target_ratio = self.target_resolution[0] / self.target_resolution[1]
                img_ratio = img.width / img.height
                
                if img_ratio > target_ratio:
                    # Image is wider than target ratio
                    new_width = int(self.target_resolution[1] * img_ratio)
                    new_height = self.target_resolution[1]
                else:
                    # Image is taller than target ratio
                    new_width = self.target_resolution[0]
                    new_height = int(self.target_resolution[0] / img_ratio)
                
                # Resize image using LANCZOS resampling
                img = img.resize((new_width, new_height), Resampling.LANCZOS)
                
                # Create new image with target resolution and paste resized image in center
                final_img = Image.new('RGB', self.target_resolution, (0, 0, 0))  # Black background
                paste_x = (self.target_resolution[0] - new_width) // 2
                paste_y = (self.target_resolution[1] - new_height) // 2
                final_img.paste(img, (paste_x, paste_y))
                
                # Save processed image
                processed_path = os.path.join(self.temp_dir, f"processed_{os.path.basename(image_path)}")
                final_img.save(processed_path, quality=95)
                
                # Create video clip
                clip = ImageClip(processed_path).set_duration(duration)
                logger.info(f"Successfully processed image: {image_path}")
                return clip
                
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            raise

    def process_audio(self, audio_path: str) -> AudioFileClip:
        """
        Process audio file for video.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            AudioFileClip: Processed audio clip
        """
        try:
            audio_clip = AudioFileClip(audio_path)
            logger.info(f"Successfully processed audio: {audio_path}")
            return audio_clip
        except Exception as e:
            logger.error(f"Error processing audio {audio_path}: {str(e)}")
            raise

    def process_video(self, video_path: str, target_duration: float = 3.0) -> VideoFileClip:
        """
        Process a video clip for inclusion in the final video.
        - Resizes to target resolution
        - Adjusts duration
        - Centers the video
        - Maintains aspect ratio with letterboxing/pillarboxing if needed
        
        Args:
            video_path: Path to the video file
            target_duration: Target duration in seconds
            
        Returns:
            VideoFileClip: Processed video clip ready for final video
        """
        try:
            # Log video processing start
            logger.info(f"Processing video file: {video_path} with target duration {target_duration}s")
            
            # Load video - handle errors better
            try:
                # Explicitly disable audio loading since we'll be using TTS audio
                clip = VideoFileClip(video_path, audio=False)
                logger.info(f"Successfully loaded video: {video_path}, original duration: {clip.duration}s, dimensions: {clip.w}x{clip.h}")
            except Exception as e:
                logger.error(f"Error loading video file {video_path}: {str(e)}")
                raise ValueError(f"Failed to load video file. This may not be a valid video format: {str(e)}")
            
            # Trim or loop video to match target duration
            original_duration = clip.duration
            if original_duration > target_duration:
                # Take a good portion from the video - prefer starting from beginning for stock videos
                if original_duration > target_duration * 2:
                    # For long videos, take the most interesting parts at the beginning
                    # This works better for stock videos which often have good content at the start
                    start_time = 0.5  # Start a bit after the beginning
                    clip = clip.subclip(start_time, start_time + target_duration)
                    logger.info(f"Video trimmed to {target_duration}s starting at {start_time}s")
                else:
                    # For shorter videos, take the middle section
                    start_time = (original_duration - target_duration) / 2
                    clip = clip.subclip(start_time, start_time + target_duration)
                    logger.info(f"Video trimmed to {target_duration}s from middle section")
            elif original_duration < target_duration:
                # For short videos, we'll loop or extend them
                if original_duration > 1.0:  # Only loop if it's long enough to be meaningful
                    # Loop the video to reach target duration
                    num_loops = math.ceil(target_duration / original_duration)
                    clip = concatenate_videoclips([clip] * num_loops).subclip(0, target_duration)
                    logger.info(f"Video looped {num_loops} times to reach {target_duration}s")
                else:
                    # For very short clips, extend their duration
                    clip = clip.fx(vfx.speedx, original_duration / target_duration)
                    logger.info(f"Very short video extended from {original_duration}s to {target_duration}s")
            
            logger.info(f"Video duration adjusted: {original_duration}s → {clip.duration}s")
            
            # Resize maintaining aspect ratio
            target_ratio = self.target_resolution[0] / self.target_resolution[1]
            clip_ratio = clip.w / clip.h
            
            if clip_ratio > target_ratio:
                # Video is wider than target
                new_height = self.target_resolution[1]
                new_width = int(new_height * clip_ratio)
                logger.info(f"Resizing video (wider): {clip.w}x{clip.h} → {new_width}x{new_height}")
            else:
                # Video is taller than target
                new_width = self.target_resolution[0]
                new_height = int(new_width / clip_ratio)
                logger.info(f"Resizing video (taller): {clip.w}x{clip.h} → {new_width}x{new_height}")
            
            # Resize video with higher quality settings
            try:
                clip = clip.resize(width=new_width, height=new_height)
                logger.info(f"Video successfully resized to {new_width}x{new_height}")
            except Exception as resize_error:
                logger.error(f"Error during video resize: {str(resize_error)}")
                # Fallback to simpler resize method if the standard one fails
                try:
                    clip = clip.resize(newsize=(new_width, new_height))
                    logger.info(f"Video resized with fallback method to {new_width}x{new_height}")
                except Exception as fallback_error:
                    logger.error(f"Fallback resize also failed: {str(fallback_error)}")
                    # Last resort, don't resize but continue
                    logger.warning(f"Using original video size: {clip.w}x{clip.h}")
            
            # Create a black background clip
            bg = ColorClip(self.target_resolution, color=(0,0,0))
            bg = bg.set_duration(clip.duration)
            
            # Position video in center
            x_pos = (self.target_resolution[0] - new_width) // 2
            y_pos = (self.target_resolution[1] - new_height) // 2
            clip = clip.set_position((x_pos, y_pos))
            
            # Composite with background
            final_clip = CompositeVideoClip([bg, clip], size=self.target_resolution)
            
            logger.info(f"Successfully processed video: {video_path}, final duration: {final_clip.duration}s")
            return final_clip
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def create_video_segments(self, 
                            media_files: Dict[str, List[str]], 
                            durations: List[float],
                            video_style: VideoStyle = VideoStyle.PROFESSIONAL,
                            transition_duration: Optional[float] = None,
                            transition_style: Optional[TransitionStyle] = None) -> List[Union[ImageClip, VideoFileClip]]:
        """
        Create video segments from media files with transitions.
        
        Args:
            media_files: Dictionary containing lists of image and video paths
            durations: List of durations for each segment
            video_style: Style of the video
            transition_duration: Duration of transitions in seconds
            transition_style: User's chosen transition style
            
        Returns:
            List of video clips with transitions
        """
        try:
            # Use provided transition duration or default
            transition_duration = transition_duration or self.transition_duration
            
            # Process all images and videos
            clips = []
            for i, (image_path, duration) in enumerate(zip(media_files['images'], durations)):
                # Process image
                clip = self.process_image(image_path, duration)
                
                # Apply transition if not the first clip
                if i > 0:
                    # Use user's chosen transition style if provided, otherwise use style-based selection
                    if transition_style:
                        logger.info(f"Using user-specified transition style: {transition_style}")
                        transition = self.TRANSITIONS[transition_style]
                    else:
                        style_transition = self.select_transition(i, len(media_files['images']), video_style)
                        logger.info(f"Using style-based transition: {style_transition}")
                        transition = self.TRANSITIONS[style_transition]
                    
                    # Apply transition
                    logger.info(f"Applying transition with duration {transition_duration}s for clip {i}")
                    clip = transition(clip, transition_duration)
                
                clips.append(clip)
            
            # Process videos if any
            for video_path in media_files.get('videos', []):
                video_clip = self.process_video(video_path)
                clips.append(video_clip)
            
            return clips
            
        except Exception as e:
            logger.error(f"Error creating video segments: {str(e)}")
            raise

    def combine_with_audio(self, video_clips: List[VideoFileClip], audio_clip: AudioFileClip, output_path: str) -> None:
        """
        Combine video clips with audio and add transitions.
        
        Args:
            video_clips: List of video clips to combine
            audio_clip: Audio clip to add to the video
            output_path: Path where the final video should be saved
        """
        try:
            # Log memory usage before processing
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            logger.info(f"Starting video combination. Initial memory usage: {initial_memory:.2f} MB")
            
            # Log video clip details
            for i, clip in enumerate(video_clips):
                logger.info(f"Video clip {i+1}/{len(video_clips)}: "
                          f"Duration: {clip.duration:.2f}s, "
                          f"Size: {clip.w}x{clip.h}, "
                          f"FPS: {clip.fps}")
            
            # Log audio details
            logger.info(f"Audio clip: Duration: {audio_clip.duration:.2f}s, "
                      f"FPS: {audio_clip.fps}")
            
            # Apply transitions between clips
            final_clips = []
            for i, clip in enumerate(video_clips):
                if i > 0:  # Add transition to all clips except the first
                    transition = self.select_transition(i, len(video_clips), VideoStyle.DYNAMIC)
                    clip = self.TRANSITIONS[transition](clip, self.transition_duration)
                final_clips.append(clip)
            
            # Combine all clips
            final_video = concatenate_videoclips(final_clips)
            
            # Log memory usage after combining clips
            memory_after_combine = process.memory_info().rss / 1024 / 1024  # MB
            logger.info(f"Memory usage after combining clips: {memory_after_combine:.2f} MB")
            
            # Set audio
            final_video = final_video.set_audio(audio_clip)
            
            # Write the final video
            logger.info(f"Writing final video to: {output_path}")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp-audio.m4a'),
                remove_temp=True,
                fps=30,
                threads=4,
                preset='medium',
                bitrate='5000k'
            )
            
            # Log memory usage after writing
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            logger.info(f"Final memory usage: {final_memory:.2f} MB")
            
            # Clean up
            final_video.close()
            for clip in video_clips:
                clip.close()
            audio_clip.close()
            
            logger.info(f"Successfully created video at: {output_path}")
            
        except Exception as e:
            logger.error(f"Error combining video with audio: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def cleanup(self):
        """
        Clean up temporary files and directories.
        """
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
                # Remove all files in the temp directory
                for filename in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f"Error removing {file_path}: {str(e)}")
                
                # Remove the temp directory itself
                try:
                    os.rmdir(self.temp_dir)
                    logger.info(f"Successfully cleaned up temporary directory: {self.temp_dir}")
                except Exception as e:
                    logger.error(f"Error removing temp directory {self.temp_dir}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")
            logger.error(traceback.format_exc())

# Create a singleton instance with square aspect ratio and longer transition duration
media_processor = MediaProcessor(
    aspect_ratio='square',
    transition_duration=0.8  # Increased from 0.5 to make transitions more visible
) 