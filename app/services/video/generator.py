import logging
import json
from typing import Dict, List
from datetime import datetime
from redis import Redis
from ..media.fetcher import media_fetcher
from ..media.processor import media_processor
from ..media.audio import audio_generator
from ..media.text_processor import text_processor
from .storage import storage_service
from app.models.video import VideoRequest
import traceback
import math

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class VideoGenerator:
    STEPS = {
        'initialized': {'step': 1, 'message': 'Initializing video generation'},
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
        try:
            logger.info(f"Starting video generation for job {job_id}")
            logger.info(f"Request data: {request.model_dump_json()}")
            
            # Update status to processing
            self.update_job_status(redis_client, job_id, "initialized", progress=0)
            
            # Fetch media assets
            self.update_job_status(redis_client, job_id, "media_fetching", progress=10)
            logger.info(f"Fetching media assets for content: {request.content}")
            media_assets = media_fetcher.fetch_media(request.content, duration=request.duration)
            logger.info(f"Media assets fetched: {json.dumps(media_assets, indent=2)}")
            self.update_job_status(redis_client, job_id, "media_fetched", progress=20)
            
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
            
            if audio_file:
                logger.info(f"Audio generated successfully: {audio_file}")
                self.update_job_status(redis_client, job_id, "audio_generated", progress=40)
            else:
                logger.error("Audio generation returned None")
                error_msg = "Failed to generate audio file - check logs for detailed error"
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
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
            
            # Create video segments
            video_segments = media_processor.create_video_segments(media_assets, durations)
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
            
            if not final_video:
                error_msg = "Failed to combine audio and video"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
            # Upload to storage
            self.update_job_status(redis_client, job_id, "uploading", progress=90)
            logger.info(f"Uploading video to storage: {final_video}")
            video_url = storage_service.upload_video(final_video, job_id)
            logger.info(f"Video uploaded: {video_url}")
            
            if not video_url:
                error_msg = "Failed to upload video to storage"
                logger.error(error_msg)
                self.update_job_status(redis_client, job_id, "failed", error=error_msg)
                raise Exception(error_msg)
            
            # Update final status
            self.update_job_status(redis_client, job_id, "completed", progress=100, video_url=video_url)
            logger.info("Video generation completed successfully")
            
            return video_url
            
        except Exception as e:
            error_msg = f"Error generating video: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.update_job_status(redis_client, job_id, "failed", error=error_msg)
            raise

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