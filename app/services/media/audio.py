import os
import logging
import tempfile
from edge_tts import Communicate
import asyncio
import traceback
from typing import Optional
from moviepy.editor import AudioFileClip
from moviepy.audio.fx.all import audio_fadein, audio_fadeout
from moviepy.audio.fx import speedx as vfx

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug level logging

class AudioGenerator:
    def __init__(self):
        """Initialize the AudioGenerator service."""
        self.voice = "en-US-GuyNeural"  # Default voice
        
        # Create temporary directory with multiple fallback options
        try:
            self.temp_dir = tempfile.mkdtemp(prefix='audio_')
            logger.info(f"Created temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to create temp directory with tempfile.mkdtemp: {str(e)}")
            
            # Fallback 1: Try to create in /tmp
            try:
                self.temp_dir = os.path.join('/tmp', f'audio_{os.urandom(4).hex()}')
                os.makedirs(self.temp_dir, exist_ok=True)
                logger.info(f"Created temp directory (fallback 1): {self.temp_dir}")
            except Exception as e2:
                logger.warning(f"Failed to create temp directory in /tmp: {str(e2)}")
                
                # Fallback 2: Use current directory
                try:
                    self.temp_dir = os.path.join(os.getcwd(), f'tmp_audio_{os.urandom(4).hex()}')
                    os.makedirs(self.temp_dir, exist_ok=True)
                    logger.info(f"Created temp directory (fallback 2): {self.temp_dir}")
                except Exception as e3:
                    logger.error(f"All attempts to create temporary directory failed: {str(e3)}")
                    # Last resort - use a hardcoded path that should be writable on most systems
                    self.temp_dir = '/tmp/audio_default'
                    os.makedirs(self.temp_dir, exist_ok=True)
                    logger.info(f"Using default temp directory: {self.temp_dir}")
        
        # Verify the directory exists and is writable
        if not os.path.exists(self.temp_dir):
            logger.error(f"Temp directory does not exist after creation attempts: {self.temp_dir}")
        else:
            # Test if directory is writable
            try:
                test_file = os.path.join(self.temp_dir, 'test_write.txt')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info(f"Temp directory is writable: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Temp directory exists but is not writable: {self.temp_dir}, error: {str(e)}")

        logger.info(f"Initialized AudioGenerator with temp directory: {self.temp_dir}")

    def generate_audio(self, text: str, voice: Optional[str] = None, fade_in: float = 2.0, fade_out: float = 2.0, target_duration: Optional[float] = None) -> str:
        """
        Synchronous wrapper for async generate_audio method.
        
        Args:
            text: The text to convert to speech
            voice: Optional voice to use (defaults to en-US-GuyNeural)
            fade_in: Duration of fade in effect in seconds
            fade_out: Duration of fade out effect in seconds
            target_duration: Optional target duration in seconds. If provided, the audio will be
                           adjusted to match this duration using time stretching.
            
        Returns:
            str: Path to the generated audio file
        """
        try:
            logger.debug(f"Starting audio generation for text: {text[:100]}...")
            # Create event loop if one doesn't exist
            try:
                loop = asyncio.get_event_loop()
                logger.debug("Using existing event loop")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                logger.debug("Created new event loop")
            
            # Run async method
            result = loop.run_until_complete(self._generate_audio_async(text, voice))
            if result is None:
                logger.error("Audio generation failed in async method")
                return None

            # Apply fade effects if specified
            if fade_in > 0 or fade_out > 0:
                result = self._apply_fade_effects(result, fade_in, fade_out)
            
            # Adjust duration if target_duration is specified
            if target_duration is not None:
                result = self._adjust_duration(result, target_duration)
            
            return result
        except Exception as e:
            logger.error(f"Error in synchronous generate_audio: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _apply_fade_effects(self, audio_path: str, fade_in: float, fade_out: float) -> str:
        """
        Apply fade in/out effects to the audio file.
        
        Args:
            audio_path: Path to the input audio file
            fade_in: Duration of fade in effect in seconds
            fade_out: Duration of fade out effect in seconds
            
        Returns:
            str: Path to the processed audio file
        """
        try:
            # Load audio clip
            audio = AudioFileClip(audio_path)
            
            # Apply fade effects
            if fade_in > 0:
                audio = audio.fx(audio_fadein, fade_in)
            if fade_out > 0:
                audio = audio.fx(audio_fadeout, fade_out)
            
            # Save processed audio
            output_path = os.path.join(self.temp_dir, f"processed_{os.path.basename(audio_path)}")
            audio.write_audiofile(output_path)
            
            # Clean up
            audio.close()
            os.remove(audio_path)  # Remove original file
            
            return output_path
        except Exception as e:
            logger.error(f"Error applying fade effects: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return audio_path  # Return original file if processing fails

    def _adjust_duration(self, audio_path: str, target_duration: float) -> str:
        """
        Adjust the duration of an audio file to match the target duration.
        
        Args:
            audio_path: Path to the input audio file
            target_duration: Target duration in seconds
            
        Returns:
            str: Path to the processed audio file
        """
        try:
            # Load audio clip
            audio = AudioFileClip(audio_path)
            
            # Calculate speed factor
            current_duration = audio.duration
            speed_factor = current_duration / target_duration
            
            # Apply speed adjustment
            if speed_factor != 1.0:
                audio = audio.fx(vfx.speedx, speed_factor)
            
            # Save processed audio
            output_path = os.path.join(self.temp_dir, f"duration_adjusted_{os.path.basename(audio_path)}")
            audio.write_audiofile(output_path)
            
            # Clean up
            audio.close()
            os.remove(audio_path)  # Remove original file
            
            return output_path
        except Exception as e:
            logger.error(f"Error adjusting audio duration: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return audio_path  # Return original file if processing fails

    async def _generate_audio_async(self, text: str, voice: Optional[str] = None) -> str:
        """
        Generate audio from text using Edge TTS.
        
        Args:
            text: The text to convert to speech
            voice: Optional voice to use (defaults to en-US-GuyNeural)
            
        Returns:
            str: Path to the generated audio file
        """
        try:
            # Use provided voice or default
            selected_voice = voice or self.voice
            logger.debug(f"Using voice: {selected_voice}")
            
            # Ensure the temp directory exists
            if not os.path.exists(self.temp_dir):
                logger.warning(f"Temp directory doesn't exist, recreating: {self.temp_dir}")
                os.makedirs(self.temp_dir, exist_ok=True)
                
            # Create temporary file path
            temp_path = os.path.join(self.temp_dir, f"audio_{hash(text)}.mp3")
            logger.debug(f"Will save audio to: {temp_path}")
            
            # Double-check parent directory exists before saving
            parent_dir = os.path.dirname(temp_path)
            if not os.path.exists(parent_dir):
                logger.warning(f"Parent directory doesn't exist, creating: {parent_dir}")
                os.makedirs(parent_dir, exist_ok=True)
            
            # Generate audio
            communicate = Communicate(text, selected_voice)
            logger.debug("Created Communicate instance")
            
            await communicate.save(temp_path)
            logger.info(f"Successfully generated audio at: {temp_path}")
            
            # Verify file exists and has size
            if os.path.exists(temp_path):
                size = os.path.getsize(temp_path)
                logger.debug(f"Generated audio file size: {size} bytes")
                if size == 0:
                    raise Exception("Generated audio file is empty")
            else:
                raise Exception("Audio file was not created")
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def cleanup(self):
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temporary audio files")
        except Exception as e:
            logger.error(f"Error cleaning up audio files: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

# Create singleton instance
audio_generator = AudioGenerator() 