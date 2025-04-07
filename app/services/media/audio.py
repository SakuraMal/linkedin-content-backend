import os
import logging
import tempfile
from edge_tts import Communicate
import asyncio
import traceback
from typing import Optional
from moviepy.editor import AudioFileClip
from moviepy.audio.fx.all import audio_fadein, audio_fadeout
from moviepy.audio.fx.volumex import volumex
import shutil

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug level logging

class AudioGenerator:
    def __init__(self):
        """Initialize the AudioGenerator service."""
        self.voice = "en-US-GuyNeural"  # Default voice
        self.rate = "+0%"  # Default rate (2.6 words per second)
        
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

    def generate_audio(self, text: str, voice: Optional[str] = None, fade_in: float = 2.0, fade_out: float = 2.0) -> str:
        """
        Synchronous wrapper for async generate_audio method.
        
        Args:
            text: The text to convert to speech
            voice: Optional voice to use (defaults to en-US-GuyNeural)
            fade_in: Duration of fade in effect in seconds
            fade_out: Duration of fade out effect in seconds
            
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
            os.makedirs(self.temp_dir, exist_ok=True)
            
            # Generate unique filename
            output_path = os.path.join(self.temp_dir, f"tts_{os.urandom(4).hex()}.mp3")
            
            # Create communicate object with voice and rate
            communicate = Communicate(text, selected_voice, rate=self.rate)
            
            # Generate audio file
            await communicate.save(output_path)
            
            logger.info(f"Successfully generated audio file: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def cleanup(self):
        """Clean up temporary files and directory."""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {str(e)}")

# Create singleton instance
audio_generator = AudioGenerator() 