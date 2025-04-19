import os
import logging
import requests
from typing import List, Dict, Optional
import tempfile
from urllib.parse import urlparse
import json

logger = logging.getLogger(__name__)

class PexelsFetcher:
    BASE_URL = "https://api.pexels.com/videos"
    MIN_DURATION = 3  # Minimum video duration in seconds
    MAX_DURATION = 10  # Maximum video duration in seconds
    
    def __init__(self):
        """Initialize the PexelsFetcher with API key from environment."""
        self.api_key = os.getenv('PEXELS_API_KEY')
        if not self.api_key:
            logger.error("PEXELS_API_KEY not found in environment variables")
            raise ValueError("PEXELS_API_KEY environment variable is required")
        
        # Create a temporary directory for video downloads
        try:
            # First try using tempfile
            self.temp_dir = tempfile.mkdtemp(prefix='pexels_')
            # Test if directory is writable
            test_file = os.path.join(self.temp_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"Created temporary directory at {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise

# Create a singleton instance that will be initialized when first accessed
_pexels_fetcher = None

def get_pexels_fetcher():
    """Get the singleton instance of PexelsFetcher, initializing it if necessary."""
    global _pexels_fetcher
    if _pexels_fetcher is None:
        _pexels_fetcher = PexelsFetcher()
    return _pexels_fetcher

    def search_videos(self, query: str, min_duration: int = MIN_DURATION, 
                     max_duration: int = MAX_DURATION, per_page: int = 5) -> List[Dict]:
        """
        Search for videos on Pexels matching the query.
        
        Args:
            query: Search term
            min_duration: Minimum video duration in seconds
            max_duration: Maximum video duration in seconds
            per_page: Number of results to return
            
        Returns:
            List of video metadata dictionaries
        """
        try:
            headers = {'Authorization': self.api_key}
            params = {
                'query': query,
                'per_page': per_page * 2,  # Request more to filter better
                'size': 'medium',  # Balance between quality and download speed
                'orientation': 'landscape'  # Prefer landscape videos for professional look
            }
            
            logger.info(f"Searching Pexels for videos with query: '{query}'")
            response = requests.get(f"{self.BASE_URL}/search", headers=headers, params=params)
            response.raise_for_status()
            
            videos = response.json().get('videos', [])
            logger.info(f"Found {len(videos)} total videos for query: '{query}'")
            
            # Filter videos by duration and get best quality within size limit
            filtered_videos = []
            for video in videos:
                duration = video.get('duration')
                if min_duration <= duration <= max_duration:
                    # Get the medium quality video file
                    video_files = video.get('video_files', [])
                    
                    # Prefer HD quality first, then standard
                    medium_quality = next(
                        (f for f in video_files if f['quality'] == 'hd' and f['width'] <= 1920 and f['width'] >= 720),
                        next(
                            (f for f in video_files if f['quality'] == 'sd' and f['width'] >= 640),
                            video_files[0] if video_files else None
                        )
                    )
                    
                    if medium_quality:
                        filtered_videos.append({
                            'id': video['id'],
                            'duration': duration,
                            'url': medium_quality['link'],
                            'width': medium_quality['width'],
                            'height': medium_quality['height']
                        })
            
            # Sort by higher resolution and better duration
            filtered_videos.sort(key=lambda x: (x['width'], -abs(x['duration'] - 6)), reverse=True)
            
            logger.info(f"Found {len(filtered_videos)} suitable videos for query: '{query}'")
            if filtered_videos:
                logger.info(f"Top video: {filtered_videos[0]['width']}x{filtered_videos[0]['height']}, {filtered_videos[0]['duration']}s")
            return filtered_videos[:per_page]  # Return only the top ones
            
        except Exception as e:
            logger.error(f"Error searching Pexels videos: {str(e)}")
            return []

    def download_video(self, video_url: str) -> Optional[str]:
        """
        Download a video from Pexels.
        
        Args:
            video_url: URL of the video to download
            
        Returns:
            Path to downloaded video file or None if download fails
        """
        try:
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            # Extract filename from URL or generate one
            url_path = urlparse(video_url).path
            filename = os.path.basename(url_path) or f"pexels_video_{hash(video_url)}.mp4"
            
            # Ensure temp directory exists
            if not os.path.exists(self.temp_dir):
                # If initial temp_dir doesn't exist, create a new one
                self.temp_dir = os.path.join('/tmp', f'pexels_{os.getpid()}')
                os.makedirs(self.temp_dir, exist_ok=True)
                logger.info(f"Created new temp directory: {self.temp_dir}")
            
            local_path = os.path.join(self.temp_dir, filename)
            
            # Download the file in chunks
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Successfully downloaded video to {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Error downloading video from {video_url}: {str(e)}")
            return None

    def fetch_relevant_videos(self, keywords: List[str], count: int = 2) -> List[str]:
        """
        Fetch relevant videos based on keywords with enhanced selection.
        
        Args:
            keywords: List of keywords to search for
            count: Number of videos to fetch
            
        Returns:
            List of paths to downloaded video files
        """
        video_paths = []
        searched_keywords = set()
        
        logger.info(f"Fetching relevant videos for keywords: {keywords}")
        
        # Try to get one video for each unique keyword
        for keyword in keywords:
            if len(video_paths) >= count:
                break
                
            # Avoid duplicate searches
            if keyword in searched_keywords:
                continue
                
            searched_keywords.add(keyword)
            videos = self.search_videos(keyword, per_page=3)
            
            # Try to download at least one video per keyword
            if videos:
                logger.info(f"Downloading video for keyword '{keyword}': {videos[0]['width']}x{videos[0]['height']}, {videos[0]['duration']}s")
                video_path = self.download_video(videos[0]['url'])
                if video_path:
                    video_paths.append(video_path)
        
        # If we still need more videos, try other videos from the searches
        if len(video_paths) < count:
            for keyword in keywords:
                if len(video_paths) >= count:
                    break
                
                videos = self.search_videos(keyword, per_page=3)
                for i, video in enumerate(videos):
                    # Skip the first one as we already tried it
                    if i == 0:
                        continue
                        
                    if len(video_paths) >= count:
                        break
                        
                    logger.info(f"Downloading additional video for keyword '{keyword}': {video['width']}x{video['height']}, {video['duration']}s")
                    video_path = self.download_video(video['url'])
                    if video_path:
                        video_paths.append(video_path)
        
        logger.info(f"Successfully fetched {len(video_paths)} videos")
        return video_paths

    def cleanup(self):
        """Remove all temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}") 