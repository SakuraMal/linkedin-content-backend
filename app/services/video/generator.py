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

    def fetch_user_images(self, user_image_ids, request_data=None):
        """
        Fetch user-uploaded images by their IDs
        
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
        if request_data and 'stockMediaUrls' in request_data:
            logger.info(f"Found stockMediaUrls in request data with {len(request_data['stockMediaUrls'])} entries")
            stock_media_urls = request_data['stockMediaUrls']
        
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
            
            # Extract request data
            request_data = request.model_dump()
            
            # Get user-provided image IDs if any
            user_image_ids = request_data.get('user_image_ids', [])
            
            # Monitor memory usage before fetching images
            logger.info(f"Memory before fetching images: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Handle user-provided images if any
            image_files = []
            if user_image_ids:
                logger.info(f"Using user-provided images: {user_image_ids}")
                self.update_job_status(redis_client, job_id, "fetching_user_images", progress=5)
                
                # Fetch user-provided images, passing the full request_data
                image_files = self.fetch_user_images(user_image_ids, request_data)
                
                # Track user image paths for cleanup
                temp_files.extend(image_files)
                
                if not image_files:
                    error_msg = "Failed to fetch any user-provided images"
                    logger.error(error_msg)
                    self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"Successfully fetched {len(image_files)} user images")
                self.update_job_status(redis_client, job_id, "user_images_fetched", progress=10)
                
                # Create media assets object with user images
                media_assets = {'images': image_files, 'videos': []}
                self.update_job_status(redis_client, job_id, "media_fetched", progress=20)
                
            else:
                # Fall back to fetching media from Unsplash
                logger.info(f"No user images provided, fetching media assets for content: {request.content}")
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
            
            # Monitor memory usage before audio generation
            logger.info(f"Memory before audio generation: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Generate audio with processed text
            self.update_job_status(redis_client, job_id, "audio_generating", progress=30)
            logger.info("Generating audio for processed content")
            logger.debug("Calling audio_generator.generate_audio")
            
            # Get audio preferences or use defaults
            audio_prefs = request.audioPreferences or {}
            fade_in = audio_prefs.fadeInDuration if audio_prefs else 2.0
            fade_out = audio_prefs.fadeOutDuration if audio_prefs else 2.0
            
            logger.info(f"Using audio preferences - fade in: {fade_in}s, fade out: {fade_out}s")
            audio_file = audio_generator.generate_audio(
                processed_text,
                voice=request.voice,
                fade_in=fade_in,
                fade_out=fade_out
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
            
            # Monitor memory usage after audio generation
            logger.info(f"Memory after audio generation: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Process media
            self.update_job_status(redis_client, job_id, "processing_media", progress=50)
            logger.info(f"Processing media with duration: {request.duration}")
            
            # Calculate segment durations with minimum duration per image
            num_images = len(media_assets.get('images', []))
            if num_images == 0:
                error_msg = "No images available for processing"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
                
            # For a 15-second video, we want 5-7 images
            # For longer videos, scale up proportionally but cap at 10 images
            target_num_images = min(max(5, round(request.duration / 3)), 10)
            
            # If we have too many images, only use the first target_num_images
            if num_images > target_num_images:
                media_assets['images'] = media_assets['images'][:target_num_images]
                num_images = target_num_images
            
            # Calculate duration per image to fill the total duration
            segment_duration = request.duration / num_images
            
            # Ensure minimum duration of 3 seconds per image
            MIN_DURATION_PER_IMAGE = 3.0
            if segment_duration < MIN_DURATION_PER_IMAGE:
                # Recalculate with fewer images if needed
                num_images = min(num_images, math.floor(request.duration / MIN_DURATION_PER_IMAGE))
                media_assets['images'] = media_assets['images'][:num_images]
                segment_duration = request.duration / num_images
            
            durations = [segment_duration] * num_images
            logger.info(f"Using {num_images} images with {segment_duration:.2f}s per image")
            
            # Get transition preferences
            transition_prefs = request.transitionPreferences
            transition_duration = transition_prefs.duration if transition_prefs else 0.5
            
            # Create video segments with AI-driven transitions if enabled
            video_segments = media_processor.create_video_segments(
                media_assets,
                durations,
                video_style=request.style,
                transition_duration=transition_duration
            )
            
            if not video_segments:
                error_msg = "Failed to create video segments"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
                
            logger.info(f"Created {len(video_segments)} video segments")
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