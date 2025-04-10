import os
import logging
from typing import List, Dict, Tuple, Literal, Union, Optional
from PIL import Image, ImageFile
from PIL.Image import Resampling
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, vfx, VideoFileClip, ColorClip
)
import tempfile
import numpy as np
import math
from ...models.video import VideoStyle, TransitionStyle
import traceback
import psutil

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
        self.temp_dir = tempfile.mkdtemp(prefix='processed_')
        self.target_resolution = self.RESOLUTIONS[aspect_ratio]
        self.transition_duration = transition_duration
        logger.info(f"Initialized MediaProcessor with resolution: {self.target_resolution}, "
                   f"default transition duration: {transition_duration}s")

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
            # Load video
            clip = VideoFileClip(video_path)
            
            # Trim or loop video to match target duration
            if clip.duration > target_duration:
                # Take the middle section of the video
                start_time = (clip.duration - target_duration) / 2
                clip = clip.subclip(start_time, start_time + target_duration)
            elif clip.duration < target_duration:
                # Loop the video to reach target duration
                num_loops = math.ceil(target_duration / clip.duration)
                clip = concatenate_videoclips([clip] * num_loops).subclip(0, target_duration)
            
            # Resize maintaining aspect ratio
            target_ratio = self.target_resolution[0] / self.target_resolution[1]
            clip_ratio = clip.w / clip.h
            
            if clip_ratio > target_ratio:
                # Video is wider than target
                new_height = self.target_resolution[1]
                new_width = int(new_height * clip_ratio)
            else:
                # Video is taller than target
                new_width = self.target_resolution[0]
                new_height = int(new_width / clip_ratio)
            
            # Resize video
            clip = clip.resize(width=new_width, height=new_height)
            
            # Create a black background clip
            bg = ColorClip(self.target_resolution, color=(0,0,0))
            bg = bg.set_duration(clip.duration)
            
            # Position video in center
            x_pos = (self.target_resolution[0] - new_width) // 2
            y_pos = (self.target_resolution[1] - new_height) // 2
            clip = clip.set_position((x_pos, y_pos))
            
            # Composite with background
            final_clip = CompositeVideoClip([bg, clip], size=self.target_resolution)
            
            logger.info(f"Successfully processed video: {video_path}")
            return final_clip
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
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

    def combine_with_audio(self, video_clips: List[Union[ImageClip, VideoFileClip]], audio_path: str) -> Optional[str]:
        """
        Combine video clips with audio, ensuring proper synchronization and equal display times.
        
        Args:
            video_clips: List of video clips to combine
            audio_path: Path to the audio file
            
        Returns:
            Optional[str]: Path to the final video file if successful, None otherwise
        """
        try:
            # Process audio
            audio_clip = self.process_audio(audio_path)
            total_audio_duration = audio_clip.duration
            
            logger.info(f"Combining {len(video_clips)} video clips with audio (total duration: {total_audio_duration}s)")
            
            # IMPORTANT: Use method="chain_previews" to preserve transitions between clips
            # The "compose" method can sometimes reset transition effects
            final_video = concatenate_videoclips(video_clips, method="chain_previews")
            logger.info(f"Final video duration after concatenation: {final_video.duration}s")
            
            # Set audio
            final_video = final_video.set_audio(audio_clip)
            
            # Generate output path
            output_path = os.path.join(self.temp_dir, "final_video.mp4")
            
            # Write video with high quality settings
            logger.info(f"Writing final video to {output_path} with fps=30, bitrate=8000k")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=30,
                preset='medium',
                bitrate='8000k',
                audio_bitrate='192k',
                threads=4,
                logger=None
            )
            
            # Clean up
            final_video.close()
            audio_clip.close()
            
            logger.info(f"Successfully created video with synchronized audio: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error combining video with audio: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def cleanup(self):
        """Remove all temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

# Create a singleton instance with square aspect ratio and longer transition duration
media_processor = MediaProcessor(
    aspect_ratio='square',
    transition_duration=0.8  # Increased from 0.5 to make transitions more visible
) 