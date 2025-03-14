import os
import requests
import logging
from typing import List, Dict
from urllib.parse import urlparse
import tempfile
import traceback
import json
import openai

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class MediaFetcher:
    def __init__(self):
        """Initialize the MediaFetcher service."""
        self.temp_dir = tempfile.mkdtemp(prefix='video_gen_')
        self.unsplash_api_key = os.getenv('UNSPLASH_ACCESS_KEY')
        self._openai_client = None
        if not self.unsplash_api_key:
            logger.error("UNSPLASH_ACCESS_KEY not set. Unsplash image fetching will not work.")
        else:
            logger.info(f"Initialized MediaFetcher with Unsplash API key: {self.unsplash_api_key[:5]}...")
        logger.info(f"Initialized MediaFetcher with temp directory: {self.temp_dir}")

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    def extract_keywords(self, content: str, max_keywords: int = 3) -> List[str]:
        """Extract relevant keywords from content for image search."""
        try:
            logger.info(f"Extracting keywords from content: {content}")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a visual keyword extractor. Your task is to extract keywords that will produce good visual search results. "
                            f"Extract exactly {max_keywords} visually descriptive keywords or phrases from the text. "
                            "Focus on concrete objects, scenes, or concepts that would make good photographs. "
                            "Avoid abstract concepts unless they have clear visual representations. "
                            "Return only the keywords, separated by commas, no explanations. "
                            "Example good keywords: 'artificial intelligence laboratory, data scientist working, modern research facility'"
                        )
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            keywords = [k.strip() for k in response.choices[0].message.content.split(',')]
            logger.info(f"Extracted keywords: {keywords}")
            return keywords[:max_keywords]  # Ensure we don't exceed max_keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a safe fallback that should produce decent images
            return ["modern office", "technology", "business professional"]

    def fetch_unsplash_images(self, query: str, count: int = 3, retries: int = 2) -> List[str]:
        """Fetch image URLs from Unsplash based on query."""
        try:
            logger.info(f"Fetching {count} images from Unsplash for query: {query}")
            
            if not self.unsplash_api_key:
                error_msg = "Unsplash API key is not set"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Try to get more images than needed to have some buffer
            buffer_count = min(30, count * 2)  # Don't request too many
            
            url = f"https://api.unsplash.com/photos/random"
            headers = {"Authorization": f"Client-ID {self.unsplash_api_key}"}
            params = {
                "query": query,
                "count": buffer_count,
                "orientation": "landscape",
                "content_filter": "high"
            }
            
            logger.debug(f"Making request to Unsplash API: {url}")
            logger.debug(f"Request params: {json.dumps(params, indent=2)}")
            
            urls = []
            attempts = 0
            
            while len(urls) < count and attempts < retries:
                try:
                    response = requests.get(url, headers=headers, params=params)
                    logger.info(f"Unsplash API response status: {response.status_code}")
                    
                    if response.status_code != 200:
                        logger.error(f"Unsplash API error response: {response.text}")
                        response.raise_for_status()
                    
                    photos = response.json()
                    logger.debug(f"Unsplash API response: {json.dumps(photos, indent=2)}")
                    
                    new_urls = [photo["urls"]["regular"] for photo in photos]
                    urls.extend(new_urls)
                    
                except Exception as e:
                    logger.error(f"Error on attempt {attempts + 1}: {str(e)}")
                    attempts += 1
                    continue
            
            # Ensure we have unique URLs
            urls = list(dict.fromkeys(urls))
            logger.info(f"Successfully fetched {len(urls)} unique image URLs")
            return urls[:count]  # Return only the number of images requested
            
        except Exception as e:
            logger.error(f"Error fetching Unsplash images: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if isinstance(e, requests.exceptions.RequestException):
                logger.error(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response'}")
            return []

    def download_file(self, url: str, prefix: str = '') -> str:
        """Download a file from URL and save it locally."""
        try:
            logger.info(f"Downloading file from URL: {url}")
            response = requests.get(url, stream=True)
            
            if response.status_code != 200:
                logger.error(f"Failed to download file. Status code: {response.status_code}")
                logger.error(f"Response content: {response.text}")
                response.raise_for_status()
            
            # Get file extension from URL or content type
            content_type = response.headers.get('content-type', '')
            ext = self._get_extension(url, content_type)
            logger.debug(f"Determined file extension: {ext} from content type: {content_type}")
            
            # Create temporary file
            fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=ext, dir=self.temp_dir)
            logger.debug(f"Created temporary file: {temp_path}")
            
            # Write content to file
            total_size = 0
            with os.fdopen(fd, 'wb') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                    total_size += len(chunk)
            
            logger.info(f"Successfully downloaded file to {temp_path} (size: {total_size} bytes)")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _get_extension(self, url: str, content_type: str) -> str:
        """Get file extension from URL or content type."""
        # Try to get extension from URL
        path = urlparse(url).path
        ext = os.path.splitext(path)[1]
        if ext:
            return ext
            
        # If no extension in URL, try content type
        if 'image/jpeg' in content_type:
            return '.jpg'
        elif 'image/png' in content_type:
            return '.png'
        elif 'audio/mpeg' in content_type:
            return '.mp3'
        else:
            return '.tmp'

    def fetch_media(self, content: str, duration: int = 10) -> Dict[str, List[str]]:
        """Fetch media assets for video generation."""
        try:
            logger.info(f"Starting media fetching for content: {content}")
            
            # Calculate number of images needed with both minimum and maximum limits
            MIN_IMAGES = 5
            MAX_IMAGES = 10  # Maximum number of images to prevent excessive fetching
            calculated_images = round(duration / 2)
            num_images = max(MIN_IMAGES, min(MAX_IMAGES, calculated_images))
            logger.info(f"Calculated number of images needed: {num_images} (duration: {duration}s, calculated: {calculated_images})")
            
            # Extract keywords for better image search
            keywords = self.extract_keywords(content, max_keywords=5)  # Increased max_keywords for better coverage
            if not keywords:
                logger.warning("No keywords extracted, using fallback keywords")
                keywords = ["modern office", "technology", "business professional"]
            
            # Initialize image collection
            all_image_urls = []
            
            # First pass: Try each keyword individually
            for keyword in keywords:
                if len(all_image_urls) >= num_images:
                    break
                    
                remaining = num_images - len(all_image_urls)
                image_urls = self.fetch_unsplash_images(keyword, count=remaining)
                
                # Only add new, unique URLs
                new_urls = [url for url in image_urls if url not in all_image_urls]
                all_image_urls.extend(new_urls)
                logger.info(f"Fetched {len(new_urls)} new images for keyword '{keyword}'")
            
            # Second pass: Try combinations of keywords if we need more images
            if len(all_image_urls) < num_images and len(keywords) >= 2:
                for i in range(len(keywords) - 1):
                    if len(all_image_urls) >= num_images:
                        break
                        
                    for j in range(i + 1, len(keywords)):
                        if len(all_image_urls) >= num_images:
                            break
                            
                        combined_query = f"{keywords[i]} {keywords[j]}"
                        remaining = num_images - len(all_image_urls)
                        more_urls = self.fetch_unsplash_images(combined_query, count=remaining)
                        
                        # Only add new, unique URLs
                        new_urls = [url for url in more_urls if url not in all_image_urls]
                        all_image_urls.extend(new_urls)
                        logger.info(f"Fetched {len(new_urls)} new images for combined query '{combined_query}'")
            
            # Final pass: Use fallback queries if we still need more images
            if len(all_image_urls) < num_images:
                # Extract main topic or subject from the content for more relevant fallbacks
                fallback_response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "Extract the main topic or subject from this text in 2-3 words, focusing on what would make good background images."
                        },
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    temperature=0.3,
                    max_tokens=20
                )
                main_topic = fallback_response.choices[0].message.content.strip()
                
                fallback_queries = [
                    f"{main_topic} professional",
                    f"{main_topic} modern",
                    "modern business",
                    "technology workspace",
                    "professional office"
                ]
                
                for query in fallback_queries:
                    if len(all_image_urls) >= num_images:
                        break
                        
                    remaining = num_images - len(all_image_urls)
                    more_urls = self.fetch_unsplash_images(query, count=remaining)
                    
                    # Only add new, unique URLs
                    new_urls = [url for url in more_urls if url not in all_image_urls]
                    all_image_urls.extend(new_urls)
                    logger.info(f"Fetched {len(new_urls)} fallback images for query '{query}'")
            
            # Final check and warning
            if len(all_image_urls) < MIN_IMAGES:
                logger.warning(f"Could only fetch {len(all_image_urls)} unique images out of minimum {MIN_IMAGES} required")
            
            if not all_image_urls:
                error_msg = f"No images found for content: {content}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Download all images
            logger.info(f"Downloading {len(all_image_urls)} images")
            image_paths = []
            for i, url in enumerate(all_image_urls):
                path = self.download_file(url, prefix=f'img_{i}_')
                if path:
                    image_paths.append(path)
            
            return {
                'images': image_paths
            }
            
        except Exception as e:
            logger.error(f"Error in fetch_media: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def cleanup(self):
        """Clean up temporary files."""
        try:
            import shutil
            logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir)
            logger.info(f"Successfully cleaned up temporary directory")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

# Create singleton instance
media_fetcher = MediaFetcher() 