# LinkedIn Content Backend - Current Architecture

## Overview
The backend service handles post generation and video creation through a Redis-based status tracking system, deployed on Fly.io.

## Core Components

### 1. API Layer (Flask Application)
```mermaid
graph TD
    Frontend[Next.js Frontend]
    Backend[Flask Backend]
    Redis[Redis Status Tracking]
    GCS[Google Cloud Storage]
    CORS[CORS Layer]
    
    Frontend -->|1. Generate Video Request| CORS
    CORS -->|2. Validated Request| Backend
    Backend -->|3. Return job_id| Frontend
    Frontend -->|4. Poll Status| Backend
    Backend -->|Track Progress| Redis
    Backend -->|Store Videos| GCS
```

### 2. CORS Configuration
See detailed documentation in [CORS.md](./docs/CORS.md)

```python
# Flask CORS configuration (tested and verified March 13, 2025)
CORS(app, 
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'OPTIONS'])
```

Key aspects:
- Initialized before blueprints and routes
- Configured via environment variables
- Supports credentials for authenticated requests
- Handles preflight requests automatically

### 3. Video Generation Flow
1. **Request Handling**
   ```python
   @app.route('/api/video/generate', methods=['POST'])
   def generate_video():
       job_id = str(uuid.uuid4())
       redis_client.set(f"job:{job_id}:status", "queued")
       # Start processing in background
       return {"job_id": job_id}, 202
   ```

2. **Status Tracking**
   ```python
   @app.route('/api/video/status/<job_id>', methods=['GET'])
   def get_status(job_id):
       status = redis_client.get(f"job:{job_id}:status")
       progress = redis_client.get(f"job:{job_id}:progress")
       return {
           "status": status,
           "progress": progress,
           "video_url": video_url if status == "completed" else None
       }
   ```

3. **Video Processing**
   ```python
   def process_video(job_id, content):
       try:
           redis_client.set(f"job:{job_id}:status", "processing")
           # Process video...
           redis_client.set(f"job:{job_id}:progress", "100")
           redis_client.set(f"job:{job_id}:status", "completed")
       except Exception as e:
           redis_client.set(f"job:{job_id}:status", "error")
   ```

## Service Configuration

### 1. CORS Origins
```env
# Comma-separated list of allowed origins
CORS_ORIGINS=http://localhost:3000,https://linkedin-content-frontend.vercel.app
```

### 2. Redis Configuration (Upstash)
```env
REDIS_URL=rediss://default:${REDIS_PASSWORD}@fly-linkedin-content-redis.upstash.io:6379
```
- Handles job status tracking
- Stores progress information
- 24-hour data retention

### 3. Google Cloud Storage
```env
GOOGLE_CLOUD_PROJECT=paa-some
GOOGLE_CLOUD_STORAGE_BUCKET=paa-some-videos
```
- Stores generated videos
- Provides public URLs for video access

### 4. Environment Variables
```env
# Service Configuration
PORT=8080
ENVIRONMENT=production

# External Services
REDIS_URL=...
GOOGLE_CLOUD_STORAGE_BUCKET=...
UNSPLASH_ACCESS_KEY=...
```

## Implementation Details

### 1. Status Management
- **States**:
  - `queued`: Job received, waiting to start
  - `processing`: Video generation in progress
  - `completed`: Video ready, URL available
  - `error`: Processing failed

- **Progress Tracking**:
  ```python
  # Redis Keys Pattern
  f"job:{job_id}:status"    # Current state
  f"job:{job_id}:progress"  # Percentage complete
  f"job:{job_id}:video_url" # Final video URL
  ```

### 2. Error Handling
```python
try:
    # Process video
    await process_video_content()
except Exception as e:
    await redis.set(f"job:{job_id}:status", "error")
    await redis.set(f"job:{job_id}:error", str(e))
```

### 3. Cleanup
- Redis TTL: 24 hours
- Temporary files removed after processing
- Error states preserved for debugging

## Frontend Integration

### 1. Video Generation Request
```typescript
const response = await fetch('/api/video/generate', {
  method: 'POST',
  body: JSON.stringify({ content, style })
});
const { job_id } = await response.json();
```

### 2. Status Polling
```typescript
const pollStatus = async (jobId: string) => {
  const response = await fetch(`/api/video/status/${jobId}`);
  const status = await response.json();
  if (status.status === 'completed') {
    return status.video_url;
  }
  // Continue polling...
};
```

## Deployment (Fly.io)

### 1. Resources
- 512MB RAM
- Shared CPU
- 1GB storage

### 2. Configuration
```toml
# fly.toml
[env]
  PORT = "8080"
  PYTHONUNBUFFERED = "1"
  FLASK_APP = "wsgi.py"
  FLASK_ENV = "production"

[http_service]
  internal_port = 8080
  force_https = true
```

## Testing

### 1. Status Management Tests
```python
async def test_video_generation_flow():
    job_id = await generate_video(content)
    assert await get_job_status(job_id) == "queued"
    # Test status transitions...
```

### 2. Integration Tests
```python
async def test_full_video_generation():
    response = await client.post("/api/video/generate", json={...})
    job_id = response.json()["job_id"]
    # Test status polling...
```

## Video Generation Architecture

### 1. Media Processing Pipeline
```mermaid
graph TD
    Request[Generate Video Request]
    Media[Media Processor]
    Audio[Audio Generator]
    Storage[Storage Service]
    
    Request -->|1. Process Request| Media
    Media -->|2. Create Video Segments| Media
    Media -->|3. Generate Audio| Audio
    Media -->|4. Combine Audio & Video| Media
    Media -->|5. Store Result| Storage
    Storage -->|6. Return Signed URL| Request
```

### 2. Media Processor
```python
class MediaProcessor:
    def create_video_segments(self, media_assets: List[str], durations: List[float]) -> List[str]:
        """Creates video segments from images with specified durations"""
        # Process each image into a video segment
        return video_segments

    def combine_with_audio(self, video_segments: List[str], audio_file: str) -> str:
        """Combines video segments with audio track"""
        # Merge segments and audio
        return final_video_path
```

### 3. Audio Generation
```python
class AudioGenerator:
    def generate_audio(self, text: str) -> Optional[str]:
        """Synchronous wrapper for audio generation"""
        try:
            return self._generate_audio_async(text)
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return None

    async def _generate_audio_async(self, text: str) -> str:
        """Asynchronous audio generation using Edge TTS"""
        # Generate audio file
        return audio_file_path
```

### 4. Storage Service (Google Cloud Storage)
```python
class StorageService:
    def upload_video(self, file_path: str, job_id: str) -> str:
        """Upload video and generate signed URL"""
        storage_path = f"videos/{date_prefix}/{job_id}.mp4"
        blob = self.bucket.blob(storage_path)
        blob.upload_from_filename(file_path)
        
        # Generate 7-day signed URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(days=7),
            method="GET"
        )
        return url
```

### 5. Configuration Settings
```env
# Google Cloud Storage
GOOGLE_CLOUD_STORAGE_BUCKET=paa-some-videos
GOOGLE_CLOUD_PROJECT=paa-some

# Video Generation
VIDEO_SEGMENT_DURATION=5  # seconds per segment
MAX_VIDEO_DURATION=60     # maximum total duration
AUDIO_SAMPLE_RATE=44100   # audio quality setting

# Edge TTS Configuration
EDGE_TTS_VOICE="en-US-JennyNeural"
EDGE_TTS_RATE="+0%"      # normal speed
EDGE_TTS_VOLUME="+0%"    # normal volume
```

### 6. Error Handling
```python
try:
    # Generate video segments
    video_segments = media_processor.create_video_segments(media_assets, durations)
    if not video_segments:
        raise ValueError("Failed to create video segments")

    # Generate audio
    audio_file = audio_generator.generate_audio(text)
    if not audio_file:
        raise ValueError("Failed to generate audio")

    # Combine and store
    final_video = media_processor.combine_with_audio(video_segments, audio_file)
    video_url = storage_service.upload_video(final_video, job_id)
    
except Exception as e:
    logger.error(f"Video generation failed: {str(e)}")
    redis_client.set(f"job:{job_id}:status", "error")
    redis_client.set(f"job:{job_id}:error", str(e))
```

### 7. Progress Tracking
```python
def update_progress(job_id: str, stage: str, percentage: int):
    """Update job progress in Redis"""
    redis_client.set(f"job:{job_id}:status", "processing")
    redis_client.set(f"job:{job_id}:progress", percentage)
    redis_client.set(f"job:{job_id}:stage", stage)

# Usage in pipeline
update_progress(job_id, "media_processing", 20)
update_progress(job_id, "audio_generation", 40)
update_progress(job_id, "combining_media", 60)
update_progress(job_id, "uploading", 80)
update_progress(job_id, "completed", 100)
```

### 8. Cleanup and Resource Management
- Temporary files are deleted after processing
- Failed jobs are preserved for 24 hours
- Video URLs expire after 7 days
- Background tasks are properly terminated

### 9. Testing Endpoints
```
GET  /test                     # Test video generation interface
POST /api/video/generate       # Start video generation
GET  /api/video/status/{id}    # Check generation status
GET  /api/video/{id}          # Get video URL
```

---
> Note: Previous architecture files (ARCHITECTURE.md, VIDEO_ARCHITECTURE.md, IMPLEMENTATION.md) are preserved for historical reference but should not be used for current implementation. 