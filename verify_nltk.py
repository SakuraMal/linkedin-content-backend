#!/usr/bin/env python3
"""
NLTK Resource Verification Script

This script checks for the presence of required NLTK resources and reports their status.
It returns a non-zero exit code if any required resources are missing.

Usage:
  python verify_nltk.py          # Check all resources
  python verify_nltk.py --fix    # Check and attempt to download missing resources
"""

import sys
import argparse
import nltk
import os
from typing import Dict, List, Tuple

# Define resources and their criticality
REQUIRED_RESOURCES = [
    ('tokenizers/punkt', True),           # (resource_path, is_critical)
    ('tokenizers/punkt/punkt_tab', True), # Critical - needed for tokenization
    ('corpora/stopwords', True),          # Critical - needed for keyword extraction
]

OPTIONAL_RESOURCES = [
    ('corpora/wordnet', False),           # Optional - enhances analysis
]

ALL_RESOURCES = REQUIRED_RESOURCES + OPTIONAL_RESOURCES


def check_resource(resource_path: str) -> bool:
    """Check if an NLTK resource exists."""
    try:
        nltk.data.find(resource_path)
        return True
    except LookupError:
        return False


def download_resource(resource_path: str) -> bool:
    """Attempt to download an NLTK resource."""
    # Extract the resource name from the path
    resource_name = resource_path.split('/')[-1]
    
    # Special case for punkt_tab which is part of punkt
    if resource_path == 'tokenizers/punkt/punkt_tab':
        resource_name = 'punkt'
        
    try:
        print(f"Attempting to download {resource_name}...")
        nltk.download(resource_name)
        return check_resource(resource_path)
    except Exception as e:
        print(f"Error downloading {resource_name}: {e}")
        return False


def verify_resources(fix_missing: bool = False) -> Tuple[bool, Dict[str, bool]]:
    """
    Verify all NLTK resources and optionally fix missing ones.
    
    Args:
        fix_missing: If True, attempt to download missing resources
        
    Returns:
        Tuple of (all_critical_resources_available, status_dict)
    """
    status = {}
    all_critical_available = True
    
    print(f"\nChecking NLTK resources...")
    print(f"NLTK data path: {nltk.data.path}\n")
    
    for resource_path, is_critical in ALL_RESOURCES:
        resource_available = check_resource(resource_path)
        status[resource_path] = resource_available
        
        status_text = "✓ OK" if resource_available else "✗ MISSING"
        critical_text = "(CRITICAL)" if is_critical else "(Optional)"
        
        print(f"{status_text} {resource_path} {critical_text}")
        
        if not resource_available:
            if is_critical:
                all_critical_available = False
            
            if fix_missing:
                fixed = download_resource(resource_path)
                status[resource_path] = fixed
                
                if fixed:
                    print(f"  ✓ Fixed: {resource_path} successfully downloaded")
                    if is_critical:
                        all_critical_available = True
                else:
                    print(f"  ✗ Failed to download: {resource_path}")
    
    return all_critical_available, status


def main():
    parser = argparse.ArgumentParser(description='Verify NLTK resources')
    parser.add_argument('--fix', action='store_true', 
                        help='Attempt to download missing resources')
    args = parser.parse_args()
    
    all_critical_available, status = verify_resources(fix_missing=args.fix)
    
    print("\nSummary:")
    if all_critical_available:
        print("✓ All critical NLTK resources are available")
        exit_code = 0
    else:
        print("✗ Some critical NLTK resources are missing!")
        print("  See NLTK_REQUIREMENTS.md for more information")
        exit_code = 1
    
    # Count missing resources
    missing_count = sum(1 for val in status.values() if not val)
    total_count = len(status)
    
    print(f"Resources available: {total_count - missing_count}/{total_count}")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 