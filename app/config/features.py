"""
Feature flag configuration for the application.
This module provides feature flags that can be used to enable/disable features
in the application. Feature flags can be set via environment variables.
"""

import os
from typing import Dict, Any

# Feature flags with default values
FEATURE_FLAGS: Dict[str, Any] = {
    # Video caption rendering feature
    "ENABLE_CAPTIONS": os.environ.get("ENABLE_CAPTIONS", "true").lower() in ("true", "1", "yes"),
    
    # Debugging features
    "DEBUG_LOGGING": os.environ.get("DEBUG_LOGGING", "false").lower() in ("true", "1", "yes"),
    
    # Performance monitoring
    "PERFORMANCE_MONITORING": os.environ.get("PERFORMANCE_MONITORING", "false").lower() in ("true", "1", "yes"),
}

def is_feature_enabled(feature_name: str) -> bool:
    """
    Check if a feature is enabled.
    
    Args:
        feature_name: The name of the feature to check
        
    Returns:
        True if the feature is enabled, False otherwise
    """
    return FEATURE_FLAGS.get(feature_name, False)

def set_feature(feature_name: str, enabled: bool) -> None:
    """
    Set a feature flag to enabled or disabled.
    
    Args:
        feature_name: The name of the feature to set
        enabled: Whether the feature should be enabled
    """
    FEATURE_FLAGS[feature_name] = enabled 