# NLTK Resources: Requirements and Best Practices

## Overview

This document provides information about the NLTK (Natural Language Toolkit) resources required by the LinkedIn Content Generator backend service, with specific focus on preventing the `punkt_tab` resource error that has caused issues in production.

## Required NLTK Resources

The following NLTK resources **must** be available for the application to function correctly:

| Resource | Purpose | Status |
|----------|---------|--------|
| `punkt` | Text tokenization | Required |
| `punkt_tab` | Used by the punkt tokenizer internally | Required |
| `stopwords` | Filtering common words | Required |
| `wordnet` | Word relationships for enhanced analysis | Optional |

## Installation Methods

### 1. During Docker Build (Recommended)

In the Dockerfile, include explicit commands to download required NLTK resources:

```dockerfile
# Download required NLTK resources
RUN python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data')"
RUN python -c "import nltk; nltk.download('stopwords', download_dir='/usr/local/share/nltk_data')"
```

### 2. Installation Script

We've created a dedicated script `nltk_install.py` that should be run during deployment:

```python
import nltk

# Set a consistent download directory
nltk_data_dir = '/usr/local/share/nltk_data'

# Critical resources
nltk.download('punkt', download_dir=nltk_data_dir)
nltk.download('stopwords', download_dir=nltk_data_dir)

# Verify installation
try:
    nltk.data.find('tokenizers/punkt')
    print("✓ punkt installed successfully")
    
    # Explicitly check for punkt_tab
    nltk.data.find('tokenizers/punkt/punkt_tab')
    print("✓ punkt_tab available")
except LookupError as e:
    print(f"ERROR: {e}")
    print("! CRITICAL: Required NLTK resources are missing")
```

### 3. Runtime Download Fallback

The application includes automatic fallback to download missing resources at runtime:

```python
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading punkt resources")
    nltk.download('punkt')
```

**Note:** While runtime downloading works, it should be considered a fallback mechanism only. Always prefer pre-installing resources during deployment.

## Error Handling Strategy

The application implements a multi-layered approach to handle missing NLTK resources:

1. **Resource Detection**: On startup, check if all required resources exist
2. **Download Attempt**: Try to download missing resources
3. **Fallback Tokenizer**: Use RegexpTokenizer if punkt is unavailable
4. **Error Tracking**: Capture detailed information in Sentry
5. **Graceful Degradation**: Return usable results even with limited functionality

## Common Issues and Solutions

### Missing punkt_tab Error

**Error message**: `Resource punkt_tab not found.`

This occurs because the `punkt_tab` file is not a top-level resource but a file within the `punkt` resource. Sometimes downloading `punkt` doesn't properly install `punkt_tab`.

**Solutions**:

1. Explicitly check for `punkt_tab` after downloading `punkt`:
   ```python
   try:
       nltk.data.find('tokenizers/punkt/punkt_tab')
   except LookupError:
       # Try downloading punkt again to get punkt_tab
       nltk.download('punkt')
   ```

2. Use the fallback tokenizer implementation:
   ```python
   from nltk.tokenize import RegexpTokenizer
   fallback_tokenizer = RegexpTokenizer(r'\w+')
   tokens = fallback_tokenizer.tokenize(text)
   ```

### Deployment Best Practices

1. **Always Include NLTK Resources in Docker Image**
   - Include NLTK downloads in Dockerfile
   - Verify resources after download
   - Set a fixed download directory

2. **Add Health Check for NLTK Resources**
   - Create a dedicated health check endpoint for NLTK
   - Check for all required resources
   - Return detailed status information

3. **Monitor NLTK-Related Errors in Sentry**
   - Set up specific alerts for NLTK resource errors
   - Add custom tags to NLTK-related exceptions
   - Track occurrences of fallback mechanisms being used

## Adding New NLTK Resources

When adding a new NLTK resource dependency:

1. Add it to this documentation
2. Update the Dockerfile
3. Update the nltk_install.py script
4. Add appropriate fallback mechanisms
5. Update health checks to verify the new resource

## Troubleshooting

### Manually Verify NLTK Resources

Run this Python code to check for required resources:

```python
import nltk
nltk.data.path  # Check current search paths

# Test for required resources
resources = [
    'tokenizers/punkt',
    'tokenizers/punkt/punkt_tab',
    'corpora/stopwords'
]

for resource in resources:
    try:
        nltk.data.find(resource)
        print(f"✓ {resource} - OK")
    except LookupError:
        print(f"✗ {resource} - MISSING")
```

### Force Resource Download

Force download of a specific resource:

```bash
python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data', force=True)"
``` 