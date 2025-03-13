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
                        "content": f"You are a keyword extractor. Extract the {max_keywords} most visually relevant keywords or phrases from the text. Return only the keywords, separated by commas, no explanations."
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
            return keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return the first few words of content as fallback
            return [content.split()[:max_keywords][0]]

    def fetch_unsplash_images(self, query: str, count: int = 3) -> List[str]:
        """Fetch image URLs from Unsplash based on query."""
        try:
            logger.info(f"Fetching {count} images from Unsplash for query: {query}")
            
            if not self.unsplash_api_key:
                error_msg = "Unsplash API key is not set"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            url = f"https://api.unsplash.com/photos/random"
            headers = {"Authorization": f"Client-ID {self.unsplash_api_key}"}
            params = {
                "query": query,
                "count": count,
                "orientation": "landscape"
            }
            
            logger.debug(f"Making request to Unsplash API: {url}")
            logger.debug(f"Request params: {json.dumps(params, indent=2)}")
            
            response = requests.get(url, headers=headers, params=params)
            logger.info(f"Unsplash API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Unsplash API error response: {response.text}")
                response.raise_for_status()
            
            photos = response.json()
            logger.debug(f"Unsplash API response: {json.dumps(photos, indent=2)}")
            
            urls = [photo["urls"]["regular"] for photo in photos]
            logger.info(f"Successfully fetched {len(urls)} image URLs: {urls}")
            return urls
            
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
            
            # Calculate number of images based on duration (1 image per 2 seconds)
            num_images = max(5, round(duration / 2))
            logger.info(f"Calculated number of images needed: {num_images}")
            
            # Extract keywords for better image search
            keywords = self.extract_keywords(content)
            if not keywords:
                logger.warning("No keywords extracted, using full content")
                keywords = [content]
            
            # Fetch images for each keyword
            all_image_urls = []
            images_per_keyword = max(2, round(num_images / len(keywords)))
            
            for keyword in keywords:
                image_urls = self.fetch_unsplash_images(keyword, count=images_per_keyword)
                all_image_urls.extend(image_urls)
            
            # Ensure we have enough images
            while len(all_image_urls) < num_images and keywords:
                # Try to fetch more images with the first keyword
                more_urls = self.fetch_unsplash_images(keywords[0], count=num_images - len(all_image_urls))
                all_image_urls.extend(more_urls)
                if not more_urls:
                    break
            
            if not all_image_urls:
                error_msg = f"No images found for content: {content}"
                logger.error(error_msg)
                return {"images": [], "error": error_msg}
            
            # Download all images
            image_paths = []
            for url in all_image_urls[:num_images]:  # Limit to required number of images
                image_path = self.download_file(url, prefix='img_')
                if image_path:
                    image_paths.append(image_path)
            
            logger.info(f"Successfully fetched {len(image_paths)} images: {image_paths}")
            return {"images": image_paths}
            
        except Exception as e:
            error_msg = f"Error fetching media: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"images": [], "error": error_msg}

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