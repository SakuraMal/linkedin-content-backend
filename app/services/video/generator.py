import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
from redis import Redis
from ..media.fetcher import media_fetcher
from ..media.processor import media_processor
from ..media.audio import audio_generator
from ..media.text_processor import text_processor
from .storage import storage_service
from ...models.video import VideoRequest
from ..storage.image_storage import image_storage_service
import traceback
import math
import os
import shutil
import tempfile
import psutil
import requests
import openai
from moviepy.video.VideoClip import ColorClip
from ...utils.feature_flag import is_feature_enabled
from .caption_renderer import CaptionRenderer
import time
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class VideoGenerator:
    STEPS = {
        'initialized': {'step': 1, 'message': 'Initializing video generation'},
        'fetching_user_images': {'step': 2, 'message': 'Fetching user-provided images'},
        'user_images_fetched': {'step': 2, 'message': 'User images fetched successfully'},
        'media_fetching': {'step': 2, 'message': 'Collecting media assets'},
        'media_fetched': {'step': 2, 'message': 'Media assets collected'},
        'audio_generating': {'step': 3, 'message': 'Generating audio narration'},
        'audio_generated': {'step': 3, 'message': 'Audio narration generated'},
        'processing_media': {'step': 4, 'message': 'Processing media assets'},
        'media_processed': {'step': 4, 'message': 'Media assets processed'},
        'combining': {'step': 5, 'message': 'Combining audio and video'},
        'combined': {'step': 5, 'message': 'Audio and video combined'},
        'uploading': {'step': 6, 'message': 'Uploading to cloud storage'},
        'completed': {'step': 6, 'message': 'Video generation completed'},
        'failed': {'step': 0, 'message': 'Video generation failed'}
    }

    def __init__(self):
        """Initialize the VideoGenerator service."""
        self._openai_client = None
        logger.info("VideoGenerator initialized")

    @property
    def openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is not set")
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    def update_job_status(self, redis_client: Redis, job_id: str, status: str, progress: int = None, video_url: str = None, error: str = None) -> None:
        """Update job status in Redis."""
        try:
            logger.debug(f"Updating job {job_id} status to {status} (progress: {progress}, error: {error})")
            job_data = redis_client.get(f"job:{job_id}:status")
            if not job_data:
                logger.error(f"No job data found for {job_id}")
                return

            job_info = json.loads(job_data)
            current_step = self.STEPS.get(status, {'step': 0, 'message': 'Unknown state'})
            
            # Map the status to our simplified format
            status_mapping = {
                "initialized": "pending",
                "fetching_user_images": "generating",
                "media_fetching": "generating",
                "media_fetched": "generating",
                "audio_generating": "generating",
                "audio_generated": "generating",
                "processing_media": "generating",
                "media_processed": "generating",
                "combining": "generating",
                "combined": "generating",
                "uploading": "generating",
                "completed": "completed",
                "failed": "error"
            }
            
            # Update job info with simplified status
            job_info.update({
                "status": status_mapping.get(status, "error"),
                "step": current_step['step'],
                "step_message": current_step['message'],
                "updated_at": datetime.utcnow().isoformat()
            })

            if progress is not None:
                job_info["progress"] = progress
            if video_url is not None:
                job_info["video_url"] = video_url
            if error is not None:
                job_info["error"] = error

            redis_client.set(
                f"job:{job_id}:status",
                json.dumps(job_info)
            )
            logger.debug(f"Successfully updated job status in Redis: {job_info}")
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def fetch_user_images(self, user_image_ids: list[str], request_data) -> list[str]:
        """
        Fetch user-uploaded images based on their IDs.
        
        Args:
            user_image_ids: List of image IDs
            request_data: Optional request data that might contain stock media URLs
            
        Returns:
            List of image file paths
        """
        logger.info(f"Fetching {len(user_image_ids)} user-uploaded images")
        image_files = []
        
        # Extract stock media URLs from request if available
        stock_media_urls = {}
        
        # Check for stockMediaUrls (frontend naming convention)
        if request_data and hasattr(request_data, '__dict__'):
            # Safely check if 'stockMediaUrls' exists in __dict__ and is not None
            stock_media_urls_dict = request_data.__dict__.get('stockMediaUrls')
            if stock_media_urls_dict is not None:
                logger.info(f"Found stockMediaUrls in request_data.__dict__ with {len(stock_media_urls_dict)} entries")
                stock_media_urls = stock_media_urls_dict
            # Check for stockImageUrls (backend naming convention)
            elif 'stockImageUrls' in request_data.__dict__ and request_data.__dict__['stockImageUrls'] is not None:
                logger.info(f"Found stockImageUrls in request_data.__dict__ with {len(request_data.__dict__['stockImageUrls'])} entries")
                stock_media_urls = request_data.__dict__['stockImageUrls']
        # Check if request_data is a dict and has stockMediaUrls
        elif request_data and isinstance(request_data, dict):
            # Safely check if 'stockMediaUrls' exists and is not None
            if 'stockMediaUrls' in request_data and request_data['stockMediaUrls'] is not None:
                logger.info(f"Found stockMediaUrls in request_data dict with {len(request_data['stockMediaUrls'])} entries")
                stock_media_urls = request_data['stockMediaUrls']
            # Check if request_data is a dict and has stockImageUrls
            elif 'stockImageUrls' in request_data and request_data['stockImageUrls'] is not None:
                logger.info(f"Found stockImageUrls in request_data dict with {len(request_data['stockImageUrls'])} entries")
                stock_media_urls = request_data['stockImageUrls']
        # Check if request_data has model_extra attribute with stockMediaUrls
        elif request_data and hasattr(request_data, 'model_extra'):
            # Safely check if 'stockMediaUrls' exists in model_extra and is not None
            if 'stockMediaUrls' in request_data.model_extra and request_data.model_extra['stockMediaUrls'] is not None:
                logger.info(f"Found stockMediaUrls in request_data.model_extra with {len(request_data.model_extra['stockMediaUrls'])} entries")
                stock_media_urls = request_data.model_extra['stockMediaUrls']
            # Check if request_data has model_extra attribute with stockImageUrls
            elif 'stockImageUrls' in request_data.model_extra and request_data.model_extra['stockImageUrls'] is not None:
                logger.info(f"Found stockImageUrls in request_data.model_extra with {len(request_data.model_extra['stockImageUrls'])} entries")
                stock_media_urls = request_data.model_extra['stockImageUrls']
        # Check if we can get model_dump to extract stockMediaUrls
        elif request_data and hasattr(request_data, 'model_dump'):
            try:
                model_dict = request_data.model_dump()
                if 'stockMediaUrls' in model_dict and model_dict['stockMediaUrls'] is not None:
                    logger.info(f"Found stockMediaUrls in model_dump with {len(model_dict['stockMediaUrls'])} entries")
                    stock_media_urls = model_dict['stockMediaUrls']
                elif 'stockImageUrls' in model_dict and model_dict['stockImageUrls'] is not None:
                    logger.info(f"Found stockImageUrls in model_dump with {len(model_dict['stockImageUrls'])} entries")
                    stock_media_urls = model_dict['stockImageUrls']
            except Exception as e:
                logger.error(f"Error extracting stock URLs from model_dump: {str(e)}")
        
        for image_id in user_image_ids:
            try:
                # Check if it's a stock media ID with a URL in the request
                if image_id.startswith('stock_') and image_id in stock_media_urls:
                    # Use the URL directly from the request
                    stock_url = stock_media_urls[image_id]
                    logger.info(f"Using original stock URL for {image_id}: {stock_url}")
                    
                    # Use media_fetcher's robust download method instead of direct requests
                    local_path = media_fetcher.download_file(stock_url)
                    if local_path:
                        logger.info(f"Successfully downloaded stock media to {local_path}")
                        image_files.append(local_path)
                    else:
                        logger.warning(f"Failed to download stock media from URL: {stock_url}")
                    continue
                    
                # Regular flow: Get image URL from storage
                image_url = image_storage_service.get_image_url(image_id)
                if not image_url:
                    logger.warning(f"Could not find image with ID: {image_id}")
                    continue
                
                # Use media_fetcher for user images too for consistent handling
                local_path = media_fetcher.download_file(image_url)
                if local_path:
                    logger.info(f"Successfully downloaded user image {image_id} to {local_path}")
                    image_files.append(local_path)
                else:
                    logger.warning(f"Failed to download user image from URL: {image_url}")
                
            except Exception as e:
                logger.error(f"Error fetching image {image_id}: {str(e)}")
        
        logger.info(f"Successfully fetched {len(image_files)} user images")
        return image_files

    def generate_video(self, job_id: str, request: VideoRequest, redis_client: Redis) -> str:
        """
        Generate a video from content description.
        
        Args:
            job_id: Unique identifier for the video generation job
            request: Video generation request data
            redis_client: Redis client instance
            
        Returns:
            str: URL of the generated video
        """
        temp_files = []  # Track temporary files for cleanup
        
        try:
            # Log current memory usage at start
            process = psutil.Process()
            logger.info(f"Starting video job. Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            logger.info(f"Starting video generation for job {job_id}")
            logger.info(f"Request data: {request.model_dump_json()}")
            
            # Update status to processing
            self.update_job_status(redis_client, job_id, "initialized", progress=0)
            
            # Monitor memory usage before fetching images
            logger.info(f"Memory before fetching images: {process.memory_info().rss / 1024 / 1024:.2f} MB")

            # Check if this is a direct stock media request (new approach)
            is_stock_media_direct = False
            stock_image_urls = []
            
            # Try to extract stockImageUrls from model_extra or request.__dict__
            if hasattr(request, 'model_extra') and 'stockImageUrls' in request.model_extra and request.model_extra['stockImageUrls'] is not None:
                stock_image_urls = request.model_extra['stockImageUrls']
                is_stock_media_direct = True
                logger.info(f"Found stockImageUrls in model_extra: {stock_image_urls}")
            # Also check for stockMediaUrls (frontend naming convention)
            elif hasattr(request, 'model_extra') and 'stockMediaUrls' in request.model_extra and request.model_extra['stockMediaUrls'] is not None:
                stock_image_urls = request.model_extra['stockMediaUrls']
                is_stock_media_direct = True
                logger.info(f"Found stockMediaUrls in model_extra: {stock_image_urls}")
            elif hasattr(request, '__dict__'):
                try:
                    # Try to find it in __dict__
                    if 'stockImageUrls' in request.__dict__ and request.__dict__['stockImageUrls'] is not None:
                        stock_image_urls = request.__dict__['stockImageUrls']
                        is_stock_media_direct = True
                        logger.info(f"Found stockImageUrls in __dict__: {stock_image_urls}")
                    # Check for stockMediaUrls field (frontend naming convention)
                    elif 'stockMediaUrls' in request.__dict__ and request.__dict__['stockMediaUrls'] is not None:
                        stock_image_urls = request.__dict__['stockMediaUrls']
                        is_stock_media_direct = True
                        logger.info(f"Found stockMediaUrls in __dict__: {stock_image_urls}")
                    # Also try raw dictionary access (for non-standard attributes)
                    elif isinstance(request.__dict__.get('_obj'), dict) and 'stockImageUrls' in request.__dict__['_obj'] and request.__dict__['_obj']['stockImageUrls'] is not None:
                        stock_image_urls = request.__dict__['_obj']['stockImageUrls']
                        is_stock_media_direct = True
                        logger.info(f"Found stockImageUrls in _obj: {stock_image_urls}")
                    # Try alternative field name 
                    elif isinstance(request.__dict__.get('_obj'), dict) and 'stockMediaUrls' in request.__dict__['_obj'] and request.__dict__['_obj']['stockMediaUrls'] is not None:
                        stock_image_urls = request.__dict__['_obj']['stockMediaUrls']
                        is_stock_media_direct = True
                        logger.info(f"Found stockMediaUrls in _obj: {stock_image_urls}")
                except Exception as e:
                    logger.error(f"Error extracting stock media URLs from __dict__: {str(e)}")
                    
            # Also try the additional data passed to the function
            if not is_stock_media_direct and hasattr(request, 'model_dump'):
                try:
                    request_dict = request.model_dump()
                    if 'stockMediaUrls' in request_dict and request_dict['stockMediaUrls'] is not None:
                        stock_image_urls = request_dict['stockMediaUrls']
                        is_stock_media_direct = True
                        logger.info(f"Found stockMediaUrls in model_dump: {stock_image_urls}")
                except Exception as e:
                    logger.error(f"Error extracting stockMediaUrls from model_dump: {str(e)}")

            # Handle both list and dictionary formats for stockImageUrls safely
            urls_to_download = []
            if stock_image_urls is not None:
                if isinstance(stock_image_urls, dict):
                    logger.info(f"Stock media URLs is a dictionary with {len(stock_image_urls)} items")
                    # It's a map of IDs to URLs, extract just the URLs
                    urls_to_download = list(stock_image_urls.values())
                elif isinstance(stock_image_urls, list):
                    logger.info("Stock media URLs is a list")
                    # It's already a list of URLs
                    urls_to_download = stock_image_urls
            
            # Also look for the skip flag
            skip_user_images = False
            if hasattr(request, 'model_extra') and 'skipUserImageIds' in request.model_extra:
                skip_user_images = request.model_extra['skipUserImageIds']
            elif hasattr(request, '__dict__'):
                try:
                    if 'skipUserImageIds' in request.__dict__:
                        skip_user_images = request.__dict__['skipUserImageIds']
                    elif isinstance(request.__dict__.get('_obj'), dict) and 'skipUserImageIds' in request.__dict__['_obj']:
                        skip_user_images = request.__dict__['_obj']['skipUserImageIds']
                except Exception as e:
                    logger.error(f"Error extracting skipUserImageIds: {str(e)}")
                    
            # Log for debugging - safely get urls_to_download length
            url_count = len(urls_to_download) if urls_to_download is not None else 0
            logger.info(f"Direct stock media check: is_stock_media_direct={is_stock_media_direct}, urls_count={url_count}, skip_user_images={skip_user_images}")
                
            if is_stock_media_direct and urls_to_download and len(urls_to_download) > 0:
                # Process similar to AI but with direct stock URLs
                logger.info(f"Using direct stock media URLs approach with {len(urls_to_download)} URLs")
                self.update_job_status(redis_client, job_id, "fetching_user_images", progress=5)
                
                # Download all stock images directly
                stock_image_paths = []
                for url in urls_to_download:
                    logger.info(f"Downloading stock image from URL: {url}")
                    local_path = media_fetcher.download_file(url)
                    if local_path:
                        stock_image_paths.append(local_path)
                        temp_files.append(local_path)
                        logger.info(f"Downloaded stock image to {local_path}")
                    else:
                        logger.error(f"Failed to download stock image from {url}")
                
                if not stock_image_paths:
                    error_msg = "Failed to download any stock images"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"Successfully downloaded {len(stock_image_paths)} stock images")
                self.update_job_status(redis_client, job_id, "user_images_fetched", progress=10)
                
                # Create media assets object with stock images (similar to user images)
                media_assets = {'images': stock_image_paths, 'videos': []}
                self.update_job_status(redis_client, job_id, "media_fetched", progress=20)
                
            # Determine if we're using user-provided images
            elif hasattr(request, 'user_image_ids') and request.user_image_ids and len(request.user_image_ids) > 0 and not skip_user_images:
                logger.info(f"Using user-provided images: {request.user_image_ids}")
                self.update_job_status(redis_client, job_id, "fetching_user_images", progress=5)
                
                # Fetch user images and create media assets object  
                user_image_paths = self.fetch_user_images(request.user_image_ids, request)
                
                # Track user image paths for cleanup
                temp_files.extend(user_image_paths)
                
                if not user_image_paths:
                    error_msg = "Failed to fetch any user-provided images"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"Successfully fetched {len(user_image_paths)} user images")
                self.update_job_status(redis_client, job_id, "user_images_fetched", progress=10)
                
                # Create media assets object with user images
                media_assets = {'images': user_image_paths, 'videos': []}
                self.update_job_status(redis_client, job_id, "media_fetched", progress=20)
                
            else:
                # Fall back to fetching media from Unsplash (AI approach)
                logger.info(f"No user or stock images provided, fetching media assets for content: {request.content}")
                self.update_job_status(redis_client, job_id, "media_fetching", progress=10)
                
                media_assets = media_fetcher.fetch_media(request.content, duration=request.duration)
                logger.info(f"Media assets fetched: {json.dumps(media_assets, indent=2)}")
                
                # Track auto-generated media for cleanup
                if media_assets and 'images' in media_assets:
                    temp_files.extend(media_assets['images'])
                if media_assets and 'videos' in media_assets:
                    temp_files.extend(media_assets['videos'])
                
                self.update_job_status(redis_client, job_id, "media_fetched", progress=20)
            
            # Monitor memory usage after fetching images
            logger.info(f"Memory after fetching images: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Verify we have media assets to work with
            if not media_assets or not media_assets.get('images'):
                error_msg = "No media assets were fetched"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
            # Process text to match target duration
            logger.info(f"Processing text to match duration: {request.duration}s")
            processed_text = text_processor.process_text(request.content, request.duration)
            if not processed_text:
                error_msg = "Failed to process text for target duration"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            logger.info("Text processed successfully")
            
            # Check video preferences for content analysis and segment matching
            video_prefs = request.videoPreferences if hasattr(request, 'videoPreferences') and request.videoPreferences is not None else {}
            
            # Handle videoPreferences which can be either a dict or a Pydantic model
            if isinstance(video_prefs, dict):
                disable_content_analysis = video_prefs.get('disableContentAnalysis', False)
                force_simple_distribution = video_prefs.get('forceSimpleDistribution', False)
                skip_segment_matching = video_prefs.get('skipSegmentMatching', False)
            else:
                # When it's a Pydantic model, use hasattr/getattr instead of dict.get
                disable_content_analysis = getattr(video_prefs, 'disableContentAnalysis', False)
                force_simple_distribution = getattr(video_prefs, 'forceSimpleDistribution', False)
                skip_segment_matching = getattr(video_prefs, 'skipSegmentMatching', False)
            
            logger.info(f"Video preferences: disable_content_analysis={disable_content_analysis}, force_simple_distribution={force_simple_distribution}, skip_segment_matching={skip_segment_matching}")
            logger.info(f"Full video preferences: {video_prefs}")
            
            # Add more detailed logging about request properties
            logger.info(f"Request has videoPreferences attr: {hasattr(request, 'videoPreferences')}")
            if hasattr(request, 'videoPreferences'):
                logger.info(f"videoPreferences value: {request.videoPreferences}")
                if request.videoPreferences is not None:
                    logger.info(f"videoPreferences has transitionStyle: {hasattr(request.videoPreferences, 'transitionStyle')}")
                    if hasattr(request.videoPreferences, 'transitionStyle'):
                        logger.info(f"transitionStyle value: '{request.videoPreferences.transitionStyle}'")
                    
                    # If videoPreferences is a dict, check keys
                    if isinstance(request.videoPreferences, dict):
                        logger.info(f"videoPreferences keys: {list(request.videoPreferences.keys())}")
                        if 'transitionStyle' in request.videoPreferences:
                            logger.info(f"transitionStyle in dict: '{request.videoPreferences['transitionStyle']}'")

            # Get transition preferences
            transition_prefs = request.transitionPreferences
            transition_duration = transition_prefs.duration if transition_prefs else 0.5
            transition_style = transition_prefs.defaultStyle if transition_prefs else None
            
            # Add additional logging for videoPreferences
            logger.info(f"Request has videoPreferences attribute: {hasattr(request, 'videoPreferences')}")
            if hasattr(request, 'videoPreferences'):
                logger.info(f"videoPreferences is None: {request.videoPreferences is None}")
                if request.videoPreferences is not None:
                    if hasattr(request.videoPreferences, 'transitionStyle'):
                        logger.info(f"videoPreferences.transitionStyle value: '{request.videoPreferences.transitionStyle}'")
                    elif isinstance(request.videoPreferences, dict) and 'transitionStyle' in request.videoPreferences:
                        logger.info(f"videoPreferences dict has transitionStyle: '{request.videoPreferences['transitionStyle']}'")

            # If no transition style is set, try to get it from videoPreferences
            if transition_style is None and hasattr(request, 'videoPreferences') and request.videoPreferences is not None:
                video_prefs = request.videoPreferences
                
                # Handle the case where videoPreferences is a dictionary
                if isinstance(video_prefs, dict):
                    logger.info(f"videoPreferences is a dictionary with keys: {list(video_prefs.keys())}")
                    if 'transitionStyle' in video_prefs and video_prefs['transitionStyle']:
                        logger.info(f"Using transition style from videoPreferences dict: '{video_prefs['transitionStyle']}'")
                        
                        # Convert string to TransitionStyle enum
                        from ...models.video import TransitionStyle
                        try:
                            # Handle mapping of frontend style names to backend enum values
                            frontend_to_backend = {
                                'crossfade': TransitionStyle.CROSSFADE,
                                'cinematic': TransitionStyle.FADE,
                                'dynamic': TransitionStyle.ZOOM
                            }
                            
                            # Try direct mapping from frontend names
                            if video_prefs['transitionStyle'].lower() in frontend_to_backend:
                                transition_style = frontend_to_backend[video_prefs['transitionStyle'].lower()]
                                logger.info(f"Mapped frontend transition style '{video_prefs['transitionStyle']}' to backend enum {transition_style}")
                            # Try uppercase enum lookup
                            elif hasattr(TransitionStyle, video_prefs['transitionStyle'].upper()):
                                transition_style = getattr(TransitionStyle, video_prefs['transitionStyle'].upper())
                                logger.info(f"Used direct enum lookup for transition style '{video_prefs['transitionStyle']}'")
                            else:
                                # Default to crossfade
                                logger.warning(f"No mapping found for transition style '{video_prefs['transitionStyle']}', using CROSSFADE")
                                transition_style = TransitionStyle.CROSSFADE
                        except Exception as e:
                            logger.warning(f"Failed to convert dictionary transition style '{video_prefs['transitionStyle']}': {e}")
                            # Fallback mapping
                            if video_prefs['transitionStyle'] == 'crossfade':
                                transition_style = TransitionStyle.CROSSFADE
                            elif video_prefs['transitionStyle'] == 'cinematic':
                                transition_style = TransitionStyle.FADE
                            elif video_prefs['transitionStyle'] == 'dynamic':
                                transition_style = TransitionStyle.ZOOM
                            else:
                                transition_style = TransitionStyle.CROSSFADE
                            logger.info(f"Exception fallback: Used direct mapping for '{video_prefs['transitionStyle']}' to {transition_style}")
                # Handle the case where videoPreferences is an object
                elif hasattr(video_prefs, 'transitionStyle') and video_prefs.transitionStyle:
                    logger.info(f"Using transition style from videoPreferences object: '{video_prefs.transitionStyle}'")
                    
                    # Convert string to TransitionStyle enum if needed
                    from ...models.video import TransitionStyle
                    try:
                        # Handle mapping of frontend style names to backend enum values
                        frontend_to_backend = {
                            'crossfade': TransitionStyle.CROSSFADE,
                            'cinematic': TransitionStyle.FADE,
                            'dynamic': TransitionStyle.ZOOM
                        }
                        
                        # First try direct mapping from frontend names
                        if video_prefs.transitionStyle.lower() in frontend_to_backend:
                            transition_style = frontend_to_backend[video_prefs.transitionStyle.lower()]
                            logger.info(f"Mapped frontend transition style '{video_prefs.transitionStyle}' to backend enum {transition_style}")
                        # Then try uppercase enum lookup (for values sent directly as enum names)
                        elif hasattr(TransitionStyle, video_prefs.transitionStyle.upper()):
                            transition_style = getattr(TransitionStyle, video_prefs.transitionStyle.upper())
                            logger.info(f"Used direct enum lookup for transition style '{video_prefs.transitionStyle}'")
                        else:
                            # Default to crossfade if no mapping is found
                            logger.warning(f"No mapping found for transition style '{video_prefs.transitionStyle}', using CROSSFADE")
                            transition_style = TransitionStyle.CROSSFADE
                            
                    except Exception as e:
                        logger.warning(f"Failed to convert object transition style '{video_prefs.transitionStyle}': {e}")
                        # Use a safer direct mapping approach as fallback
                        if video_prefs.transitionStyle == 'crossfade':
                            transition_style = TransitionStyle.CROSSFADE
                        elif video_prefs.transitionStyle == 'cinematic':
                            transition_style = TransitionStyle.FADE
                        elif video_prefs.transitionStyle == 'dynamic':
                            transition_style = TransitionStyle.ZOOM
                        else:
                            # Default to crossfade
                            transition_style = TransitionStyle.CROSSFADE
                        
                        logger.info(f"Exception fallback: Used direct mapping for '{video_prefs.transitionStyle}' to {transition_style}")

            logger.info(f"Final transition style selected: {transition_style}")
            
            # Calculate total transition time
            total_transition_time = (len(media_assets['images']) - 1) * transition_duration
            
            # Calculate equal duration for each image
            available_image_time = request.duration - total_transition_time
            
            # For stock media, always use equal duration for all images
            if is_stock_media_direct:
                equal_image_duration = available_image_time / len(media_assets['images'])
                logger.info(f"Stock media: Using equal duration of {equal_image_duration:.2f}s for all {len(media_assets['images'])} images")
            else:
                # For non-stock media, enforce minimum duration
                min_segment_duration = 2.5  # Minimum 2.5 seconds per segment
                
                # Check if we have enough time for all segments with minimum duration
                required_time = len(media_assets['images']) * min_segment_duration + total_transition_time
                if available_image_time < required_time:
                    # Reduce number of segments to fit minimum duration
                    max_segments = math.floor((request.duration - total_transition_time) / min_segment_duration)
                    if max_segments < 1:
                        max_segments = 1
                    logger.warning(f"Not enough time for all segments with minimum duration. Reducing from {len(media_assets['images'])} to {max_segments} segments")
                    media_assets['images'] = media_assets['images'][:max_segments]
                    # Recalculate total transition time
                    total_transition_time = (max_segments - 1) * transition_duration
                    available_image_time = request.duration - total_transition_time
                
                # Calculate equal duration for remaining segments
                equal_image_duration = available_image_time / len(media_assets['images'])
            
            logger.info(f"Calculated timing - Total duration: {request.duration}s, Transition time: {total_transition_time}s, Segments: {len(media_assets['images'])}, Segment duration: {equal_image_duration:.2f}s")
            
            # Create video segments with equal timing
            video_segments = []
            logger.info(f"=== VIDEO SEGMENT DETAILS ===")
            logger.info(f"Total images available: {len(media_assets['images'])}")
            logger.info(f"Video duration: {request.duration:.2f}s")
            logger.info(f"Transition duration: {transition_duration:.2f}s")
            logger.info(f"Total transition time: {total_transition_time:.2f}s")
            logger.info(f"Available image time: {available_image_time:.2f}s")
            logger.info(f"Equal duration per image: {equal_image_duration:.2f}s")
            logger.info(f"Using transition style: {transition_style}")
            
            # First create all base clips without transitions
            base_clips = []
            for i, image_path in enumerate(media_assets['images']):
                time_start = time.time()
                try:
                    # Check if file exists
                    if not os.path.exists(image_path):
                        logger.error(f"File does not exist: {image_path}")
                        self.update_job_status(redis_client, job_id, "failed", error=f"Media file not found: {os.path.basename(image_path)}")
                        raise FileNotFoundError(f"Media file not found: {image_path}")
                    
                    # Check file type
                    is_video = any(image_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv'])
                    
                    if is_video:
                        logger.info(f"Processing video file {i+1}/{len(media_assets['images'])}: {image_path}")
                        try:
                            clip = media_processor.process_video(image_path, equal_image_duration)
                            logger.info(f"Successfully created video clip {i+1} with duration {clip.duration}s")
                        except Exception as e:
                            logger.error(f"Error processing video file {image_path}: {str(e)}")
                            # Fallback to using a blank clip if video processing fails
                            logger.warning(f"Using fallback blank clip for video {image_path}")
                            blank_clip = ColorClip(media_processor.target_resolution, color=(0,0,0))
                            clip = blank_clip.set_duration(equal_image_duration)
                    else:
                        logger.info(f"Processing image file {i+1}/{len(media_assets['images'])}: {image_path}")
                        clip = media_processor.process_image(image_path, equal_image_duration)
                        logger.info(f"Successfully created image clip {i+1} with duration {clip.duration}s")
                except Exception as e:
                    logger.error(f"Error processing media file {image_path}: {str(e)}")
                    logger.error(traceback.format_exc())
                    self.update_job_status(redis_client, job_id, "failed", error=f"Failed to process media: {str(e)}")
                    raise
                base_clips.append((clip, image_path))
            
            # Now apply transitions between clips
            for i, (clip, image_path) in enumerate(base_clips):
                if i > 0:
                    # Determine transition style to use
                    if transition_style:
                        try:
                            # Make sure we convert string values to enum values if needed
                            from ...models.video import TransitionStyle
                            transition_value = transition_style
                            if isinstance(transition_style, str):
                                # Try to convert string to enum
                                try:
                                    # Check if it's a lowercase string that matches an enum value
                                    for style in TransitionStyle:
                                        if transition_style.lower() == style.value:
                                            transition_value = style
                                            break
                                except:
                                    # If conversion fails, keep the string value
                                    pass
                                    
                            logger.info(f"Segment {i+1}: Using configured transition style: {transition_value}")
                        except KeyError:
                            # Fallback to crossfade if the transition style is not found
                            logger.warning(f"Transition style {transition_style} not found in TRANSITIONS, falling back to CROSSFADE")
                            transition_style = TransitionStyle.CROSSFADE
                    else:
                        from ...models.video import TransitionStyle
                        selected_style = TransitionStyle.CROSSFADE
                        transition_style = selected_style
                        logger.info(f"Segment {i+1}: Dynamically selected transition style: {transition_style}")
                    
                    # Apply transition effect explicitly based on type
                    logger.info(f"Segment {i+1}: Applying {transition_style} transition with duration {transition_duration:.2f}s")
                    try:
                        # Apply the transition directly based on type
                        from ...models.video import TransitionStyle
                        
                        # Get the string value of the transition for easier comparison
                        transition_value = transition_style
                        if hasattr(transition_style, 'value'):
                            # If it's an enum, get its value
                            transition_value = transition_style.value
                        
                        logger.info(f"Using transition value: {transition_value}")
                        
                        # Apply transition based on the string value
                        if transition_value == TransitionStyle.CROSSFADE.value:
                            logger.info(f"Applying CROSSFADE transition to segment {i+1}")
                            clip = clip.crossfadein(transition_duration)
                        elif transition_value == TransitionStyle.FADE.value:
                            logger.info(f"Applying FADE transition to segment {i+1}")
                            clip = clip.fadein(transition_duration)
                        elif transition_value == TransitionStyle.ZOOM.value:
                            logger.info(f"Applying ZOOM transition to segment {i+1}")
                            # Implement a more dramatic zoom effect
                            clip = clip.resize(lambda t: max(0.6, min(1, 0.6 + 0.4*t/transition_duration)) if t < transition_duration*1.5 else 1)
                        elif transition_value == TransitionStyle.SLIDE_LEFT.value:
                            logger.info(f"Applying SLIDE_LEFT transition to segment {i+1}")
                            # Move from right to left
                            clip = clip.set_position(lambda t: ((1-min(1, t/transition_duration))*clip.w, 0) if t < transition_duration*1.5 else (0,0))
                        elif transition_value == TransitionStyle.SLIDE_RIGHT.value:
                            logger.info(f"Applying SLIDE_RIGHT transition to segment {i+1}")
                            # Move from left to right
                            clip = clip.set_position(lambda t: ((-min(1, t/transition_duration)*clip.w, 0) if t < transition_duration*1.5 else (0,0)))
                        else:
                            # Fallback to crossfade for unknown transition types
                            logger.warning(f"Unknown transition value {transition_value}, falling back to crossfade")
                            clip = clip.crossfadein(transition_duration)
                        
                        logger.info(f"Segment {i+1}: Successfully applied {transition_value} transition")
                    except Exception as e:
                        logger.error(f"Error applying transition: {str(e)}")
                        logger.error(traceback.format_exc())
                        # Fallback to crossfade on error
                        logger.warning(f"Falling back to crossfade due to error")
                        try:
                            clip = clip.crossfadein(transition_duration)
                        except:
                            # If even crossfade fails, continue without transition
                            logger.error("Even crossfade failed, continuing without transition")
                
                video_segments.append(clip)
            
            if not video_segments:
                error_msg = "Failed to create video segments"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
                
            logger.info(f"=== FINAL VIDEO SEGMENT SUMMARY ===")
            logger.info(f"Total segments created: {len(video_segments)}")
            logger.info(f"Total video duration: {request.duration:.2f}s")
            logger.info(f"Average segment duration: {equal_image_duration:.2f}s")
            logger.info(f"Total transition time: {total_transition_time:.2f}s")
            logger.info(f"Media type: {'Stock' if is_stock_media_direct else 'User/Custom'}")
            self.update_job_status(redis_client, job_id, "media_processed", progress=60)
            
            # Combine audio with video
            self.update_job_status(redis_client, job_id, "combining", progress=70)
            logger.info("Combining audio and video")
            
            # Check if there's audio available or if we need to generate it
            if 'videos' not in media_assets or not media_assets['videos']:
                # Generate audio narration
                logger.info("No audio found in media assets, generating audio narration")
                self.update_job_status(redis_client, job_id, "audio_generating", progress=65)
                
                # Check if the text needs to be summarized for TTS
                logger.info(f"Original text length for TTS: {len(processed_text)} chars")
                # Get audio preferences or use defaults
                audio_prefs = request.audioPreferences or {}
                strict_duration = audio_prefs.get('strictDuration', True) if isinstance(audio_prefs, dict) else getattr(audio_prefs, 'strictDuration', True)
                
                # Calculate target duration for TTS
                target_duration = request.duration * 0.9  # Use 90% of video duration for narration
                
                # Check if we need to summarize the text to fit the video duration
                words = processed_text.split()
                estimated_audio_duration = len(words) / 2.5  # Estimate 2.5 words per second
                
                logger.info(f"Estimated audio duration: {estimated_audio_duration:.2f}s, Target: {target_duration:.2f}s")
                
                if estimated_audio_duration > target_duration + 0.5:
                    logger.info(f"Text is too long for target duration, generating summary")
                    try:
                        # Try up to 3 iterations of progressively shorter text
                        max_attempts = 3
                        current_attempt = 1
                        summarized_text = processed_text
                        
                        while current_attempt <= max_attempts and estimated_audio_duration > target_duration + 0.5:
                            logger.info(f"Attempting to generate shorter text (attempt {current_attempt}/{max_attempts})")
                            
                            # Make target more aggressive with each attempt
                            scaling_factor = 1.0 + (0.3 * current_attempt)  # Gets more aggressive with each attempt
                            current_target = target_duration / scaling_factor
                            
                            # Use different conciseness levels based on attempt
                            conciseness_levels = ["concise", "very concise", "extremely concise"]
                            word_descriptors = ["shorter", "much shorter", "drastically shorter"]
                            conciseness = conciseness_levels[min(current_attempt - 1, 2)]
                            descriptor = word_descriptors[min(current_attempt - 1, 2)]
                            
                            logger.info(f"Using {conciseness} level for iteration {current_attempt}")
                            
                            response = self.openai_client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {
                                        "role": "system",
                                        "content": f"""You are a professional content editor. Create a {conciseness} version of the following text that will take EXACTLY {current_target:.1f} seconds to speak naturally.
                                        
                                        Rules:
                                        1. The final text MUST be spoken in {current_target:.1f} seconds - this is CRITICAL
                                        2. Make the content {descriptor} while preserving core message
                                        3. Use shorter words and simpler sentences
                                        4. Remove all optional content, examples, and elaborations
                                        5. Focus on the most essential points
                                        6. Target approximately {int(current_target * 2.5)} words total
                                        
                                        The length of your response is the HIGHEST priority - it MUST be spoken in {current_target:.1f} seconds or less.
                                        """
                                    },
                                    {
                                        "role": "user",
                                        "content": processed_text
                                    }
                                ],
                                temperature=0.7,
                                max_tokens=500
                            )
                            
                            summarized_text = response.choices[0].message.content.strip()
                            if summarized_text and len(summarized_text) < len(processed_text):
                                logger.info(f"Generated shorter text: Original {len(processed_text)} chars -> New {len(summarized_text)} chars")
                                # Update estimated duration
                                words = summarized_text.split()
                                estimated_audio_duration = len(words) / 2.5
                                logger.info(f"New estimated audio duration: {estimated_audio_duration:.2f}s, Target: {target_duration:.2f}s")
                                processed_text = summarized_text
                            else:
                                logger.warning(f"Failed to generate shorter text or result wasn't shorter (attempt {current_attempt})")
                                break
                                
                            current_attempt += 1
                            
                    except Exception as e:
                        logger.error(f"Error generating summary: {str(e)}")
                        logger.error(f"Using original text for audio generation")
                        # Continue with original text if summarization fails
                
                # Create transcript with chunks
                logger.info("Creating transcript with chunks")
                transcript = Transcript(
                    chunks=[],
                    total_duration=0,
                    original_text=processed_text,
                    processed_text=processed_text
                )
                
                # Split into chunks and estimate timing
                words = processed_text.split()
                chunk_size = 10  # words per chunk
                for i in range(0, len(words), chunk_size):
                    chunk_text = ' '.join(words[i:i+chunk_size])
                    duration = len(chunk_text.split()) / 2.5  # words per second
                    
                    transcript.chunks.append(TranscriptChunk(
                        text=chunk_text,
                        start_time=transcript.total_duration,
                        end_time=transcript.total_duration + duration
                    ))
                    transcript.total_duration += duration
                
                logger.info(f"Created {len(transcript.chunks)} chunks with total duration {transcript.total_duration:.2f}s")
                
                # Generate audio for each chunk
                audio_chunks = []
                for i, chunk in enumerate(transcript.chunks):
                    logger.info(f"Generating audio for chunk {i+1}/{len(transcript.chunks)}")
                    chunk.tts_file = audio_generator.generate_audio(chunk.text)
                    if chunk.tts_file:
                        logger.info(f"Generated audio for chunk {i+1}: {chunk.tts_file}")
                        audio_chunks.append(chunk.tts_file)
                        temp_files.append(chunk.tts_file)
                    else:
                        logger.error(f"Failed to generate audio for chunk {i+1}")
                
                if audio_chunks:
                    logger.info("Combining audio chunks")
                    final_audio = media_processor.combine_audio_chunks(audio_chunks)
                    if final_audio:
                        logger.info(f"Successfully combined audio chunks: {final_audio}")
                        temp_files.append(final_audio)
                        media_assets['videos'] = [final_audio]
                        self.update_job_status(redis_client, job_id, "audio_generated", progress=68)
                    else:
                        logger.error("Failed to combine audio chunks")
                        # Fallback to silent audio
                        from moviepy.audio.AudioClip import AudioClip
                        silent_audio = AudioClip(lambda t: 0, duration=request.duration)
                        final_video = media_processor.combine_with_audio(video_segments, silent_audio)
                else:
                    logger.error("No audio chunks generated successfully")
                    # Fallback to silent audio
                    from moviepy.audio.AudioClip import AudioClip
                    silent_audio = AudioClip(lambda t: 0, duration=request.duration)
                    final_video = media_processor.combine_with_audio(video_segments, silent_audio)
            
            # Now proceed with the audio we have
            if 'videos' in media_assets and media_assets['videos']:
                logger.info(f"Using audio file from media_assets: {media_assets['videos'][0]}")
                final_video = media_processor.combine_with_audio(video_segments, media_assets['videos'][0])
            
            logger.info(f"Final video created: {final_video}")
            self.update_job_status(redis_client, job_id, "combined", progress=80)
            
            # Track final video for cleanup
            if final_video:
                temp_files.append(final_video)
            
            if not final_video:
                error_msg = "Failed to combine audio and video"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
            # Monitor memory before final video upload
            logger.info(f"Memory before video upload: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Upload video with more detailed error handling
            logger.info(f"Uploading video to storage: {final_video}")
            self.update_job_status(redis_client, job_id, "uploading", progress=90)
            
            try:
                # Verify the video file exists and has content before upload
                if not os.path.exists(final_video):
                    error_msg = f"Video file not found: {final_video}"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise FileNotFoundError(error_msg)
                
                file_size = os.path.getsize(final_video)
                if file_size == 0:
                    error_msg = f"Video file is empty: {final_video}"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise ValueError(error_msg)
                
                logger.info(f"Video file size: {file_size / (1024 * 1024):.2f} MB")
                
                # Attempt upload with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        video_url = storage_service.upload_video(final_video, job_id)
                        if video_url:
                            logger.info(f"Video uploaded successfully: {video_url}")
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            error_msg = f"Failed to upload video after {max_retries} attempts: {str(e)}"
                            logger.error(error_msg)
                            self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                            raise
                        logger.warning(f"Upload attempt {attempt + 1} failed: {str(e)}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                
                if not video_url:
                    error_msg = "Failed to upload video to storage - empty URL returned"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise Exception(error_msg)
                
                # Monitor memory after successful upload
                logger.info(f"Memory after successful upload: {process.memory_info().rss / 1024 / 1024:.2f} MB")
                
                # Update final status
                self.update_job_status(redis_client, job_id, "completed", progress=100, video_url=video_url)
                logger.info("Video generation completed successfully")
                
                # Clean up temporary files
                self.cleanup_temp_files(temp_files)
                
                # After the video is generated but before it's returned, add caption rendering
                try:
                    # Extract caption preferences from request
                    captions_enabled = False
                    caption_prefs = None
                    caption_timing = None
                    
                    # Log detailed raw request properties for debugging
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Starting caption processing for job {job_id}")
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Raw request type: {type(request)}")
                    
                    # Log direct request fields
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Direct fields available: {[f for f in dir(request) if not f.startswith('_')]}")
                    
                    # Log information about the request structure
                    if hasattr(request, 'model_dump'):
                        try:
                            dump = request.model_dump()
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Top-level fields in request: {list(dump.keys())}")
                            if 'videoPreferences' in dump:
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: videoPreferences keys: {list(dump['videoPreferences'].keys())}")
                                if 'captions' in dump['videoPreferences']:
                                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Captions in videoPreferences: {dump['videoPreferences']['captions']}")
                        except Exception as e:
                            logger.error(f"🎬 CAPTION DEBUG [BACKEND]: Error dumping model: {str(e)}")
                    
                    # Check for X-Captions-Enabled header
                    if hasattr(request, 'model_extra') and 'headers' in request.model_extra:
                        headers = request.model_extra['headers']
                        if isinstance(headers, dict) and 'X-Captions-Enabled' in headers:
                            header_value = headers['X-Captions-Enabled']
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found X-Captions-Enabled header: {header_value}")
                            if header_value.lower() == 'true':
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Captions explicitly enabled via header")
                    
                    # Safely check for videoPreferences and captions
                    if hasattr(request, 'videoPreferences') and request.videoPreferences is not None:
                        video_prefs = request.videoPreferences
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found videoPreferences directly on request")
                        
                        if hasattr(video_prefs, 'captions') and video_prefs.captions is not None:
                            captions_enabled = getattr(video_prefs.captions, 'enabled', False)
                            caption_prefs = video_prefs.captions.dict() if hasattr(video_prefs.captions, 'dict') else video_prefs.captions
                            caption_timing = getattr(video_prefs.captions, 'timing', None)
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found captions in videoPreferences: enabled={captions_enabled}, has_timing={caption_timing is not None}")
                            if caption_timing:
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Caption timing data: {len(caption_timing)} segments")
                                # Log first segment sample
                                if len(caption_timing) > 0:
                                    first_segment = caption_timing[0]
                                    caption_chunks = getattr(first_segment, 'captionChunks', [])
                                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: First segment caption chunks: {len(caption_chunks)} chunks")
                                    if caption_chunks and len(caption_chunks) > 0:
                                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: First caption chunk sample: {caption_chunks[0]}")

                    # Also check in model_extra for captions
                    elif hasattr(request, 'model_extra') and request.model_extra:
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Checking model_extra for captions")
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: model_extra keys: {list(request.model_extra.keys())}")
                        
                        if 'videoPreferences' in request.model_extra and request.model_extra['videoPreferences']:
                            video_prefs = request.model_extra['videoPreferences']
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found videoPreferences in model_extra")
                            
                            if isinstance(video_prefs, dict) and 'captions' in video_prefs:
                                captions_enabled = video_prefs['captions'].get('enabled', False)
                                caption_prefs = video_prefs['captions']
                                caption_timing = video_prefs['captions'].get('timing', None)
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found captions in model_extra: enabled={captions_enabled}, has_timing={caption_timing is not None}")
                                if caption_timing:
                                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Caption timing data from model_extra: {len(caption_timing)} segments")
                        
                        # Also check for top-level captions
                        if 'captions' in request.model_extra:
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found top-level captions in model_extra: {request.model_extra['captions']}")
                            if isinstance(request.model_extra['captions'], dict) and 'enabled' in request.model_extra['captions']:
                                captions_enabled = request.model_extra['captions'].get('enabled', False)
                                caption_prefs = request.model_extra['captions']
                                caption_timing = request.model_extra['captions'].get('timing', None)
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Using top-level captions from model_extra: enabled={captions_enabled}")
                    
                    # Look for contentAnalysis data if timing is not found
                    if not caption_timing and hasattr(request, 'contentAnalysis') and request.contentAnalysis:
                        logger.info("🎬 CAPTION DEBUG [BACKEND]: Looking for caption timing in contentAnalysis")
                        if hasattr(request.contentAnalysis, 'segments') and request.contentAnalysis.segments:
                            segments = request.contentAnalysis.segments
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Found {len(segments)} segments in contentAnalysis")
                            
                            # Check if any segment has timing with captionChunks
                            has_caption_chunks = False
                            for i, segment in enumerate(segments):
                                if hasattr(segment, 'timing') and segment.timing:
                                    if hasattr(segment.timing, 'captionChunks') and segment.timing.captionChunks:
                                        has_caption_chunks = True
                                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Segment {i} has {len(segment.timing.captionChunks)} caption chunks")
                                        # Log first chunk sample
                                        if len(segment.timing.captionChunks) > 0:
                                            first_chunk = segment.timing.captionChunks[0]
                                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: First chunk sample: {first_chunk}")
                                        break
                            
                            if not has_caption_chunks:
                                logger.warning("🎬 CAPTION DEBUG [BACKEND]: No captionChunks found in contentAnalysis segments")
                    
                    # Log the final decision about captions
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Final caption decision: enabled={captions_enabled}, has_prefs={caption_prefs is not None}, has_timing={caption_timing is not None}")
                    
                    # If captions are enabled, apply them to the video
                    if captions_enabled:
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Caption rendering enabled for job {job_id}")
                        feature_flag_enabled = is_feature_enabled("ENABLE_CAPTIONS")
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: ENABLE_CAPTIONS feature flag: {feature_flag_enabled}")
                        
                        # Final check if both enabled flag and feature flag are true
                        captions_enabled = captions_enabled and feature_flag_enabled
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Final captions_enabled value: {captions_enabled}")
                        
                        # Create caption renderer
                        caption_renderer = CaptionRenderer(
                            captions_enabled=captions_enabled,
                            caption_prefs=caption_prefs,
                            tts_text=processed_text
                        )
                        
                        # Prepare caption data
                        caption_data = {
                            "text": processed_text,
                            "timing": caption_timing
                        }
                        
                        # If we're using caption timing from content analysis
                        if not caption_timing and hasattr(request, 'contentAnalysis') and request.contentAnalysis:
                            if hasattr(request.contentAnalysis, 'segments') and request.contentAnalysis.segments:
                                caption_data["timing"] = request.contentAnalysis.segments
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Using timing data from content analysis for job {job_id}")
                        
                        # Apply captions to the video
                        if caption_data["timing"]:
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Applying captions to video for job {job_id}")
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Caption data timing has {len(caption_data['timing'])} entries")
                            
                            try:
                                temp_dir = tempfile.gettempdir()
                                captioned_video = caption_renderer.render_captions(
                                    video_path=final_video, 
                                    caption_data=caption_data, 
                                    work_dir=temp_dir
                                )
                                
                                if captioned_video and captioned_video != final_video:
                                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Successfully applied captions to video for job {job_id}")
                                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Original path: {final_video}, Captioned path: {captioned_video}")
                                    final_video = captioned_video
                                else:
                                    logger.warning(f"🎬 CAPTION DEBUG [BACKEND]: Caption renderer returned original video, captions may not have been applied")
                            except Exception as e:
                                logger.error(f"🎬 CAPTION ERROR [BACKEND]: Error applying captions: {str(e)}")
                                logger.error(f"🎬 CAPTION ERROR [BACKEND]: Error traceback: {traceback.format_exc()}")
                                # Continue without captions
                        else:
                            # If we have caption preferences but no timing data, try to generate timing from content
                            logger.info(f"🎬 CAPTION DEBUG [BACKEND]: No caption timing data available, will generate from content for job {job_id}")
                            content_text = processed_text if hasattr(processed_text, 'strip') else None
                            
                            if content_text:
                                logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Generating captions from content text: {content_text[:100]}...")
                                try:
                                    temp_dir = tempfile.gettempdir()
                                    captioned_video = caption_renderer.render_captions(
                                        video_path=final_video, 
                                        caption_data=caption_data, 
                                        work_dir=temp_dir,
                                        content=content_text
                                    )
                                    
                                    if captioned_video and captioned_video != final_video:
                                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Successfully applied auto-generated captions to video for job {job_id}")
                                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Original path: {final_video}, Captioned path: {captioned_video}")
                                        final_video = captioned_video
                                    else:
                                        logger.warning(f"🎬 CAPTION DEBUG [BACKEND]: Caption renderer with auto-generated timing returned original video")
                                except Exception as e:
                                    logger.error(f"🎬 CAPTION ERROR [BACKEND]: Error applying auto-generated captions: {str(e)}")
                                    logger.error(f"🎬 CAPTION ERROR [BACKEND]: Error traceback: {traceback.format_exc()}")
                                    # Continue without captions
                            else:
                                logger.warning(f"🎬 CAPTION DEBUG [BACKEND]: No content available for caption generation for job {job_id}")
                    else:
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Captions disabled for job {job_id}")
                
                    # After the audio generation and before the final video creation
                    if captions_enabled:
                        try:
                            # Try the new transcript-based approach first
                            if hasattr(transcript, 'chunks') and transcript.chunks:
                                logger.info("🎬 Using new transcript-based caption approach")
                                final_video = media_processor.apply_captions(
                                    video_path=final_video,
                                    transcript=transcript,
                                    caption_prefs=caption_prefs
                                )
                            else:
                                # Fall back to the old caption renderer if transcript is not available
                                logger.info("🎬 Falling back to old caption renderer")
                                caption_renderer = CaptionRenderer(
                                    captions_enabled=captions_enabled,
                                    caption_prefs=caption_prefs,
                                    tts_text=processed_text
                                )
                                final_video = caption_renderer.render_captions(
                                    video_path=final_video,
                                    caption_timing=caption_timing
                                )
                        except Exception as e:
                            logger.error(f"Error applying captions: {str(e)}")
                            # Continue with uncaptioned video if captioning fails
                            pass
                
                    # Add detailed logging for caption processing
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Starting caption processing for job {job_id}")
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Captions enabled: {captions_enabled}")
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Has caption prefs: {caption_prefs is not None}")
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Has caption timing: {caption_timing is not None}")
                    logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Has transcript: {hasattr(transcript, 'chunks')}")
                    if hasattr(transcript, 'chunks'):
                        logger.info(f"🎬 CAPTION DEBUG [BACKEND]: Number of transcript chunks: {len(transcript.chunks)}")
                
                except Exception as e:
                    logger.error(f"🎬 CAPTION ERROR [BACKEND]: Error in caption processing for job {job_id}: {str(e)}")
                    logger.error(f"🎬 CAPTION ERROR [BACKEND]: Caption error traceback: {traceback.format_exc()}")
                    # Continue with original video if caption rendering fails
                
                return video_url
            except Exception as e:
                error_msg = f"Error during video upload: {str(e)}"
                logger.error(error_msg)
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise
            
        except Exception as e:
            error_msg = f"Error generating video: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Log memory usage on error
            try:
                logger.error(f"Memory usage at error: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            except:
                pass
                
            self.update_job_status(redis_client, job_id, "failed", error=error_msg)
            
            # Clean up temporary files even on error
            self.cleanup_temp_files(temp_files)
            
            raise

    def cleanup_temp_files(self, file_paths: List[str]) -> None:
        """
        Clean up temporary files created during video generation.
        
        Args:
            file_paths: List of file paths to clean up
        """
        logger.info(f"Cleaning up {len(file_paths)} temporary files")
        
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")
        
        # Clean up any empty temporary directories
        try:
            # Get unique directories from file paths
            temp_dirs = set()
            for file_path in file_paths:
                if file_path:
                    dir_path = os.path.dirname(file_path)
                    if dir_path.startswith('/tmp/') or 'temp' in dir_path.lower():
                        temp_dirs.add(dir_path)
            
            # Remove empty directories
            for dir_path in temp_dirs:
                if os.path.exists(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.debug(f"Removed empty temporary directory: {dir_path}")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary directories: {str(e)}")

    def process_video_job(self, job_id: str, request: VideoRequest, redis_client: Redis) -> None:
        """Process video generation job."""
        try:
            logger.info(f"Starting video job processing for job {job_id}")
            self.generate_video(job_id, request, redis_client)
        except Exception as e:
            logger.error(f"Error processing video job: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Error status already updated in generate_video

# Create a singleton instance
video_generator = VideoGenerator() 