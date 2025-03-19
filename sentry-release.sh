#!/bin/bash
# Sentry Release Script
# Add these commands to your CI config when you deploy your application

# Install the cli
curl -sL https://sentry.io/get-cli/ | bash

# Setup configuration values
SENTRY_AUTH_TOKEN=<click-here-for-your-token>
SENTRY_ORG=pro-ai-assistant
SENTRY_PROJECT=python-flask
VERSION=`sentry-cli releases propose-version`

# Workflow to create releases
sentry-cli releases new "$VERSION"
sentry-cli releases set-commits "$VERSION" --auto
sentry-cli releases finalize "$VERSION"
