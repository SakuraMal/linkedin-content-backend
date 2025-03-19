from typing import Dict, Optional, List
import os
import logging
from openai import OpenAI, APIError
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime
import nltk
from nltk.tokenize import word_tokenize, RegexpTokenizer
from nltk.corpus import stopwords
from string import punctuation
import re
import traceback
import sentry_sdk

logger = logging.getLogger(__name__)

# Define a custom tokenizer as fallback
FALLBACK_TOKENIZER = RegexpTokenizer(r'\w+|\$[\d\.]+|\S+')

# Module-level flag for punkt_tab availability
PUNKT_TAB_AVAILABLE = False

try:
    nltk.data.find('tokenizers/punkt')
    PUNKT_TAB_AVAILABLE = True
    logger.info("NLTK punkt tokenizer is available")
except LookupError:
    logger.warning("NLTK punkt tokenizer not found, will use fallback tokenizer")
    PUNKT_TAB_AVAILABLE = False

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
        
        # Setup fallback tokenizer flag
        self.use_fallback_tokenizer = False
        
        # Initialize NLTK resources if needed for content analysis
        try:
            sentry_sdk.add_breadcrumb(
                category="nltk",
                message="Checking NLTK resources",
                level="info"
            )
            
            # Try to find punkt and stopwords
            try:
                nltk.data.find('tokenizers/punkt')
                logger.info("Found NLTK punkt resource")
                
                # Check specifically for punkt_tab resource
                try:
                    nltk.data.find('tokenizers/punkt/punkt_tab')
                    logger.info("Found NLTK punkt_tab resource")
                    sentry_sdk.add_breadcrumb(
                        category="nltk",
                        message="punkt_tab resource found",
                        level="info"
                    )
                except LookupError as e:
                    logger.warning(f"punkt_tab resource not found: {e}")
                    sentry_sdk.add_breadcrumb(
                        category="nltk",
                        message=f"punkt_tab resource not found: {e}",
                        level="warning"
                    )
                    self.use_fallback_tokenizer = True
            except LookupError:
                logger.warning("punkt resource not found")
                self.use_fallback_tokenizer = True
            
            try:
                nltk.data.find('corpora/stopwords')
                logger.info("Found NLTK stopwords resource")
            except LookupError:
                logger.warning("stopwords resource not found")
                
            # Download resources if not found
            if self.use_fallback_tokenizer:
                logger.info("Downloading NLTK resources")
                sentry_sdk.add_breadcrumb(
                    category="nltk",
                    message="Downloading NLTK resources",
                    level="info"
                )
                
                try:
                    # First try punkt_tab directly (for NLTK 3.8.2+)
                    nltk.download('punkt_tab')
                    self.use_fallback_tokenizer = False
                    sentry_sdk.add_breadcrumb(
                        category="nltk",
                        message="Downloaded punkt_tab",
                        level="info"
                    )
                except Exception as e:
                    logger.warning(f"Failed to download punkt_tab: {e}")
                    sentry_sdk.add_breadcrumb(
                        category="nltk",
                        message=f"Failed to download punkt_tab: {e}",
                        level="warning"
                    )
                    
                    # Fall back to punkt (for older NLTK versions)
                    try:
                        nltk.download('punkt')
                        logger.info("Downloaded punkt")
                        
                        # Check if punkt_tab is now available
                        try:
                            nltk.data.find('tokenizers/punkt/punkt_tab')
                            self.use_fallback_tokenizer = False
                            logger.info("punkt_tab is now available after punkt download")
                        except LookupError:
                            logger.warning("punkt_tab still not available after punkt download")
                            self.use_fallback_tokenizer = True
                    except Exception as e:
                        logger.warning(f"Failed to download punkt: {e}")
                        self.use_fallback_tokenizer = True
                
                nltk.download('stopwords')
        except Exception as e:
            logger.error(f"Error initializing NLTK resources: {e}")
            self.use_fallback_tokenizer = True
            sentry_sdk.capture_exception(e)
            sentry_sdk.add_breadcrumb(
                category="nltk",
                message=f"Error initializing NLTK resources: {e}",
                level="error"
            )
        
        # Log final state
        if self.use_fallback_tokenizer:
            logger.info("Using fallback tokenizer")
            sentry_sdk.set_tag("nltk.tokenizer", "fallback")
        else:
            logger.info("Using NLTK tokenizer")
            sentry_sdk.set_tag("nltk.tokenizer", "nltk")

    def tokenize_text(self, text):
        """
        Tokenize text using NLTK if available, otherwise use a simple fallback tokenizer.
        
        Args:
            text (str): The text to tokenize
            
        Returns:
            list: List of tokens
        """
        # Use fallback tokenizer if determined necessary during init
        if self.use_fallback_tokenizer:
            return FALLBACK_TOKENIZER.tokenize(text.lower())
        
        # Try NLTK tokenization, with fallback if it fails
        try:
            return word_tokenize(text.lower())
        except LookupError as e:
            logger.warning(f"NLTK tokenization error: {e}")
            sentry_sdk.capture_message(f"NLTK tokenization error: {e}")
            
            # Update state for future calls
            self.use_fallback_tokenizer = True
            sentry_sdk.set_tag("nltk.tokenizer", "fallback")
            
            # Use fallback tokenizer
            return FALLBACK_TOKENIZER.tokenize(text.lower())
        except Exception as e:
            logger.warning(f"Unexpected tokenization error: {e}")
            return FALLBACK_TOKENIZER.tokenize(text.lower())

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
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_error_callback=lambda retry_state: None
    )
    def analyze_content(self, content: str) -> Dict:
        """
        Analyze content to extract keywords, sentiment, and other useful metadata.
        
        Args:
            content (str): The content to analyze
            
        Returns:
            Dict: Analysis results including keywords, sentiment, entities, and topics
            
        Raises:
            APIError: If OpenAI API call fails
        """
        try:
            sentry_sdk.add_breadcrumb(
                category="analysis",
                message="Starting content analysis",
                level="info"
            )
            
            # Track which type of tokenizer we're using in Sentry
            sentry_sdk.set_context("tokenizer", {
                "type": "fallback" if self.use_fallback_tokenizer else "nltk",
                "content_length": len(content)
            })
            
            # First, perform basic analysis using NLTK or fallback tokenizer
            try:
                # Use the tokenize_text method which handles fallback
                words = self.tokenize_text(content.lower())
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message=f"Tokenization successful: {len(words)} tokens",
                    level="info"
                )
            except Exception as e:
                logger.error(f"Error during tokenization: {str(e)}")
                sentry_sdk.capture_exception(e)
                # Use a very simple fallback tokenization as a last resort
                words = re.findall(r'\w+', content.lower())
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message=f"Using emergency fallback tokenization after error: {len(words)} tokens",
                    level="warning"
                )
            
            # Get stopwords if available, otherwise use a simple list
            try:
                stop_words = set(stopwords.words('english'))
            except Exception as e:
                logger.warning(f"Error getting stopwords: {str(e)}")
                # Simple fallback stopwords
                stop_words = set(['the', 'a', 'an', 'and', 'in', 'on', 'at', 'to', 'for', 'of', 'with'])
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message="Using fallback stopwords",
                    level="warning"
                )
            
            # Filter words
            try:
                filtered_words = [word for word in words if word.isalnum() and word not in stop_words and len(word) > 3]
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message=f"Filtered to {len(filtered_words)} words",
                    level="info"
                )
            except Exception as e:
                logger.error(f"Error during word filtering: {str(e)}")
                sentry_sdk.capture_exception(e)
                filtered_words = words  # Use unfiltered words as fallback
            
            # Get word frequency
            try:
                from collections import Counter
                word_counts = Counter(filtered_words)
                keywords_nltk = [word for word, count in word_counts.most_common(10)]
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message="Extracted NLTK keywords successfully",
                    level="info"
                )
            except Exception as e:
                logger.error(f"Error during keyword extraction: {str(e)}")
                sentry_sdk.capture_exception(e)
                keywords_nltk = filtered_words[:10] if len(filtered_words) > 10 else filtered_words
            
            # Track state before OpenAI API call
            sentry_sdk.add_breadcrumb(
                category="analysis",
                message="Preparing to call OpenAI API for advanced analysis",
                level="info"
            )
            
            # Then use OpenAI for more sophisticated analysis
            prompt = f"""Analyze the following content for a LinkedIn post and extract:
            1. Top 5-10 keywords or key phrases
            2. Overall sentiment (positive, negative, or neutral)
            3. Main topics covered
            4. Any entities mentioned (people, companies, products)
            
            Return the analysis in a structured format that can be parsed as JSON.
            
            Content to analyze:
            {content}"""

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a content analysis expert. Extract structured information from text and return it in a JSON-compatible format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent analytical results
                max_tokens=500,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )

            # Extract generated analysis
            analysis_text = response.choices[0].message.content.strip()
            sentry_sdk.add_breadcrumb(
                category="analysis",
                message="OpenAI API call successful",
                level="info"
            )
            
            # Try to extract JSON from the response (if it's formatted as JSON)
            import json
            try:
                # First try to see if the whole response is JSON
                analysis_data = json.loads(analysis_text)
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message="Successfully parsed response as JSON",
                    level="info"
                )
            except json.JSONDecodeError:
                # If not, use regex to try to extract JSON-like structure and parse manually
                logger.info("Couldn't parse response as JSON, using processed output")
                sentry_sdk.add_breadcrumb(
                    category="analysis",
                    message="Using regex-based extraction for non-JSON response",
                    level="warning"
                )
                
                # Fallback to a simpler, regex-based extraction
                keywords_match = re.search(r'keywords?[:\s]+\[([^\]]+)\]', analysis_text, re.IGNORECASE)
                keywords = []
                if keywords_match:
                    keywords_text = keywords_match.group(1)
                    keywords = [k.strip().strip('"\'') for k in keywords_text.split(',')]
                
                sentiment_match = re.search(r'sentiment[:\s]+"?([a-z]+)"?', analysis_text, re.IGNORECASE)
                sentiment = sentiment_match.group(1) if sentiment_match else "neutral"
                
                topics_match = re.search(r'topics?[:\s]+\[([^\]]+)\]', analysis_text, re.IGNORECASE)
                topics = []
                if topics_match:
                    topics_text = topics_match.group(1)
                    topics = [t.strip().strip('"\'') for t in topics_text.split(',')]
                
                entities_match = re.search(r'entities?[:\s]+\[([^\]]+)\]', analysis_text, re.IGNORECASE)
                entities = []
                if entities_match:
                    entities_text = entities_match.group(1)
                    entities = [e.strip().strip('"\'') for e in entities_text.split(',')]
                
                # Create structured analysis data
                analysis_data = {
                    "keywords": keywords or keywords_nltk,
                    "sentiment": sentiment,
                    "topics": topics,
                    "entities": entities
                }
            
            # Combine with NLTK keywords for better coverage
            if "keywords" in analysis_data and keywords_nltk:
                # Add any NLTK keywords not already in the OpenAI keywords
                combined_keywords = list(analysis_data["keywords"])
                for keyword in keywords_nltk:
                    if keyword not in combined_keywords:
                        combined_keywords.append(keyword)
                analysis_data["keywords"] = combined_keywords[:15]  # Limit to 15 keywords
            
            sentry_sdk.add_breadcrumb(
                category="analysis",
                message="Content analysis completed successfully",
                level="info"
            )
            
            return {
                "success": True,
                "data": analysis_data
            }

        except APIError as e:
            logger.error(f"OpenAI API error during content analysis: {str(e)}")
            sentry_sdk.capture_exception(e)
            sentry_sdk.set_context("api_error", {
                "message": str(e),
                "type": "api_error"
            })
            return {
                "success": False,
                "error": f"OpenAI API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in content analysis: {str(e)}")
            logger.error(traceback.format_exc())
            sentry_sdk.capture_exception(e)
            sentry_sdk.set_context("error_details", {
                "message": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            return {
                "success": False,
                "error": f"Unexpected error in content analysis: {str(e)}"
            } 