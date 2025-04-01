# Video Captions Feature: Updated Implementation Plan

## Lessons Learned from Previous Attempts

Our previous attempts to implement the video captions feature resulted in breaking the video generation functionality. Here are the key issues we identified and how we'll address them:

1. **API Contract Mismatch**: The frontend and backend had different expectations for request/response formats.
   - **Solution**: Clearly document and maintain API contracts for both sides.

2. **Breaking Changes**: Changes to core components affected existing functionality.
   - **Solution**: Use feature flags and maintain backward compatibility.

3. **Stock Media Handling**: Changes to the video generation feature affected stock media handling.
   - **Solution**: Ensure special handling for stock media remains intact.

4. **Testing Gaps**: Insufficient testing of all video generation modes.
   - **Solution**: Comprehensive testing across all media types.

## Revised Implementation Strategy

### Phase 1: Preparation (Non-intrusive)

1. **Document Current State**
   - [x] Create API contract documents
   - [ ] Trace the current request/response flow
   - [ ] Map out stock media handling

2. **Backend Feature Flag**
   - [ ] Add a `ENABLE_CAPTIONS` feature flag in backend code
   - [ ] Implement conditional processing based on flag

3. **Set Up Testing Environment**
   - [ ] Create test scripts for all video generation modes
   - [ ] Set up automated tests for regression detection

### Phase 2: Backend Implementation (Isolated)

1. **Caption Parsing**
   - [ ] Add caption preferences to Pydantic models
   - [ ] Ensure models maintain backward compatibility
   - [ ] Implement caption data extraction logic

2. **Caption Rendering Service**
   - [ ] Create isolated caption rendering module
   - [ ] Implement caption styling and positioning
   - [ ] Add caption timing calculation (optional fallback if timing data missing)

3. **Video Generation Integration**
   - [ ] Modify video generation service to use caption renderer when enabled
   - [ ] Maintain full backward compatibility
   - [ ] Log caption usage for monitoring

### Phase 3: Frontend Updates (Safe)

1. **Caption Timing Data**
   - [ ] Implement content analysis to generate caption timing
   - [ ] Test timing calculation with different content

2. **Request Updates**
   - [ ] Update frontend to send caption data in correct format
   - [ ] Ensure caption data is only included when captions are enabled
   - [ ] Add validation for caption parameters

3. **UI Refinements**
   - [ ] Update caption preview
   - [ ] Add caption toggle in video player
   - [ ] Implement caption style preview

### Phase 4: Testing and Verification

1. **Integration Testing**
   - [ ] Test video generation with captions enabled
   - [ ] Test video generation with captions disabled
   - [ ] Verify that both paths work correctly

2. **Media Type Testing**
   - [ ] Test with AI-generated media
   - [ ] Test with custom uploaded images
   - [ ] Test with stock media
   - [ ] Ensure all three modes work with and without captions

3. **Performance Testing**
   - [ ] Measure impact of caption rendering on generation time
   - [ ] Test with different caption styles and layouts

### Phase 5: Gradual Rollout

1. **Internal Testing**
   - [ ] Enable feature for development team
   - [ ] Fix any issues discovered

2. **Limited User Release**
   - [ ] Enable for a small percentage of users
   - [ ] Monitor error rates and performance

3. **Full Rollout**
   - [ ] Enable feature for all users
   - [ ] Continue monitoring for issues

## Specific Technical Changes

### Backend Changes

1. **Model Updates**
   ```python
   # Add to app/models/video.py
   class CaptionStyle(BaseModel):
       position: Literal["top", "bottom", "center"] = "bottom"
       size: int = Field(default=24, ge=10, le=48)
       color: str = Field(default="#ffffff")
       backgroundColor: Optional[str] = Field(default="#000000")
       opacity: Optional[float] = Field(default=0.7, ge=0, le=1)
       font: Optional[str] = Field(default="Arial")

   class CaptionPreferences(BaseModel):
       enabled: bool = Field(default=False)
       style: Optional[CaptionStyle] = None

   class VideoPreferences(BaseModel):
       # Existing fields...
       captions: Optional[CaptionPreferences] = None
   ```

2. **Caption Rendering Service**
   ```python
   # New file: app/services/video/caption_renderer.py
   class CaptionRenderer:
       def __init__(self, captions_enabled=False, caption_style=None):
           self.enabled = captions_enabled
           self.style = caption_style or {}
           
       def render_captions(self, video_path, caption_data, output_path):
           """Render captions onto video if enabled"""
           if not self.enabled:
               return video_path  # No captions, return original
               
           # Implement caption rendering
           # ...
           
           return output_path
   ```

3. **Safe Integration in Video Generator**
   ```python
   # Modify app/services/video/generator.py
   def generate_video(self, job_id, request):
       # Existing code...
       
       # Extract caption preferences safely
       captions_enabled = False
       caption_style = None
       
       if hasattr(request, 'videoPreferences') and request.videoPreferences:
           if hasattr(request.videoPreferences, 'captions') and request.videoPreferences.captions:
               captions_enabled = request.videoPreferences.captions.enabled
               caption_style = request.videoPreferences.captions.style
       
       # Initialize caption renderer
       caption_renderer = CaptionRenderer(captions_enabled, caption_style)
       
       # After video is generated
       if captions_enabled:
           video_path = caption_renderer.render_captions(
               video_path,
               caption_data,
               os.path.join(work_dir, "captioned_video.mp4")
           )
       
       # Continue with existing code...
   ```

### Frontend Changes

1. **Caption Timing Generation**
   ```typescript
   // Add to app/utils/contentAnalysis.ts
   function generateCaptionTiming(content: string, segmentTiming: any): any[] {
     // Implementation
     return captionChunks;
   }
   ```

2. **Safe Request Construction**
   ```typescript
   // In VideoGenerator.tsx, modify the request building
   const requestBody = {
     content,
     style,
     duration,
     postId,
     contentAnalysis,
     // Only include captions if explicitly enabled
     ...(mediaType === 'ai' && {
       videoPreferences: {
         // Existing preferences
         ...(captions.enabled && {
           captions: {
             enabled: captions.enabled,
             style: captions.style,
             // Add timing data if available
             timing: contentAnalysis.segments?.map(segment => ({
               // Timing details
             }))
           }
         })
       }
     }),
     // Maintain existing stock media handling
     ...(mediaType === 'stock' && {
       stockMediaUrls: mediaIds,
       isStockMedia: true,
     }),
     // Maintain existing custom upload handling
     ...(mediaType === 'custom' && {
       userImageIds: mediaIds,
       isCustomUpload: true
     }),
     mediaType
   };
   ```

## Monitoring and Rollback Plan

### Monitoring

1. **Key Metrics to Track**
   - Video generation success rate (overall)
   - Video generation success rate (with captions)
   - Video generation time (with vs. without captions)
   - Error rates by media type

2. **Logging**
   - Enhanced logging for caption-related operations
   - Track caption rendering status

### Rollback Plan

1. **Fast Rollback Option**
   - Disable captions feature flag in backend
   - Revert to existing UI without caption options

2. **Emergency Procedure**
   - If severe issues occur, roll back both frontend and backend changes
   - Prepare rollback commits in advance

## Success Criteria

1. Video generation works for all media types with the same reliability as before
2. Captions are correctly rendered in videos when enabled
3. No performance degradation beyond acceptable limits
4. Positive user feedback on caption quality and usefulness 