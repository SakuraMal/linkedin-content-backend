import os
import logging
import tempfile
from edge_tts import Communicate
import asyncio
import traceback
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug level logging

class AudioGenerator:
    def __init__(self):
        """Initialize the AudioGenerator service."""
        self.voice = "en-US-GuyNeural"  # Default voice
        self.temp_dir = tempfile.mkdtemp(prefix='audio_')
        logger.info(f"Initialized AudioGenerator with temp directory: {self.temp_dir}")

    def generate_audio(self, text: str, voice: Optional[str] = None) -> str:
        """
        Synchronous wrapper for async generate_audio method.
        
        Args:
            text: The text to convert to speech
            voice: Optional voice to use (defaults to en-US-GuyNeural)
            
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
            return result
        except Exception as e:
            logger.error(f"Error in synchronous generate_audio: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

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
            
            # Create temporary file path
            temp_path = os.path.join(self.temp_dir, f"audio_{hash(text)}.mp3")
            logger.debug(f"Will save audio to: {temp_path}")
            
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