import os
import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse
import tempfile
import traceback
import json
import openai
from .pexels_fetcher import pexels_fetcher
import random

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class MediaFetcher:
    def __init__(self):
        """Initialize the MediaFetcher service."""
        # Fix for fly.io: ensure we use a writable directory
        try:
            # First try using the standard temp directory
            self.temp_dir = tempfile.mkdtemp(prefix='media_')
            logger.debug(f"Created temp directory: {self.temp_dir}")
            
            # Test if the directory is writable
            test_file = os.path.join(self.temp_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.debug(f"Temp directory {self.temp_dir} is writable")
        except Exception as e:
            # If standard temp directory fails, try alternatives
            logger.warning(f"Failed to create temp directory with standard method: {str(e)}")
            try:
                # Try /tmp explicitly
                self.temp_dir = os.path.join('/tmp', f'media_{os.getpid()}')
                os.makedirs(self.temp_dir, exist_ok=True)
                
                # Test if directory is writable
                test_file = os.path.join(self.temp_dir, 'test.txt')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.debug(f"Created alternate temp directory: {self.temp_dir}")
            except Exception as alt_e:
                # Last resort: try current directory
                logger.error(f"Failed to create alternate temp directory: {str(alt_e)}")
                self.temp_dir = os.path.join(os.getcwd(), 'tmp_media')
                os.makedirs(self.temp_dir, exist_ok=True)
                logger.debug(f"Created fallback temp directory: {self.temp_dir}")
        
        self.unsplash_api_key = os.getenv('UNSPLASH_ACCESS_KEY')
        if not self.unsplash_api_key:
            logger.error("UNSPLASH_ACCESS_KEY not found in environment variables")
            
        logger.info(f"Initialized MediaFetcher with temp directory: {self.temp_dir}")

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client."""
        if not hasattr(self, '_openai_client'):
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.error("OPENAI_API_KEY not found in environment variables")
                raise ValueError("OPENAI_API_KEY environment variable is required")
            
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    def analyze_content_type(self, content: str) -> Dict[str, float]:
        """
        Analyze content to determine optimal media distribution.
        Returns ratio recommendations for images vs videos.
        """
        try:
            prompt = f"""Analyze this content and determine the optimal ratio of static images vs video clips.
            Consider factors like:
            - Action and movement descriptions
            - Process or sequential explanations
            - Static concepts or descriptions
            - Technical vs visual content
            
            Return only a JSON object with these fields:
            - image_ratio: float between 0.4 and 0.8
            - video_ratio: float between 0.2 and 0.6
            - reasoning: brief explanation
            
            Content: {content}"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Content analysis result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing content type: {str(e)}")
            # Default to 70/30 split if analysis fails
            return {
                "image_ratio": 0.7,
                "video_ratio": 0.3,
                "reasoning": "Using default ratio due to analysis error"
            }

    def extract_keywords(self, content: str, max_keywords: int = 5) -> Dict[str, List[str]]:
        """Extract highly detailed, visually descriptive keywords from content for better search results."""
        try:
            # Enhanced prompt with more specific instructions for visual richness
            prompt = f"""Analyze this content and generate highly detailed, visually descriptive search terms that would yield professional stock photos and videos.

            1. For static visuals (images):
               - Create sophisticated multi-part descriptions with 4-6 words each
               - Include specific settings (e.g., "modern glass office with city view" vs just "office")
               - Specify demographics if relevant (e.g., "diverse team of professionals" vs just "team")
               - Add emotional tone (e.g., "confident executive presenting strategy")
               - Include specific lighting/style (e.g., "bright naturally lit workspace")
               - Consider both literal and metaphorical representations

            2. For dynamic visuals (videos):
               - Focus on actions and movements that work well in motion
               - Include specific setting and context details
               - Describe interactions between people or objects
               - Specify camera angles or movements if relevant (e.g., "aerial view of team collaboration")
               - Include tempo descriptions (e.g., "time-lapse of busy office workflow")

            Professional context guidelines:
            - Use business/professional terminology appropriate to the content
            - Prioritize sophisticated, premium-looking imagery descriptions
            - For abstract concepts, create concrete visual representations
            - Consider the industry, setting, and tone of the content

            Return only a JSON object with:
            - static_keywords: list of detailed image search terms (max {max_keywords//2 + 1})
            - dynamic_keywords: list of detailed video search terms (max {max_keywords//2})
            
            Content: {content}"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300  # Increased to allow for more detailed descriptions
            )
            
            keywords = json.loads(response.choices[0].message.content)
            
            # Log the enhanced keywords
            logger.info(f"Enhanced visual search terms generated:")
            for category, terms in keywords.items():
                for term in terms:
                    logger.info(f"  - {category}: {term}")
            
            return keywords
            
        except Exception as e:
            logger.error(f"Error extracting enhanced keywords: {str(e)}\n{traceback.format_exc()}")
            # Fallback to simple content splitting as before
            words = content.split()[:max_keywords]
            return {
                "static_keywords": words[:3],
                "dynamic_keywords": words[3:5]
            }

    def fetch_unsplash_images(self, query: str, count: int = 3) -> List[str]:
        """Fetch image URLs from Unsplash with enhanced search parameters."""
        try:
            headers = {'Authorization': f'Client-ID {self.unsplash_api_key}'}
            params = {
                'query': query,
                'per_page': count * 2,  # Fetch more options to filter
                'orientation': 'squarish',
                'content_filter': 'high',
                'order_by': 'relevant'
            }
            
            response = requests.get(
                'https://api.unsplash.com/search/photos',
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            # Filter for higher quality images
            photos = response.json()['results']
            filtered_photos = sorted(
                photos,
                key=lambda x: (x['likes'] + x['downloads'] if 'downloads' in x else 0),
                reverse=True
            )[:count]
            
            urls = [photo['urls']['regular'] for photo in filtered_photos]
            logger.info(f"Found {len(urls)} quality images for query: {query}")
            return urls
            
        except Exception as e:
            logger.error(f"Error fetching from Unsplash: {str(e)}")
            return []

    def download_file(self, url: str) -> Optional[str]:
        """Download a file from a URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Try to get extension from URL or content type
            url_path = urlparse(url).path
            ext = os.path.splitext(url_path)[1]
            if not ext:
                content_type = response.headers.get('content-type', '')
                ext = {
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'video/mp4': '.mp4'
                }.get(content_type, '.jpg')
            
            # Save file
            filename = f"media_{hash(url)}{ext}"
            filepath = os.path.join(self.temp_dir, filename)
            
            # Ensure the directory exists (in case it was deleted after initialization)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Log the full details for debugging
            logger.debug(f"Downloading from {url} to {filepath}")
            
            # Save the file
            with open(filepath, 'wb') as f:
                f.write(response.content)
                
            # Verify file was written successfully
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                logger.debug(f"Successfully downloaded file to {filepath} (size: {os.path.getsize(filepath)} bytes)")
                return filepath
            else:
                logger.error(f"File download failed: File exists: {os.path.exists(filepath)}, Size: {os.path.getsize(filepath) if os.path.exists(filepath) else 0}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading from {url}: {str(e)}")
            logger.debug(f"Exception traceback: {traceback.format_exc()}")
            return None

    def fetch_media(self, content: str, duration: float = 15.0) -> Dict[str, List[str]]:
        """
        Fetch media assets for video generation with smart content analysis.
        
        Args:
            content: Text content to generate media for
            duration: Target video duration in seconds
            
        Returns:
            Dictionary containing lists of image and video file paths
        """
        try:
            # Step 1: Analyze content to determine optimal media distribution
            distribution = self.analyze_content_type(content)
            image_ratio = distribution["image_ratio"]
            video_ratio = distribution["video_ratio"]
            
            # Calculate number of media items based on content analysis
            total_slots = duration / 3  # Each media item gets ~3 seconds
            num_images = min(max(3, round(total_slots * image_ratio)), 7)
            num_videos = min(max(1, round(total_slots * video_ratio)), 3)
            
            logger.info(f"Content-based distribution - Images: {num_images} ({image_ratio:.1%}), Videos: {num_videos} ({video_ratio:.1%})")
            logger.info(f"Distribution reasoning: {distribution.get('reasoning', 'Not provided')}")
            
            # Step 2: Extract highly detailed and visually descriptive keywords
            keywords = self.extract_keywords(content)
            if not keywords:
                logger.error("No keywords extracted from content")
                return {'images': [], 'videos': []}
            
            # Step 3: Fetch images with enhanced descriptive terms
            image_paths = []
            for keyword in keywords["static_keywords"]:
                if len(image_paths) >= num_images:
                    break
                    
                logger.info(f"Searching for images with enhanced term: '{keyword}'")
                urls = self.fetch_unsplash_images(keyword, count=2)
                for url in urls:
                    if len(image_paths) >= num_images:
                        break
                        
                    image_path = self.download_file(url)
                    if image_path:
                        image_paths.append(image_path)
            
            # Step 4: Fetch videos with enhanced search terms
            video_paths = pexels_fetcher.fetch_relevant_videos(
                keywords["dynamic_keywords"], 
                count=num_videos
            )
            
            logger.info(f"Successfully fetched {len(image_paths)} images and {len(video_paths)} videos with enhanced descriptive terms")
            return {
                'images': image_paths,
                'videos': video_paths
            }
            
        except Exception as e:
            logger.error(f"Error fetching media: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {'images': [], 'videos': []}

    def cleanup(self):
        """Remove all temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

# Create a singleton instance
media_fetcher = MediaFetcher() 