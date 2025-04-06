import logging
import openai
import os
import re
from typing import Optional, List, Dict
import json
import base64

logger = logging.getLogger(__name__)

class TextProcessor:
    # Average speaking rate (words per minute)
    SPEAKING_RATE = 150  # Standard speaking pace
    
    # Regex patterns for cleaning text
    HASHTAG_PATTERN = r'#\w+'  # Matches hashtags
    EMOJI_PATTERN = r'[\U0001F300-\U0001F9FF]|[\u2600-\u26FF\u2700-\u27BF]'  # Matches emojis and icons
    URL_PATTERN = r'(?:https?:\/\/|www\.)?(?:[\w]+\.)+[\w]+(?:\/[\w\.\-?=&%]*)*'  # Matches URLs with or without http(s) and www
    
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

    def clean_text(self, text: str) -> str:
        """
        Clean text by removing hashtags, emojis, URLs, and other non-narrative elements.
        
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
        First cleans the text by removing hashtags and icons,
        then adjusts length to match target duration if needed.
        
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
            
            if current_duration <= target_duration:
                logger.info("Text already fits within target duration")
                return cleaned_text
                
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
                            "content": f"You are a professional content summarizer. Summarize the following text to approximately {target_words} words while maintaining the key message and professional tone. The summary should be natural to speak and flow well when narrated. Do not include any hashtags, emojis, or special characters."
                        },
                        {
                            "role": "user",
                            "content": cleaned_text
                        }
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                processed_text = response.choices[0].message.content.strip()
                if not processed_text:
                    logger.warning("OpenAI returned empty text, using cleaned text")
                    return cleaned_text
                    
                final_duration = self.estimate_duration(processed_text)
                logger.info(f"Processed text duration: {final_duration}s")
                return processed_text
                
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                # If summarization fails, return the cleaned text instead of raising an error
                logger.warning("Using cleaned text due to summarization failure")
                return cleaned_text
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            # If all else fails, return the original text stripped
            return text.strip()

    def analyze_content_segments(self, text: str) -> List[Dict]:
        """
        Analyze text to identify natural segments and their durations.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of dictionaries containing segment text and estimated duration
        """
        try:
            # Use OpenAI to analyze and segment the content
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a content analyzer. Break down the following text into natural segments.
                        For each segment, identify:
                        1. The main topic/theme
                        2. The key points
                        3. The approximate speaking duration
                        
                        Return the segments in JSON format with:
                        - text: the segment text
                        - topic: main topic/theme
                        - key_points: list of key points
                        - duration: estimated speaking duration in seconds
                        
                        Ensure the segments flow naturally and maintain context."""
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response
            segments = json.loads(response.choices[0].message.content)
            
            # Validate and adjust durations
            total_duration = sum(segment['duration'] for segment in segments)
            if total_duration > 0:
                # Normalize durations to match estimated total
                estimated_total = self.estimate_duration(text)
                scale_factor = estimated_total / total_duration
                for segment in segments:
                    segment['duration'] = round(segment['duration'] * scale_factor, 2)
            
            return segments
            
        except Exception as e:
            logger.error(f"Error analyzing content segments: {str(e)}")
            # Fallback: split text into sentences and estimate duration for each
            sentences = text.split('.')
            segments = []
            for sentence in sentences:
                if sentence.strip():
                    duration = self.estimate_duration(sentence)
                    segments.append({
                        'text': sentence.strip(),
                        'topic': 'General',
                        'key_points': [sentence.strip()],
                        'duration': duration
                    })
            return segments

    def match_images_to_segments(self, segments: List[Dict], image_paths: List[str]) -> List[Dict]:
        """
        Match images to content segments based on semantic similarity.
        
        Args:
            segments: List of content segments
            image_paths: List of image file paths
            
        Returns:
            List of segments with matched images and adjusted durations
        """
        try:
            # For each segment, find the most relevant image
            matched_segments = []
            used_images = set()
            
            for segment in segments:
                # Find the best matching image
                best_match = None
                best_score = 0
                
                for image_path in image_paths:
                    if image_path in used_images:
                        continue
                        
                    # Use OpenAI to analyze image content
                    with open(image_path, 'rb') as img_file:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "Analyze this image and describe its content in detail."
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": f"Analyze this image and determine if it's relevant to the following content segment:\n\nTopic: {segment['topic']}\nKey Points: {', '.join(segment['key_points'])}"
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode()}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=300
                        )
                        
                        # Get relevance score from OpenAI
                        relevance_score = float(response.choices[0].message.content)
                        
                        if relevance_score > best_score:
                            best_score = relevance_score
                            best_match = image_path
                
                if best_match:
                    used_images.add(best_match)
                    segment['image_path'] = best_match
                else:
                    # If no good match found, use the first unused image
                    for image_path in image_paths:
                        if image_path not in used_images:
                            segment['image_path'] = image_path
                            used_images.add(image_path)
                            break
                
                matched_segments.append(segment)
            
            return matched_segments
            
        except Exception as e:
            logger.error(f"Error matching images to segments: {str(e)}")
            # Fallback: assign images sequentially
            matched_segments = []
            for i, segment in enumerate(segments):
                segment['image_path'] = image_paths[i % len(image_paths)]
                matched_segments.append(segment)
            return matched_segments

# Create a singleton instance
text_processor = TextProcessor() 