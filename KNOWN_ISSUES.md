# Known Issues - LinkedIn Content Backend

This document tracks known issues in the LinkedIn Content Backend, their status, and any workarounds or planned fixes.

## Video Generation

### Custom Image Handling (March 2024)

#### Issue: User-uploaded Images Not Used in Video Generation
- **Status**: Fixed (Pending Verification)
- **Description**: When users provided custom images for video generation, the system would sometimes fall back to using Unsplash images instead if there were any issues retrieving the user images.
- **Root Cause**: The `generate_video` method in `generator.py` was attempting to fetch media assets from Unsplash as a fallback when user images couldn't be fetched, rather than failing with a clear error.
- **Fix Implemented**: Modified the video generation logic to only use user-uploaded images when provided and to fail with a clear error message if they can't be fetched, rather than falling back to Unsplash.
- **Verification Steps**:
  1. Upload custom images via the frontend
  2. Generate video with those custom images
  3. Verify that only the uploaded images appear in the video
  4. Test with invalid image IDs to verify proper error handling

#### Issue: Inefficient Image URL Retrieval
- **Status**: Fixed (Pending Verification)
- **Description**: The method to retrieve image URLs from Google Cloud Storage was inefficient, potentially causing performance issues when dealing with many images.
- **Root Cause**: The `get_image_url` method in `image_storage.py` was listing all blobs in the folder to find a specific image, which is inefficient as the number of images grows.
- **Fix Implemented**: Improved the method to use a more specific prefix that includes the image ID and to retrieve the first matching blob directly without iterating through all blobs.
- **Verification Steps**:
  1. Test image retrieval with a large number of images in the bucket
  2. Monitor response times
  3. Check logs for any errors

## Environment Setup

### NLTK Resources Loading
- **Status**: Known Issue
- **Description**: Missing NLTK resources can cause startup failures or content processing issues.
- **Workaround**: Always verify NLTK resources during deployment using the provided verification script.
- **Planned Fix**: Automate the verification of NLTK resources during the container build process.

## API Endpoints

### Rate Limiting
- **Status**: Planned Enhancement
- **Description**: The API currently lacks rate limiting, which could lead to abuse or excessive resource usage.
- **Planned Fix**: Implement rate limiting middleware using Flask-Limiter or a similar library.

## Deployment

### Environment Variable Management
- **Status**: Known Issue
- **Description**: Deployment can fail if required environment variables are missing or incorrectly formatted.
- **Workaround**: Use the verified `.env.example` as a template and double-check all variables before deployment.
- **Planned Fix**: Implement a startup check that validates all required environment variables.

---

*This document is maintained as part of the development process and is updated when new issues are discovered or resolved. Last updated: March 19, 2024.* 