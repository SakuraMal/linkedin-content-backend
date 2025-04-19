import os
import sys
from typing import List, Optional
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
from moviepy.audio.AudioClip import concatenate_audioclips
import logging

# Add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.models.video import Transcript

logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self, resolution: tuple = (1920, 1080), temp_dir: str = None):
        self.resolution = resolution
        self.temp_dir = temp_dir or os.path.join(os.getcwd(), "temp_media")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def combine_audio_chunks(self, audio_chunks: List[str]) -> Optional[str]:
        """Combine multiple audio chunks into a single audio file."""
        try:
            if not audio_chunks:
                return None
                
            # Load all audio clips
            audio_clips = []
            for chunk_path in audio_chunks:
                if os.path.exists(chunk_path):
                    audio_clips.append(AudioFileClip(chunk_path))
                else:
                    logger.error(f"Audio chunk not found: {chunk_path}")
                    return None
            
            if not audio_clips:
                return None
                
            # Concatenate all audio clips
            final_audio = concatenate_audioclips(audio_clips)
            
            # Save the combined audio
            output_path = os.path.join(self.temp_dir, "combined_audio.mp3")
            final_audio.write_audiofile(output_path)
            
            # Close all clips to free resources
            for clip in audio_clips:
                clip.close()
            final_audio.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error combining audio chunks: {str(e)}")
            return None
    
    def apply_captions(self, video_path: str, transcript: Transcript, caption_prefs: dict) -> str:
        """Apply captions to the video using the transcript."""
        try:
            # Load the video
            video = VideoFileClip(video_path)
            
            # Create text clips for each chunk
            text_clips = []
            for chunk in transcript.chunks:
                # Create text clip with timing
                txt_clip = TextClip(
                    chunk.text,
                    fontsize=caption_prefs.get('fontSize', 24),
                    color=caption_prefs.get('color', 'white'),
                    bg_color=caption_prefs.get('backgroundColor', 'black'),
                    font=caption_prefs.get('font', 'Arial'),
                    method='caption',
                    size=(video.w * 0.8, None)  # 80% of video width
                )
                
                # Set position and duration
                txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(chunk.end_time - chunk.start_time)
                txt_clip = txt_clip.set_start(chunk.start_time)
                
                text_clips.append(txt_clip)
            
            # Combine video with text clips
            final_video = CompositeVideoClip([video] + text_clips)
            
            # Save the final video
            output_path = os.path.join(self.temp_dir, "video_with_captions.mp4")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp-audio.m4a'),
                remove_temp=True
            )
            
            # Close all clips to free resources
            video.close()
            for clip in text_clips:
                clip.close()
            final_video.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error applying captions: {str(e)}")
            return video_path  # Return original video if captioning fails 