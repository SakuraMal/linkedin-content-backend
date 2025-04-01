# Video Generation API Contract

## Overview

This document outlines the contract between the frontend and backend for video generation features. It covers the expected request and response formats for all video generation endpoints.

## Video Generation Endpoint

### POST `/api/video/generate`

Generates a video from content description and preferences.

#### Request

```json
{
  "content": "Text content to transform into a video",
  "style": "professional", // Acceptable values: "professional", "casual", "educational", "entertaining"
  "duration": 30, // Duration in seconds (5-120)
  "postId": "optional-post-id", // Optional, for tracking
  "contentAnalysis": {
    "videoKeywords": ["keyword1", "keyword2"],
    "segments": [
      {
        "text": "Segment text",
        "type": "intro", // "intro", "main", or "conclusion"
        "timing": {
          "startTime": 0,
          "endTime": 10,
          "duration": 10,
          "captionChunks": [
            {
              "text": "Caption chunk text",
              "startTime": 0,
              "endTime": 5
            }
          ]
        }
      }
    ]
  },
  "videoPreferences": {
    "requirePexelsVideo": true,
    "minVideoSegments": 2,
    "transitionStyle": "crossfade", // "crossfade", "cinematic", "dynamic"
    "videoKeywords": ["keyword1", "keyword2"],
    "audio": {
      "includeBackgroundMusic": true,
      "musicStyle": "corporate", // "corporate", "energetic", "calm", "dramatic"
      "volume": 0.1, // 0-1
      "fadeInDuration": 2, // seconds
      "fadeOutDuration": 2 // seconds
    },
    "captions": {
      "enabled": false,
      "style": {
        "position": "bottom", // "top", "bottom", "center"
        "size": 24,
        "color": "#ffffff",
        "font": "Arial", // optional
        "backgroundColor": "#000000", // optional
        "opacity": 0.7 // optional, 0-1
      }
    }
  },
  "user_image_ids": [], // Optional, for custom uploaded images
  "stockMediaUrls": [], // Optional, for stock media
  "stockImageUrls": [], // Optional, for stock images
  "isStockMedia": false, // Optional, indicates if using stock media
  "isCustomUpload": false, // Optional, indicates if using custom uploads
  "mediaType": "ai" // "ai", "custom", or "stock"
}
```

#### Response

Success Response:
```json
{
  "success": true,
  "data": {
    "job_id": "123e4567-e89b-12d3-a456-426614174000"
  },
  "message": "Video generation started"
}
```

Error Response:
```json
{
  "success": false,
  "error": "Error message",
  "details": {
    "field": "content",
    "message": "Content is required"
  }
}
```

## Video Status Endpoint

### GET `/api/video/status/{job_id}`

Gets the status of a video generation job.

#### Request

Path parameter: `job_id` - The job ID returned from the generation endpoint

#### Response

Success Response:
```json
{
  "success": true,
  "data": {
    "status": "processing", // "queued", "processing", "completed", "error"
    "progress": 50, // percentage (0-100)
    "video_url": null, // only present when status is "completed"
    "created_at": "2025-04-01T12:00:00Z",
    "updated_at": "2025-04-01T12:05:00Z",
    "error": null // only present when status is "error"
  }
}
```

Error Response:
```json
{
  "success": false,
  "error": "Job not found"
}
```

## Caption Implementation Notes

### Current State

As of the current implementation:

1. The frontend includes caption preferences in the request but captions are not being rendered in the final video.
2. The backend receives the caption parameters but may not be processing them correctly.

### Required Changes

When implementing captions:

1. Keep existing video generation flow intact by making caption rendering optional.
2. Backend must recognize and process the `captions` object in the `videoPreferences`.
3. Caption timing data is derived from `contentAnalysis.segments[].timing`.

## API Version Information

Current API version: v1 (implicit)

The API does not currently use explicit versioning headers or URL paths. Future versions should consider adding explicit versioning. 