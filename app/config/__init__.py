"""
Configuration module for the application.
"""

from .features import is_feature_enabled, set_feature, FEATURE_FLAGS

__all__ = ['is_feature_enabled', 'set_feature', 'FEATURE_FLAGS'] 