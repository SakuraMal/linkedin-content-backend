# Stock Media Handling

## Overview

Stock media handling is a critical part of the video generation process. This document outlines how stock media URLs are passed from the frontend to the backend and how they are processed during video generation.

## Request Format

The frontend sends stock media URLs in one of two fields:

```json
{
  // Standard fields (content, style, etc.)
  
  // Primary field for stock media URLs (frontend naming convention)
  "stockMediaUrls": {
    "media-id-1": "https://example.com/media1.jpg",
    "media-id-2": "https://example.com/media2.jpg"
  },
  
  // Alternative field (backend naming convention, used for backward compatibility)
  "stockImageUrls": {
    "media-id-1": "https://example.com/media1.jpg",
    "media-id-2": "https://example.com/media2.jpg"
  },
  
  // Flag indicating stock media is being used
  "isStockMedia": true,
  
  // Media type indicator
  "mediaType": "stock"
}
```

## Backend Processing

The backend code employs a robust strategy to find stock media URLs regardless of where they appear in the request:

1. Checks `request_data.__dict__['stockMediaUrls']`
2. Checks `request_data.__dict__['stockImageUrls']`
3. Checks `request_data['stockMediaUrls']` (if request_data is a dict)
4. Checks `request_data['stockImageUrls']` (if request_data is a dict)
5. Checks `request_data.model_extra['stockMediaUrls']`
6. Checks `request_data.model_extra['stockImageUrls']`
7. Attempts to extract from `model_dump()` result

This multi-layered approach ensures stock media URLs can be found regardless of how they're transmitted from the frontend.

## Model Definition

In the Pydantic model, stock media URLs are defined as optional fields:

```python
class VideoRequest(BaseModel):
    # ... other fields ...
    
    # Add explicit fields for stock media URLs mapping (supporting both naming conventions)
    stockMediaUrls: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Mapping of stock media IDs to their URLs"
    )
    stockImageUrls: Optional[Dict[str, str]] = Field(
        default=None, 
        description="Alternative name for stockMediaUrls"
    )
    
    class Config:
        # Allow unknown fields to handle different frontend formats
        extra = "allow"
```

## Important Considerations

When implementing captions or other features:

1. **Preserve Both Fields**: Both `stockMediaUrls` and `stockImageUrls` must be preserved for backward compatibility
2. **Maintain Flexible Extraction**: The multi-layered approach for finding these fields must be preserved
3. **Dict Format**: Stock media URLs are expected as a dictionary mapping IDs to URLs
4. **Field Location Flexibility**: The fields might appear in different locations in the request based on how the frontend constructs it

## Example Flow

1. Frontend constructs request with `stockMediaUrls` and `isStockMedia: true`
2. Backend parses request into `VideoRequest` model
3. Backend extracts stock media URLs using multi-layered approach
4. Backend downloads stock media for processing
5. Backend generates video using the stock media 