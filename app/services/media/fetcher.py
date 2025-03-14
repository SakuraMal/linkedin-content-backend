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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class MediaFetcher:
    def __init__(self):
        """Initialize the MediaFetcher service."""
        self.temp_dir = tempfile.mkdtemp(prefix='media_')
        self.unsplash_api_key = os.getenv('UNSPLASH_ACCESS_KEY')
        if not self.unsplash_api_key:
            logger.error("UNSPLASH_ACCESS_KEY not found in environment variables")
            
        logger.info("Initialized MediaFetcher")

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
        """Extract visually descriptive keywords from content, categorized by type."""
        try:
            prompt = f"""Analyze this content and extract highly specific visual search terms, categorized into two types:

            1. Static subjects (for images):
               - Concrete objects, scenes, or concepts
               - Include descriptive adjectives (e.g. 'modern office' instead of just 'office')
               - Consider metaphorical representations of abstract concepts
               - Include emotional/mood descriptors when relevant
            
            2. Dynamic subjects (for videos):
               - Actions, processes, or movements
               - Include context and setting
               - Consider human interactions or behaviors
               - Focus on visual aspects that work well in motion
            
            Guidelines:
            - Be very specific (e.g. 'business team brainstorming' vs just 'team')
            - Include visual style hints (e.g. 'minimalist', 'vibrant', 'professional')
            - Consider the content's tone and industry context
            - Combine concepts for more specific results
            
            Return only a JSON object with:
            - static_keywords: list of detailed image search terms (max {max_keywords//2 + 1})
            - dynamic_keywords: list of detailed video search terms (max {max_keywords//2})
            
            Content: {content}"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",  # Using GPT-4 for better understanding and specificity
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            keywords = json.loads(response.choices[0].message.content)
            logger.info(f"Extracted detailed keywords by type: {keywords}")
            return keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}\n{traceback.format_exc()}")
            # Fallback to simple content splitting
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
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Successfully downloaded file to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading from {url}: {str(e)}")
            return None

    def fetch_media(self, content: str, duration: float = 15.0) -> Dict[str, List[str]]:
        """
        Fetch media assets for video generation with smart content mixing.
        
        Args:
            content: Text content to generate media for
            duration: Target video duration in seconds
            
        Returns:
            Dictionary containing lists of image and video file paths
        """
        try:
            # Analyze content to determine optimal media distribution
            distribution = self.analyze_content_type(content)
            image_ratio = distribution["image_ratio"]
            video_ratio = distribution["video_ratio"]
            
            # Calculate number of media items based on content analysis
            total_slots = duration / 3  # Each media item gets ~3 seconds
            num_images = min(max(3, round(total_slots * image_ratio)), 7)
            num_videos = min(max(1, round(total_slots * video_ratio)), 3)
            
            logger.info(f"Content-based distribution - Images: {num_images} ({image_ratio:.1%}), Videos: {num_videos} ({video_ratio:.1%})")
            logger.info(f"Distribution reasoning: {distribution.get('reasoning', 'Not provided')}")
            
            # Extract keywords categorized by type
            keywords = self.extract_keywords(content)
            if not keywords:
                logger.error("No keywords extracted from content")
                return {'images': [], 'videos': []}
            
            # Fetch images using static keywords
            image_paths = []
            for keyword in keywords["static_keywords"]:
                if len(image_paths) >= num_images:
                    break
                    
                urls = self.fetch_unsplash_images(keyword, count=2)
                for url in urls:
                    if len(image_paths) >= num_images:
                        break
                        
                    image_path = self.download_file(url)
                    if image_path:
                        image_paths.append(image_path)
            
            # Fetch videos using dynamic keywords
            video_paths = pexels_fetcher.fetch_relevant_videos(
                keywords["dynamic_keywords"], 
                count=num_videos
            )
            
            logger.info(f"Successfully fetched {len(image_paths)} images and {len(video_paths)} videos")
            return {
                'images': image_paths,
                'videos': video_paths
            }
            
        except Exception as e:
            logger.error(f"Error fetching media: {str(e)}")
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