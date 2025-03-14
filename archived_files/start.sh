#!/bin/bash
set -e

# Clear any existing NODE related environment variables
unset NODE_ENV
unset NODE_PATH
unset NODE_VERSION

# Ensure Python is in the PATH
export PATH="/opt/render/project/python/bin:$PATH"

# Print diagnostic information
echo "Current PATH: $PATH"
echo "Python version: $(python3 -V)"
echo "Python location: $(which python3)"
echo "Working directory: $(pwd)"
echo "Directory contents: $(ls -la)"

# Start the application using gunicorn
exec gunicorn --bind 0.0.0.0:$PORT wsgi:app --log-level debug --timeout 120 --workers 2 --threads 2 