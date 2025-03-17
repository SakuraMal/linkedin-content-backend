import logging
import openai
import os
import re
from typing import Optional
import nltk

# Download required NLTK data at module level
nltk.download('punkt', quiet=True)
from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)

class TextProcessor:
    # Average speaking rate (words per minute)
    SPEAKING_RATE = 150  # Standard speaking pace
    
    # Regex patterns for cleaning text
    HASHTAG_PATTERN = r'#\w+'  # Matches hashtags
    EMOJI_PATTERN = r'[\U0001F300-\U0001F9FF]|[\u2600-\u26FF\u2700-\u27BF]'  # Matches emojis and icons
    URL_PATTERN = r'(?:https?:\/\/)?(?:[\w-]+\.)+[\w-]+(?:\/[\w-\.?=&%]*)*'  # Matches URLs with or without http(s)
    
    def __init__(self):
        """Initialize the TextProcessor service."""
        self._openai_client = None
        logger.info("TextProcessor initialized with NLTK support")

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    def clean_text(self, text: str) -> str:
        """
        Clean text by removing hashtags, emojis, URLs, and other non-narrative elements.
        Ensures proper sentence structure and punctuation.
        
        Args:
            text: Input text to clean
            
        Returns:
            str: Cleaned text suitable for narration
        """
        try:
            # Remove URLs
            text = re.sub(self.URL_PATTERN, '', text)
            
            # Remove hashtags
            text = re.sub(self.HASHTAG_PATTERN, '', text)
            
            # Remove emojis and icons
            text = re.sub(self.EMOJI_PATTERN, '', text)
            
            # Clean up extra whitespace and multiple line breaks
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            # Ensure proper sentence endings
            text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)  # Add space after sentence endings
            text = re.sub(r'([^.!?])\s*$', r'\1.', text)  # Add period if missing at end
            
            # Ensure we have some text left after cleaning
            if not text:
                logger.warning("Text is empty after cleaning, using original text")
                return text.strip()
            
            logger.info("Text cleaned for narration: removed URLs, hashtags, and emojis")
            return text
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            # Return stripped original text if cleaning fails
            return text.strip()

    def estimate_duration(self, text: str) -> float:
        """
        Estimate the duration of speech for given text.
        Takes into account punctuation pauses.
        
        Args:
            text: Input text
            
        Returns:
            float: Estimated duration in seconds
        """
        # Count words
        word_count = len(text.split())
        
        # Add time for punctuation pauses
        sentences = sent_tokenize(text)
        pause_time = len(sentences) * 0.5  # 0.5 second pause between sentences
        
        # Calculate base duration in seconds
        speaking_duration = (word_count / self.SPEAKING_RATE) * 60
        
        return speaking_duration + pause_time

    def adjust_text_to_duration(self, text: str, target_duration: float) -> str:
        """
        Adjust text to match target duration while preserving complete sentences.
        
        Args:
            text: Input text
            target_duration: Target duration in seconds
            
        Returns:
            str: Adjusted text that fits the target duration
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a professional content summarizer. Create a concise, well-structured summary that:
1. Takes approximately {target_duration} seconds to narrate at a pace of {self.SPEAKING_RATE} words per minute
2. Maintains complete sentences and natural flow
3. Preserves the key message and professional tone
4. Is optimized for audio narration
5. Includes a clear introduction and conclusion
6. Uses transitions between ideas
Do not include hashtags, URLs, or special characters."""
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
            if not processed_text:
                logger.warning("OpenAI returned empty text, using original")
                return text
                
            # Verify the duration is close to target
            actual_duration = self.estimate_duration(processed_text)
            logger.info(f"Processed text duration: {actual_duration}s (target: {target_duration}s)")
            
            # If duration is significantly off, try one more time with adjusted target
            if abs(actual_duration - target_duration) > 3:  # More than 3 seconds off
                logger.info("Duration significantly off, adjusting...")
                adjusted_words = int((target_duration / actual_duration) * len(processed_text.split()))
                return self.adjust_text_to_duration(text, adjusted_words)
                
            return processed_text
            
        except Exception as e:
            logger.error(f"Error adjusting text duration: {str(e)}")
            return text

    def process_text(self, text: str, target_duration: float) -> Optional[str]:
        """
        Process and summarize text to match target duration.
        Ensures complete sentences and natural flow for narration.
        
        Args:
            text: Input text to process
            target_duration: Target duration in seconds
            
        Returns:
            str: Processed text that will fit within target duration
        """
        try:
            if not text:
                logger.error("Input text is empty")
                return None

            # Clean the text first
            cleaned_text = self.clean_text(text)
            if not cleaned_text:
                logger.warning("Cleaned text is empty, using original text")
                cleaned_text = text.strip()
            
            logger.info("Text cleaned for narration")
            
            current_duration = self.estimate_duration(cleaned_text)
            logger.info(f"Original text duration: {current_duration}s, target: {target_duration}s")
            
            if abs(current_duration - target_duration) <= 1:
                logger.info("Text already fits target duration")
                return cleaned_text
            
            # Adjust text to match duration while preserving sentences
            processed_text = self.adjust_text_to_duration(cleaned_text, target_duration)
            
            # Final verification of duration
            final_duration = self.estimate_duration(processed_text)
            logger.info(f"Final text duration: {final_duration}s")
            
            return processed_text
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            return text.strip()

# Create a singleton instance
text_processor = TextProcessor() 