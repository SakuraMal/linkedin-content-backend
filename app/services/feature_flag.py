from typing import Dict

# Define feature flags
FEATURE_FLAGS: Dict[str, bool] = {
    "ENABLE_CAPTIONS": True,
    # Add more feature flags as needed
}

def is_feature_enabled(flag_name: str) -> bool:
    """
    Check if a feature flag is enabled.
    
    Args:
        flag_name: The name of the feature flag to check
        
    Returns:
        bool: True if the feature is enabled, False otherwise
    """
    # For now, always return True for ENABLE_CAPTIONS
    if flag_name == "ENABLE_CAPTIONS":
        return True
    return False 