#!/bin/bash
# Script to install NLTK resources on the backend server
echo "=== NLTK Resource Installation Script ==="
echo "This script connects to the backend server to install missing NLTK resources."
echo "1. Connecting to the backend server..."
echo "Once connected, run the following commands:"
echo "After installation, restart the service with: fly restart -a linkedin-content-backend"
fly ssh console -a linkedin-content-backend
