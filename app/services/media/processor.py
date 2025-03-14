import os
import logging
from typing import List, Dict, Tuple, Literal, Union
from PIL import Image, ImageFile
from PIL.Image import Resampling
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, vfx, VideoFileClip, ColorClip
)
import tempfile
import numpy as np
import math

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

    # Available transition effects
    TRANSITIONS = {
        'crossfade': lambda clip, duration: clip.crossfadein(duration),
        'fade': lambda clip, duration: clip.fadein(duration),
        'slide_left': lambda clip, duration: clip.set_position(lambda t: ((1-t/duration)*clip.w, 0) if t < duration else (0,0)),
        'slide_right': lambda clip, duration: clip.set_position(lambda t: ((-t/duration*clip.w, 0) if t < duration else (0,0))),
        'zoom': lambda clip, duration: clip.set_position(lambda t: ('center')).resize(lambda t: 1 + 0.1*t if t < duration else 1)
    }
    
    def __init__(self, 
                 aspect_ratio: Literal['square', 'landscape', 'portrait', 'vertical'] = 'square',
                 transition_type: Literal['crossfade', 'fade', 'slide_left', 'slide_right', 'zoom'] = 'crossfade',
                 transition_duration: float = 0.5):
        """
        Initialize the MediaProcessor service.
        
        Args:
            aspect_ratio: The target aspect ratio for the video. Defaults to 'square' (1:1)
                        as it's the most commonly used format on LinkedIn.
            transition_type: Type of transition effect between images.
            transition_duration: Duration of transition effect in seconds.
        """
        self.temp_dir = tempfile.mkdtemp(prefix='processed_')
        self.target_resolution = self.RESOLUTIONS[aspect_ratio]
        self.transition_type = transition_type
        self.transition_duration = transition_duration
        logger.info(f"Initialized MediaProcessor with resolution: {self.target_resolution}, "
                   f"transition: {transition_type}, duration: {transition_duration}s")

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

    def create_video_segments(self, media_files: Dict[str, List[str]], durations: List[float]) -> List[Union[ImageClip, VideoFileClip]]:
        """
        Create video segments from processed images and videos with transitions.
        
        Args:
            media_files: Dictionary containing paths to media files
            durations: List of durations for each media item
            
        Returns:
            List[Union[ImageClip, VideoFileClip]]: List of processed video segments
        """
        try:
            clips = []
            total_duration = 0
            
            # Process images first
            image_paths = media_files.get('images', [])
            video_paths = media_files.get('videos', [])
            
            # Calculate durations for each type
            total_media = len(image_paths) + len(video_paths)
            if total_media == 0:
                raise ValueError("No media files provided")
            
            # Interleave images and videos
            media_items = []
            i, j = 0, 0
            while i < len(image_paths) or j < len(video_paths):
                if i < len(image_paths):
                    media_items.append(('image', image_paths[i]))
                    i += 1
                if j < len(video_paths):
                    media_items.append(('video', video_paths[j]))
                    j += 1
            
            # Process each media item
            for idx, (media_type, path) in enumerate(media_items):
                duration = durations[idx] if idx < len(durations) else 3.0
                
                if media_type == 'image':
                    clip = self.process_image(path, duration)
                else:  # video
                    clip = self.process_video(path, duration)
                
                # Apply transitions
                if idx == 0:  # First clip
                    clip = clip.fadein(self.transition_duration)
                if idx == len(media_items) - 1:  # Last clip
                    clip = clip.fadeout(self.transition_duration)
                
                # Set start time
                clip = clip.set_start(total_duration)
                total_duration += duration
                
                clips.append(clip)
                logger.info(f"Added {media_type} clip {idx+1}/{len(media_items)} at {total_duration-duration}s with duration {duration}s")
            
            logger.info(f"Created {len(clips)} video segments with {self.transition_type} transitions")
            return clips
            
        except Exception as e:
            logger.error(f"Error creating video segments: {str(e)}")
            raise

    def combine_with_audio(self, video_clips: List[Union[ImageClip, VideoFileClip]], audio_path: str) -> str:
        """
        Combine video segments with audio into final video.
        
        Args:
            video_clips: List of processed video clips
            audio_path: Path to the audio file
            
        Returns:
            str: Path to the final video file
        """
        try:
            # Create composite video with sequential clips
            final_video = CompositeVideoClip(video_clips, size=self.target_resolution)
            
            # Add audio
            audio = self.process_audio(audio_path)
            
            # Ensure audio duration matches video duration
            if audio.duration > final_video.duration:
                audio = audio.set_duration(final_video.duration)
            final_video = final_video.set_audio(audio)
            
            # Export final video with LinkedIn-optimized settings
            output_path = os.path.join(self.temp_dir, 'final_video.mp4')
            final_video.write_videofile(
                output_path,
                fps=30,  # LinkedIn recommended
                codec='libx264',
                audio_codec='aac',
                audio_bitrate='192k',  # LinkedIn recommended
                bitrate='8000k',  # High quality for LinkedIn
                temp_audiofile=os.path.join(self.temp_dir, 'temp_audio.m4a'),
                remove_temp=True
            )
            
            logger.info(f"Successfully created video: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error combining video with audio: {str(e)}")
            raise
        finally:
            # Clean up clips
            for clip in video_clips:
                clip.close()

    def cleanup(self):
        """Remove all temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

# Create a singleton instance with square aspect ratio and crossfade transitions
media_processor = MediaProcessor(
    aspect_ratio='square',
    transition_type='crossfade',
    transition_duration=0.5
) 