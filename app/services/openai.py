from typing import Dict, Optional
import os
import logging
from openai import OpenAI, APIError
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        """Initialize OpenAI client with API key from environment variables."""
        api_key = os.getenv('OPENAI_API_KEY')
        logger.info("Initializing OpenAI service...")
        
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable is not set")
            raise ValueError("OPENAI_API_KEY environment variable is not set")
            
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"  # Using GPT-3.5 Turbo model
        logger.info("OpenAI service initialized successfully")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: None
    )
    def generate_post(self, theme: str, tone: str, length: str) -> Dict:
        """
        Generate a LinkedIn post using OpenAI's GPT model.
        
        Args:
            theme (str): The post theme (e.g., "Leadership & Management")
            tone (str): The desired tone (e.g., "Professional")
            length (str): Desired length category (e.g., "Medium (500-1000 characters)")
            
        Returns:
            Dict: Generated post content and metadata
            
        Raises:
            APIError: If OpenAI API call fails
        """
        try:
            # Parse length requirement
            char_limits = {
                "Short (Under 500 characters)": (100, 500),
                "Medium (500-1000 characters)": (500, 1000),
                "Long (1000-1500 characters)": (1000, 1500)
            }
            min_chars, max_chars = char_limits.get(length, (500, 1000))

            # Create prompt for GPT
            prompt = f"""Generate a LinkedIn post about {theme}.
            Tone: {tone}
            Length: Between {min_chars} and {max_chars} characters
            
            Guidelines:
            - Make it engaging and thought-provoking
            - Include relevant hashtags
            - Focus on professional insights and experiences
            - Maintain the specified tone throughout
            - End with a call to action or question when appropriate
            
            Format the post ready for LinkedIn, including line breaks where appropriate."""

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional LinkedIn content creator, skilled in writing engaging posts that drive engagement."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800,
                top_p=1.0,
                frequency_penalty=0.5,
                presence_penalty=0.3
            )

            # Extract generated content
            content = response.choices[0].message.content.strip()
            char_count = len(content)

            return {
                "success": True,
                "data": {
                    "content": content,
                    "metadata": {
                        "theme": theme,
                        "tone": tone,
                        "length": length,
                        "characterCount": char_count,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            }

        except APIError as e:
            error_msg = f"OpenAI API error: {str(e)}"
            raise APIError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error in post generation: {str(e)}"
            raise Exception(error_msg) from e

    def validate_response(self, content: str, min_chars: int, max_chars: int) -> bool:
        """
        Validate the generated content meets requirements.
        
        Args:
            content (str): Generated post content
            min_chars (int): Minimum character count
            max_chars (int): Maximum character count
            
        Returns:
            bool: True if content meets requirements, False otherwise
        """
        char_count = len(content)
        return min_chars <= char_count <= max_chars 