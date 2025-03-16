# LinkedIn Content Generator - Backend Service

A Flask-based backend service for generating LinkedIn posts and videos using AI. Deployed on Fly.io.

## Features

- 🤖 AI-powered LinkedIn post generation with GPT-3.5 Turbo
- 🎥 Professional video generation with AI narration
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

4. Start the development server:
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
