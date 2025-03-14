import logging
import openai
import os
from typing import Optional

logger = logging.getLogger(__name__)

class TextProcessor:
    # Average speaking rate (words per minute)
    SPEAKING_RATE = 150  # Standard speaking pace
    
    def __init__(self):
        """Initialize the TextProcessor service."""
        self._openai_client = None
        logger.info("TextProcessor initialized")

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    def estimate_duration(self, text: str) -> float:
        """
        Estimate the duration of speech for given text.
        
        Args:
            text: Input text
            
        Returns:
            float: Estimated duration in seconds
        """
        # Count words (simple split by spaces)
        word_count = len(text.split())
        # Calculate duration in seconds
        return (word_count / self.SPEAKING_RATE) * 60

    def process_text(self, text: str, target_duration: float) -> Optional[str]:
        """
        Process and summarize text to match target duration.
        
        Args:
            text: Input text to process
            target_duration: Target duration in seconds
            
        Returns:
            str: Processed text that will fit within target duration
        """
        try:
            current_duration = self.estimate_duration(text)
            logger.info(f"Original text duration: {current_duration}s, target: {target_duration}s")
            
            if current_duration <= target_duration:
                logger.info("Text already fits within target duration")
                return text
                
            # Calculate target word count
            target_words = int((target_duration / 60) * self.SPEAKING_RATE)
            logger.info(f"Target word count: {target_words}")
            
            # Use OpenAI to summarize the text
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a professional content summarizer. Summarize the following text to approximately {target_words} words while maintaining the key message and professional tone. The summary should be natural to speak and flow well when narrated."
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                processed_text = response.choices[0].message.content.strip()
                final_duration = self.estimate_duration(processed_text)
                
                logger.info(f"Processed text duration: {final_duration}s")
                return processed_text
                
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                raise ValueError(f"Failed to process text with OpenAI: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            return None

# Create a singleton instance
text_processor = TextProcessor() 