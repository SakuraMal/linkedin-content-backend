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
from .caption_renderer import CaptionRenderer
from ...config import is_feature_enabled
from moviepy.editor import AudioFileClip

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
            
            job_info.update({
                "status": status,
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
                    
                    # Download the image to a temporary file
                    response = requests.get(stock_url, stream=True)
                    if response.status_code != 200:
                        logger.warning(f"Could not download stock image from URL: {stock_url}")
                        continue
                    
                    # Save to a temporary file
                    img_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    img_file.write(response.content)
                    img_file.close()
                    
                    image_files.append(img_file.name)
                    continue
                    
                # Regular flow: Get image URL from storage
                image_url = image_storage_service.get_image_url(image_id)
                if not image_url:
                    logger.warning(f"Could not find image with ID: {image_id}")
                    continue
                
                # Download the image
                response = requests.get(image_url, stream=True)
                if response.status_code != 200:
                    logger.warning(f"Could not download image from URL: {image_url}")
                    continue
                
                # Save to a temporary file
                img_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                img_file.write(response.content)
                img_file.close()
                
                image_files.append(img_file.name)
                
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
            video_prefs = request.videoPreferences if hasattr(request, 'videoPreferences') else {}
            disable_content_analysis = video_prefs.get('disableContentAnalysis', False)
            force_simple_distribution = video_prefs.get('forceSimpleDistribution', False)
            skip_segment_matching = video_prefs.get('skipSegmentMatching', False)
            
            logger.info(f"Video preferences: disable_content_analysis={disable_content_analysis}, force_simple_distribution={force_simple_distribution}, skip_segment_matching={skip_segment_matching}")
            
            if disable_content_analysis or force_simple_distribution or skip_segment_matching:
                # Skip content analysis and use simple distribution
                logger.info("Using simple distribution for images")
                matched_segments = []
                equal_duration = request.duration / len(media_assets['images'])
                for i, image_path in enumerate(media_assets['images']):
                    matched_segments.append({
                        'image_path': image_path,
                        'duration': equal_duration,
                        'text': processed_text,  # Use full text for each segment
                        'topic': 'Simple distribution',
                        'key_points': ['Simple distribution']
                    })
                logger.info(f"Created {len(matched_segments)} segments with simple distribution")
            else:
                # Analyze content segments
                logger.info("Analyzing content segments")
                segments = text_processor.analyze_content_segments(processed_text)
                logger.info(f"Identified {len(segments)} content segments")
                
                # Match images to segments
                logger.info("Matching images to segments")
                matched_segments = text_processor.match_images_to_segments(segments, media_assets['images'])
                logger.info("Successfully matched images to segments")
            
            # Monitor memory usage before audio generation
            logger.info(f"Memory before audio generation: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Generate audio with processed text
            self.update_job_status(redis_client, job_id, "audio_generating", progress=30)
            logger.info("Generating audio for processed content")
            logger.debug("Calling audio_generator.generate_audio")
            
            # Get audio preferences or use defaults
            audio_prefs = request.audioPreferences or {}
            fade_in = audio_prefs.get('fadeInDuration', 2.0)
            fade_out = audio_prefs.get('fadeOutDuration', 2.0)
            strict_duration = audio_prefs.get('strictDuration', True)
            enforce_duration = audio_prefs.get('enforceDuration', True)
            match_video_duration = audio_prefs.get('matchVideoDuration', True)
            trim_audio = audio_prefs.get('trimAudio', True)
            sync_with_video = audio_prefs.get('syncWithVideo', True)
            normalize_audio = audio_prefs.get('normalizeAudio', True)
            max_duration = audio_prefs.get('maxDuration', request.duration - 2)
            
            logger.info(f"Using audio preferences - fade in: {fade_in}s, fade out: {fade_out}s, strict_duration: {strict_duration}")
            audio_file = audio_generator.generate_audio(
                processed_text,
                voice=request.voice,
                fade_in=fade_in,
                fade_out=fade_out,
                target_duration=request.duration if strict_duration else None
            )
            
            # Track audio file for cleanup
            if audio_file:
                temp_files.append(audio_file)
            
            if audio_file:
                logger.info(f"Audio generated successfully: {audio_file}")
                self.update_job_status(redis_client, job_id, "audio_generated", progress=40)
            else:
                logger.error("Audio generation returned None")
                error_msg = "Failed to generate audio file - check logs for detailed error"
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
            # Get actual audio duration and enforce timing
            audio_clip = AudioFileClip(audio_file)
            actual_audio_duration = audio_clip.duration
            audio_clip.close()
            
            # If we need to enforce duration, trim or extend the audio
            if enforce_duration and abs(actual_audio_duration - request.duration) > 0.5:
                logger.info(f"Audio duration ({actual_audio_duration}s) differs from requested duration ({request.duration}s), adjusting...")
                if trim_audio:
                    # Trim audio to match video duration
                    if actual_audio_duration > request.duration:
                        logger.info(f"Trimming audio from {actual_audio_duration}s to {request.duration}s")
                        audio_clip = AudioFileClip(audio_file)
                        audio_clip = audio_clip.subclip(0, request.duration)
                        audio_clip.write_audiofile(audio_file)
                        audio_clip.close()
                        actual_audio_duration = request.duration
                    else:
                        logger.warning(f"Audio is shorter than requested duration ({actual_audio_duration}s < {request.duration}s)")
                else:
                    logger.warning(f"Audio duration mismatch but trim_audio is disabled")
            
            logger.info(f"Final audio duration: {actual_audio_duration:.2f}s (requested: {request.duration}s)")
            
            # Monitor memory usage after audio generation
            logger.info(f"Memory after audio generation: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Process media
            self.update_job_status(redis_client, job_id, "processing_media", progress=50)
            logger.info(f"Processing media with duration: {actual_audio_duration}s")
            
            # Get transition preferences
            transition_prefs = request.transitionPreferences
            transition_duration = transition_prefs.duration if transition_prefs else 0.5
            transition_style = transition_prefs.defaultStyle if transition_prefs else None
            
            # Calculate total transition time
            total_transition_time = (len(matched_segments) - 1) * transition_duration
            
            # Calculate equal duration for each image with minimum duration enforcement
            available_image_time = actual_audio_duration - total_transition_time
            min_segment_duration = 2.5  # Minimum 2.5 seconds per segment
            
            # Check if we have enough time for all segments with minimum duration
            required_time = len(matched_segments) * min_segment_duration + total_transition_time
            if available_image_time < required_time:
                # Reduce number of segments to fit minimum duration
                max_segments = math.floor((actual_audio_duration - total_transition_time) / min_segment_duration)
                if max_segments < 1:
                    max_segments = 1
                logger.warning(f"Not enough time for all segments with minimum duration. Reducing from {len(matched_segments)} to {max_segments} segments")
                matched_segments = matched_segments[:max_segments]
                # Recalculate total transition time
                total_transition_time = (len(matched_segments) - 1) * transition_duration
                available_image_time = actual_audio_duration - total_transition_time
            
            # Calculate equal duration for remaining segments
            equal_image_duration = available_image_time / len(matched_segments)
            
            # Update segment durations to be equal
            for segment in matched_segments:
                segment['duration'] = equal_image_duration
            
            logger.info(f"Calculated timing - Total duration: {actual_audio_duration}s, Transition time: {total_transition_time}s, Segments: {len(matched_segments)}, Segment duration: {equal_image_duration:.2f}s")
            
            # Create video segments with equal timing
            video_segments = []
            for i, segment in enumerate(matched_segments):
                # Process image with equal duration
                clip = media_processor.process_image(segment['image_path'], equal_image_duration)
                
                # Apply transition if not the first clip
                if i > 0:
                    if transition_style:
                        transition = media_processor.TRANSITIONS[transition_style]
                    else:
                        transition_style = media_processor.select_transition(i, len(matched_segments), request.style)
                        transition = media_processor.TRANSITIONS[transition_style]
                    
                    clip = transition(clip, transition_duration)
                
                video_segments.append(clip)
            
            if not video_segments:
                error_msg = "Failed to create video segments"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
                
            logger.info(f"Created {len(video_segments)} video segments with equal timing")
            self.update_job_status(redis_client, job_id, "media_processed", progress=60)
            
            # Combine audio and video
            self.update_job_status(redis_client, job_id, "combining", progress=70)
            logger.info("Combining audio and video")
            final_video = media_processor.combine_with_audio(video_segments, audio_file)
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
                video_url = storage_service.upload_video(final_video, job_id)
                logger.info(f"Video uploaded: {video_url}")
                
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
                    
                    # Check if videoPreferences.captions exists in the request
                    if hasattr(request, 'videoPreferences') and request.videoPreferences:
                        if hasattr(request.videoPreferences, 'captions') and request.videoPreferences.captions:
                            captions_enabled = request.videoPreferences.captions.enabled
                            caption_prefs = request.videoPreferences.captions.dict() if hasattr(request.videoPreferences.captions, 'dict') else request.videoPreferences.captions
                            caption_timing = getattr(request.videoPreferences.captions, 'timing', None)
                            logger.info(f"Found captions in videoPreferences: enabled={captions_enabled}, has_timing={caption_timing is not None}")
                            if caption_timing:
                                logger.info(f"Caption timing data: {len(caption_timing)} segments")
                                # Log first segment sample
                                if len(caption_timing) > 0:
                                    first_segment = caption_timing[0]
                                    caption_chunks = getattr(first_segment, 'captionChunks', [])
                                    logger.info(f"First segment caption chunks: {len(caption_chunks)} chunks")
                                    if caption_chunks and len(caption_chunks) > 0:
                                        logger.info(f"First caption chunk sample: {caption_chunks[0]}")

                    # Also check in model_extra for captions
                    elif hasattr(request, 'model_extra') and request.model_extra:
                        if 'videoPreferences' in request.model_extra and request.model_extra['videoPreferences']:
                            video_prefs = request.model_extra['videoPreferences']
                            if isinstance(video_prefs, dict) and 'captions' in video_prefs:
                                captions_enabled = video_prefs['captions'].get('enabled', False)
                                caption_prefs = video_prefs['captions']
                                caption_timing = video_prefs['captions'].get('timing', None)
                                logger.info(f"Found captions in model_extra: enabled={captions_enabled}, has_timing={caption_timing is not None}")
                                if caption_timing:
                                    logger.info(f"Caption timing data from model_extra: {len(caption_timing)} segments")
                    
                    # Look for contentAnalysis data if timing is not found
                    if not caption_timing and hasattr(request, 'contentAnalysis') and request.contentAnalysis:
                        logger.info("Looking for caption timing in contentAnalysis")
                        if hasattr(request.contentAnalysis, 'segments') and request.contentAnalysis.segments:
                            segments = request.contentAnalysis.segments
                            logger.info(f"Found {len(segments)} segments in contentAnalysis")
                            
                            # Check if any segment has timing with captionChunks
                            has_caption_chunks = False
                            for i, segment in enumerate(segments):
                                if hasattr(segment, 'timing') and segment.timing:
                                    if hasattr(segment.timing, 'captionChunks') and segment.timing.captionChunks:
                                        has_caption_chunks = True
                                        logger.info(f"Segment {i} has {len(segment.timing.captionChunks)} caption chunks")
                                        # Log first chunk sample
                                        if len(segment.timing.captionChunks) > 0:
                                            first_chunk = segment.timing.captionChunks[0]
                                            logger.info(f"First chunk sample: {first_chunk}")
                                        break
                            
                            if not has_caption_chunks:
                                logger.warning("No captionChunks found in contentAnalysis segments")
                    
                    # If captions are enabled, apply them to the video
                    if captions_enabled:
                        logger.info(f"Caption rendering enabled for job {job_id}")
                        feature_flag_enabled = is_feature_enabled("ENABLE_CAPTIONS")
                        logger.info(f"ENABLE_CAPTIONS feature flag: {feature_flag_enabled}")
                        
                        # Create caption renderer
                        caption_renderer = CaptionRenderer(captions_enabled=captions_enabled, caption_prefs=caption_prefs)
                        
                        # Prepare caption data
                        caption_data = {
                            "timing": caption_timing
                        }
                        
                        # If we're using caption timing from content analysis
                        if not caption_timing and hasattr(request, 'contentAnalysis') and request.contentAnalysis:
                            if hasattr(request.contentAnalysis, 'segments') and request.contentAnalysis.segments:
                                caption_data["timing"] = request.contentAnalysis.segments
                                logger.info(f"Using timing data from content analysis for job {job_id}")
                        
                        # Apply captions to the video
                        if caption_data["timing"]:
                            logger.info(f"Applying captions to video for job {job_id}")
                            logger.info(f"Caption data timing has {len(caption_data['timing'])} entries")
                            
                            try:
                                temp_dir = tempfile.gettempdir()
                                captioned_video = caption_renderer.render_captions(
                                    video_path=final_video, 
                                    caption_data=caption_data, 
                                    work_dir=temp_dir
                                )
                                
                                if captioned_video and captioned_video != final_video:
                                    logger.info(f"Successfully applied captions to video for job {job_id}")
                                    final_video = captioned_video
                                else:
                                    logger.warning(f"Caption renderer returned original video, captions may not have been applied")
                            except Exception as e:
                                logger.error(f"Error applying captions: {str(e)}")
                                # Continue without captions
                        else:
                            # If we have caption preferences but no timing data, try to generate timing from content
                            logger.info(f"No caption timing data available, will generate from content for job {job_id}")
                            content_text = request.content if hasattr(request, 'content') else None
                            
                            if content_text:
                                try:
                                    temp_dir = tempfile.gettempdir()
                                    captioned_video = caption_renderer.render_captions(
                                        video_path=final_video, 
                                        caption_data=caption_data, 
                                        work_dir=temp_dir,
                                        content=content_text
                                    )
                                    
                                    if captioned_video and captioned_video != final_video:
                                        logger.info(f"Successfully applied auto-generated captions to video for job {job_id}")
                                        final_video = captioned_video
                                    else:
                                        logger.warning(f"Caption renderer with auto-generated timing returned original video")
                                except Exception as e:
                                    logger.error(f"Error applying auto-generated captions: {str(e)}")
                                    # Continue without captions
                            else:
                                logger.warning(f"No content available for caption generation for job {job_id}")
                
                except Exception as e:
                    logger.error(f"Error applying captions to video for job {job_id}: {str(e)}")
                    logger.error(f"Caption error traceback: {traceback.format_exc()}")
                    # Continue with original video if caption rendering fails
                
                return video_url
            except Exception as upload_error:
                error_msg = f"Error uploading video: {str(upload_error)}"
                logger.error(error_msg)
                logger.error(f"Upload error traceback: {traceback.format_exc()}")
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