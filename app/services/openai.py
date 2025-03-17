from typing import Dict, Optional
import os
import logging
from openai import OpenAI, APIError
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        """Initialize OpenAI client with API key and system instructions from environment variables."""
        api_key = os.getenv('OPENAI_API_KEY')
        self.system_instructions = os.getenv('OPENAI_SYSTEM_INSTRUCTIONS', 
            "You are a professional LinkedIn content creator, skilled in writing engaging posts that drive engagement.")
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
    def generate_post(self, theme: str, tone: str, target_audience: str, length: int, include_video: bool = False) -> Dict:
        """
        Generate a LinkedIn post using OpenAI's GPT model.
        
        Args:
            theme (str): The post theme (e.g., "Leadership & Management")
            tone (str): The desired tone (e.g., "Professional")
            target_audience (str): Target audience for the post
            length (int): Desired character length
            include_video (bool): Whether to include video suggestions
            
        Returns:
            Dict: Generated post content and metadata
            
        Raises:
            APIError: If OpenAI API call fails
        """
        try:
            # Create prompt for GPT
            prompt = f"""Generate a LinkedIn post about {theme}.
            Tone: {tone}
            Target Audience: {target_audience}
            Length: Approximately {length} characters
            
            Guidelines:
            - Make it engaging and thought-provoking for {target_audience}
            - Include relevant hashtags
            - Focus on professional insights and experiences
            - Maintain the specified tone throughout
            - End with a call to action or question when appropriate
            
            Format the post ready for LinkedIn, including line breaks where appropriate."""

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_instructions},
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

            response_data = {
                "success": True,
                "data": {
                    "content": content,
                    "metadata": {
                        "theme": theme,
                        "tone": tone,
                        "targetAudience": target_audience,
                        "length": length,
                        "characterCount": char_count,
                        "includeVideo": include_video,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            }

            # If video is requested, add placeholder for video suggestion
            if include_video:
                response_data["data"]["videoSuggestion"] = {
                    "type": "placeholder",
                    "message": "Video generation will be implemented in a future update"
                }

            return response_data

        except APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return {
                "success": False,
                "error": f"OpenAI API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in post generation: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error in post generation: {str(e)}"
            }

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