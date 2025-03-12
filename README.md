# LinkedIn Content Generator - Backend API

The Flask backend service for generating LinkedIn posts and videos using AI.

## Architecture

This is the backend service of our microservices architecture. It handles:

- Post Generation with OpenAI
- Video Generation Pipeline
- Azure Text-to-Speech Integration
- Google Cloud Storage Management
- LinkedIn API Integration

## Service Communication

```mermaid
Backend Service (Flask)
└── Components:
    ├── Content Generation API
    │   ├── Post Generation
    │   └── OpenAI Integration
    ├── Media Processing API
    │   ├── Video Generation
    │   ├── Azure TTS Integration
    │   └── Asset Management
    └── Storage Integration
        └── Google Cloud Storage
```

## Technology Stack

- Flask API
- Python 3.11+
- OpenAI API
- Azure Text-to-Speech
- Google Cloud Storage
- MoviePy for video generation

## Setup

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate  # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```env
   # Service Configuration
   PORT=5000
   FRONTEND_URL=http://localhost:3000
   
   # AI Services
   OPENAI_API_KEY=your_openai_api_key
   AZURE_SPEECH_KEY=your_azure_key
   AZURE_SPEECH_REGION=your_azure_region
   
   # Storage
   GOOGLE_CLOUD_PROJECT=your_project_id
   GOOGLE_CLOUD_STORAGE_BUCKET=your_bucket_name
   ```

4. Run development server:
   ```bash
   python -m flask run
   ```

## Project Structure
```
backend/
├── app/
│   ├── routes/
│   │   ├── post.py        # Post generation endpoints
│   │   ├── video.py       # Video processing endpoints
│   │   └── health.py      # Health check endpoints
│   ├── services/
│   │   ├── openai.py      # OpenAI integration
│   │   ├── azure_tts.py   # Azure TTS integration
│   │   └── storage.py     # GCS integration
│   └── utils/
│       └── helpers.py     # Utility functions
├── requirements.txt
└── main.py
```

## API Endpoints

### Post Generation
```http
POST /api/post/generate
Content-Type: application/json

{
  "theme": "Leadership & Management",
  "tone": "Professional",
  "length": "Medium (500-1000 characters)"
}

Response:
{
  "success": true,
  "data": {
    "content": "Generated post content...",
    "metadata": {
      "theme": "Leadership & Management",
      "tone": "Professional",
      "length": "Medium (500-1000 characters)",
      "characterCount": 750,
      "timestamp": "2024-03-11T13:34:29.789689"
    }
  }
}
```

Length options:
- Short (Under 500 characters)
- Medium (500-1000 characters)
- Long (1000-1500 characters)

The post generation endpoint uses OpenAI's GPT-3.5-turbo model to create engaging LinkedIn posts based on the specified theme, tone, and length. The service includes:
- Input validation using Pydantic
- Automatic retry mechanism for API calls
- Character count validation
- Error handling and detailed error messages

### Video Generation
```http
POST /api/video/generate
Content-Type: application/json
Authorization: Bearer <token>

{
  "postId": "123",
  "style": "slideshow"
}
```

## Implementation History

### March 11, 2024
- Implemented OpenAI integration for post generation
- Added post generation endpoint with validation
- Updated dependencies to include OpenAI, Pydantic, and other required packages
- Added retry mechanism for API calls using tenacity
- Implemented error handling and logging
- Added detailed implementation documentation in `IMPLEMENTATION.md`

### Previous Updates

## Deployment

The backend is deployed on Render as a Web Service:

```yaml
services:
  - type: web
    name: paa-some-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn main:app
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.11
      - key: FRONTEND_URL
        value: https://paa-some-frontend.onrender.com
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests
4. Submit a pull request

## License

This project is proprietary. See LICENSE file for details.
