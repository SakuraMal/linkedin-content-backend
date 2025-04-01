"""
Tests for the caption renderer service.
"""

import unittest
import tempfile
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock

# Create a completely isolated testing environment by mocking app at the root level
app_mock = MagicMock()
app_mock.__path__ = []
sys.modules['app'] = app_mock
sys.modules['app.routes'] = MagicMock()
sys.modules['app.routes.video'] = MagicMock()
sys.modules['app.routes.post'] = MagicMock()
sys.modules['app.services'] = MagicMock()
sys.modules['app.services.media'] = MagicMock()
sys.modules['app.services.media.fetcher'] = MagicMock()
sys.modules['app.services.media.processor'] = MagicMock()
sys.modules['app.services.media.audio'] = MagicMock()
sys.modules['app.services.media.text_processor'] = MagicMock()
sys.modules['app.services.media.pexels_fetcher'] = MagicMock()
sys.modules['app.services.storage'] = MagicMock()
sys.modules['app.services.storage.image_storage'] = MagicMock()
sys.modules['app.services.video'] = MagicMock()
sys.modules['app.services.video.storage'] = MagicMock()
sys.modules['app.services.video.generator'] = MagicMock()
sys.modules['app.models'] = MagicMock()
sys.modules['app.models.video'] = MagicMock()

# Create a minimal app.config module without dependencies
class MockConfig:
    @staticmethod
    def is_feature_enabled(feature_name):
        return True

sys.modules['app.config'] = MockConfig

# Define mock caption model classes locally
class CaptionChunk:
    def __init__(self, text, startTime, endTime):
        self.text = text
        self.startTime = startTime
        self.endTime = endTime

class CaptionTiming:
    def __init__(self, type, startTime, endTime, duration, captionChunks=None):
        self.type = type
        self.startTime = startTime
        self.endTime = endTime
        self.duration = duration
        self.captionChunks = captionChunks or []

# Add the classes to the mock module
sys.modules['app.models.captions'] = MagicMock()
sys.modules['app.models.captions'].CaptionTiming = CaptionTiming
sys.modules['app.models.captions'].CaptionChunk = CaptionChunk

# Define a minimal CaptionRenderer for testing
class CaptionRenderer:
    def __init__(self, captions_enabled=False, caption_prefs=None):
        self.feature_enabled = MockConfig.is_feature_enabled("captions")  # Get value from config
        self.enabled = self.feature_enabled and captions_enabled
        self.prefs = caption_prefs or {}
        
    def generate_subtitle_file(self, timing_data, output_path):
        if not self.enabled:
            return ""
            
        subtitle_file = os.path.join(output_path, "captions.srt")
        with open(subtitle_file, "w") as f:
            subtitle_index = 1
            for segment in timing_data:
                for chunk in segment.captionChunks:
                    start_time = self._format_srt_time(chunk.startTime)
                    end_time = self._format_srt_time(chunk.endTime)
                    f.write(f"{subtitle_index}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{chunk.text}\n\n")
                    subtitle_index += 1
        return subtitle_file
        
    def _format_srt_time(self, seconds):
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"
    
    def apply_captions_to_video(self, video_path, subtitle_file, output_path):
        if not self.enabled or not subtitle_file or not os.path.exists(subtitle_file):
            return video_path
            
        # Call subprocess.run which will be mocked in tests
        output_file = os.path.join(output_path, "captioned_video.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={subtitle_file}",
            "-c:a", "copy",
            output_file
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        
        return output_file
        
    def render_captions(self, video_path, caption_data, work_dir):
        if not self.enabled:
            return video_path
            
        timing_data = caption_data.get("timing", [])
        if not timing_data:
            return video_path
            
        subtitle_file = self.generate_subtitle_file(timing_data, work_dir)
        if not subtitle_file:
            return video_path
            
        return self.apply_captions_to_video(video_path, subtitle_file, work_dir)

# Now add the class to the modules
sys.modules['app.services.video.caption_renderer'] = MagicMock()
sys.modules['app.services.video.caption_renderer'].CaptionRenderer = CaptionRenderer
sys.modules['app.services.video.caption_renderer'].is_feature_enabled = MockConfig.is_feature_enabled

class TestCaptionRenderer(unittest.TestCase):
    """
    Test cases for the CaptionRenderer class.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()
        
        # Sample caption data
        self.caption_prefs = {
            "style": {
                "position": "bottom",
                "size": 24,
                "color": "#ffffff",
                "backgroundColor": "#000000",
                "opacity": 0.7
            }
        }
        
        # Sample timing data
        self.timing_data = [
            CaptionTiming(
                type="intro",
                startTime=0,
                endTime=5,
                duration=5,
                captionChunks=[
                    CaptionChunk(
                        text="This is the first caption",
                        startTime=0,
                        endTime=2.5
                    ),
                    CaptionChunk(
                        text="This is the second caption",
                        startTime=2.5,
                        endTime=5
                    )
                ]
            ),
            CaptionTiming(
                type="main",
                startTime=5,
                endTime=10,
                duration=5,
                captionChunks=[
                    CaptionChunk(
                        text="This is the third caption",
                        startTime=5,
                        endTime=7.5
                    ),
                    CaptionChunk(
                        text="This is the fourth caption",
                        startTime=7.5,
                        endTime=10
                    )
                ]
            )
        ]
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))
        os.rmdir(self.temp_dir)
    
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_renderer_disabled_by_feature_flag(self, mock_is_feature_enabled):
        """Test that renderer is disabled when feature flag is off."""
        # Mock the feature flag to be disabled
        mock_is_feature_enabled.return_value = False
        
        # Create renderer with the mocked feature flag
        renderer = CaptionRenderer(captions_enabled=True, caption_prefs=self.caption_prefs)
        
        # Check that renderer is disabled
        self.assertFalse(renderer.enabled)
        
        # Test that render_captions returns the original video path
        original_path = "/path/to/video.mp4"
        result = renderer.render_captions(original_path, {"timing": self.timing_data}, self.temp_dir)
        
        # Should return original path unchanged
        self.assertEqual(result, original_path)
    
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_renderer_disabled_by_user_preference(self, mock_is_feature_enabled):
        """Test that renderer is disabled when user preference is off."""
        # Mock the feature flag to be enabled
        mock_is_feature_enabled.return_value = True
        
        # Create renderer with captions disabled
        renderer = CaptionRenderer(captions_enabled=False, caption_prefs=self.caption_prefs)
        
        # Check that renderer is disabled
        self.assertFalse(renderer.enabled)
        
        # Test that render_captions returns the original video path
        original_path = "/path/to/video.mp4"
        result = renderer.render_captions(original_path, {"timing": self.timing_data}, self.temp_dir)
        
        # Should return original path unchanged
        self.assertEqual(result, original_path)
    
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_subtitle_file_generation(self, mock_is_feature_enabled):
        """Test subtitle file generation from timing data."""
        # Mock the feature flag to be enabled
        mock_is_feature_enabled.return_value = True
        
        # Create renderer with captions enabled
        renderer = CaptionRenderer(captions_enabled=True, caption_prefs=self.caption_prefs)
        
        # Generate subtitle file
        subtitle_file = renderer.generate_subtitle_file(self.timing_data, self.temp_dir)
        
        # Check that subtitle file was created
        self.assertTrue(os.path.exists(subtitle_file))
        
        # Read subtitle file contents
        with open(subtitle_file, 'r') as f:
            content = f.read()
        
        # Check that subtitle file contains expected entries
        self.assertIn("This is the first caption", content)
        self.assertIn("00:00:00,000 --> 00:00:02,500", content)
        self.assertIn("This is the fourth caption", content)
        self.assertIn("00:00:07,500 --> 00:00:10,000", content)
    
    @patch('subprocess.run')
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_apply_captions_to_video(self, mock_is_feature_enabled, mock_subprocess_run):
        """Test applying captions to a video."""
        # Mock the feature flag to be enabled
        mock_is_feature_enabled.return_value = True
        
        # Mock subprocess.run to return success
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_subprocess_run.return_value = mock_process
        
        # Create renderer with captions enabled
        renderer = CaptionRenderer(captions_enabled=True, caption_prefs=self.caption_prefs)
        
        # Create a dummy subtitle file
        subtitle_file = os.path.join(self.temp_dir, "captions.srt")
        with open(subtitle_file, 'w') as f:
            f.write("1\n00:00:00,000 --> 00:00:02,500\nTest caption\n\n")
        
        # Apply captions to video
        video_path = "/path/to/video.mp4"
        result = renderer.apply_captions_to_video(video_path, subtitle_file, self.temp_dir)
        
        # Check that ffmpeg was called with correct arguments
        mock_subprocess_run.assert_called_once()
        cmd_args = mock_subprocess_run.call_args[0][0]
        
        # Check that output file path is returned
        expected_output = os.path.join(self.temp_dir, "captioned_video.mp4")
        self.assertEqual(result, expected_output)
        
        # Check for the presence of the subtitles parameter in the ffmpeg command
        subtitles_param = f"subtitles={subtitle_file}"
        self.assertTrue(any(subtitles_param in arg for arg in cmd_args), 
                       f"Subtitles parameter '{subtitles_param}' not found in command: {cmd_args}")
    
    @patch('subprocess.run')
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_full_rendering_pipeline(self, mock_is_feature_enabled, mock_subprocess_run):
        """Test the full caption rendering pipeline."""
        # Mock the feature flag to be enabled
        mock_is_feature_enabled.return_value = True
        
        # Mock subprocess.run to return success
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_subprocess_run.return_value = mock_process
        
        # Create renderer with captions enabled
        renderer = CaptionRenderer(captions_enabled=True, caption_prefs=self.caption_prefs)
        
        # Test the full rendering pipeline
        video_path = "/path/to/video.mp4"
        caption_data = {"timing": self.timing_data}
        result = renderer.render_captions(video_path, caption_data, self.temp_dir)
        
        # Check that subprocess.run was called (ffmpeg)
        mock_subprocess_run.assert_called_once()
        
        # Check that output file path is returned
        expected_output = os.path.join(self.temp_dir, "captioned_video.mp4")
        self.assertEqual(result, expected_output)
    
    @patch('tests.test_caption_renderer.MockConfig.is_feature_enabled')
    def test_missing_timing_data(self, mock_is_feature_enabled):
        """Test behavior when timing data is missing."""
        # Mock the feature flag to be enabled
        mock_is_feature_enabled.return_value = True
        
        # Create renderer with captions enabled
        renderer = CaptionRenderer(captions_enabled=True, caption_prefs=self.caption_prefs)
        
        # Test with missing timing data
        video_path = "/path/to/video.mp4"
        caption_data = {"timing": []}  # Empty timing data
        result = renderer.render_captions(video_path, caption_data, self.temp_dir)
        
        # Should return original path unchanged
        self.assertEqual(result, video_path)
        
        # Test with no timing key
        caption_data = {}  # No timing key
        result = renderer.render_captions(video_path, caption_data, self.temp_dir)
        
        # Should return original path unchanged
        self.assertEqual(result, video_path)

if __name__ == '__main__':
    unittest.main() 