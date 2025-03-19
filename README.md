# LinkedIn Content Generator - Backend Service

A Flask-based backend service for generating LinkedIn posts and videos using AI. Deployed on Fly.io.

## Features

- 🤖 AI-powered LinkedIn post generation with GPT-3.5 Turbo
- 🎥 Professional video generation with AI narration
- 🖼️ Custom video creation from user-uploaded images
- 🔒 Secure API endpoints
- 📊 Request validation with Pydantic
- 🎯 Customizable post parameters:
  - Theme
  - Tone
  - Target audience
  - Character length (precise control)
  - Video generation option with AI narration

## Tech Stack

- **Framework**: Flask
- **Language**: Python 3.9
- **AI Integration**: OpenAI GPT-3.5 Turbo
- **Video Processing**: MoviePy
- **Validation**: Pydantic
- **Deployment**: Fly.io
- **Storage**: Google Cloud Storage (for video files)
- **Error Handling**: Tenacity for retries

## Prerequisites

Before you begin, ensure you have:
- Python 3.9+ installed
- An OpenAI API key
- Google Cloud credentials (for video features)
- Redis (for caching)
- Required NLTK resources - see [NLTK Requirements](./NLTK_REQUIREMENTS.md) for critical details

## Environment Variables

Create a `.env` file in the root directory:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
GOOGLE_CLOUD_STORAGE_BUCKET=your_bucket_name

# Redis Configuration
REDIS_URL=your_redis_url
REDIS_PASSWORD=your_redis_password

# Flask Configuration
FLASK_ENV=development
FLASK_APP=app
JWT_SECRET_KEY=your_jwt_secret

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,https://your-frontend-domain.com
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/linkedin-content-backend.git
cd linkedin-content-backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install required NLTK resources:
```bash
python nltk_install.py
```

5. Start the development server:
```bash
flask run
```

## API Endpoints

### Post Generation
`POST /api/post/generate`

Generate a LinkedIn post with optional video.

Request body:
```json
{
  "theme": "Leadership & Management",
  "tone": "Professional",
  "targetAudience": "Tech Professionals",
  "length": 500,
  "includeVideo": false
}
```

Response:
```json
{
  "success": true,
  "data": {
    "content": "Generated post content...",
    "metadata": {
      "theme": "Leadership & Management",
      "tone": "Professional",
      "targetAudience": "Tech Professionals",
      "length": 500,
      "characterCount": 485,
      "includeVideo": false,
      "timestamp": "2024-03-16T08:44:22Z"
    }
  }
}
```

### Health Check
`GET /health`

Check service health status.

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-03-16T08:44:22Z"
}
```

## Error Handling

The service uses structured error responses:

```json
{
  "success": false,
  "error": "Error message here"
}
```

Common error scenarios:
- Invalid request data
- OpenAI API errors
- Server errors

## Development

### Running Tests
```bash
pytest
```

### Code Style
```bash
flake8
black .
```

## Deployment

The service is deployed on Fly.io:

```bash
flyctl deploy
```

## Architecture

```
app/
├── __init__.py          # Flask app initialization
├── routes/              # API routes
│   ├── __init__.py
│   └── post.py         # Post generation endpoints
├── services/           # Business logic
│   ├── __init__.py
│   ├── openai.py      # OpenAI integration
│   └── video/         # Video generation (coming soon)
├── models/            # Data models
└── utils/            # Utility functions
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary. All rights reserved.

## Implementation Plan: Video from Uploaded Images

### Overview
This feature allows users to upload their own images (up to 3) to create a custom video instead of using auto-generated media assets.

### Technical Specifications

#### File Storage
- Google Cloud Storage (already integrated) ✅
- Temporary local storage during processing ✅
- Automatic cleanup after processing ✅

#### File Limitations
- Maximum 3 images per video ✅
- Maximum file size per image: 2MB ✅
- Maximum total upload size: 6MB ✅
- Supported formats: JPEG, PNG, GIF ✅

#### Security Measures
- File type validation (MIME type checking) ✅
- Filename sanitization ✅
- Virus/malware scanning (future enhancement) ⏳
- Rate limiting for uploads ⏳

### Implementation Checklist

#### Backend Changes
- [x] Create new API endpoint for image uploads
- [x] Implement file validation (size, type, count)
- [x] Add GCS upload functionality for user images
- [x] Modify video generator to accept user-uploaded images
- [x] Update VideoRequest model to include user image IDs
- [x] Add cleanup process for temporary files

#### Frontend Changes
- [x] Create image upload component with drag-drop support
- [x] Add image preview functionality
- [x] Implement toggle between auto-generated and user-uploaded modes
- [x] Add validation and error handling for uploads
- [x] Update video generation request to include uploaded image IDs

#### Testing
- [x] Unit tests for file validation
- [x] Unit tests for image storage service
- [x] Unit tests for video generation with custom images
- [x] Integration tests for upload workflow
- [ ] End-to-end tests for video generation with custom images

### API Endpoints

#### Upload Images
```
POST /api/video/upload-images
Content-Type: multipart/form-data

Request:
- files: Up to 3 image files (field name: "images")
- user_id: (Optional) User identifier for organizing uploads

Response:
{
  "success": true,
  "message": "Successfully uploaded 2 images",
  "images": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "filename": "example.jpg",
      "storage_path": "user_uploads/images/2024/03/17/anonymous/f47ac10b-58cc-4372-a567-0e02b2c3d479.jpg",
      "url": "https://storage.googleapis.com/bucket/...",
      "content_type": "image/jpeg"
    },
    ...
  ],
  "image_ids": ["f47ac10b-58cc-4372-a567-0e02b2c3d479", "..."]
}
```

#### Generate Video with Custom Images
```
POST /api/video/generate
Content-Type: application/json

Request:
{
  "content": "Post content...",
  "style": "professional",
  "duration": 30,
  "user_image_ids": ["f47ac10b-58cc-4372-a567-0e02b2c3d479", "..."]
}

Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Video generation started"
}
```

#### Check Video Generation Status
```
GET /api/video/status/<job_id>

Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "video_url": "https://storage.googleapis.com/bucket/videos/2024/03/17/550e8400-e29b-41d4-a716-446655440000.mp4",
  "created_at": "2024-03-17T14:30:00Z",
  "updated_at": "2024-03-17T14:35:00Z"
}
```

## Critical Dependencies

### NLTK Resources

The application relies on specific NLTK resources for text analysis and content processing. Missing resources can cause failures in the content analysis pipeline. See [NLTK Requirements](./NLTK_REQUIREMENTS.md) for detailed information about:

- Required resources
- Installation methods
- Error handling strategies
- Troubleshooting steps

**Important:** Always verify NLTK resources during deployment to prevent service disruptions.
