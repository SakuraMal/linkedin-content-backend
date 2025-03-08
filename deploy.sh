#!/bin/bash

# Export environment variables
export FIREBASE_CREDENTIALS_B64=$(echo -n '{"type":"service_account","project_id":"your-project-id"}' | base64)

export LINKEDIN_API_KEY="your_linkedin_api_key"
export LINKEDIN_API_SECRET="your_linkedin_api_secret"
export LINKEDIN_ACCESS_TOKEN="your_linkedin_access_token"
export LINKEDIN_RETURN_URL="https://video-service-95562619871.europe-north1.run.app/linkedin/callback"

# Deploy to Cloud Run
gcloud run deploy video-service \
  --source . \
  --region europe-north1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_CREDENTIALS_B64=$FIREBASE_CREDENTIALS_B64 \
  --set-env-vars LINKEDIN_API_KEY=$LINKEDIN_API_KEY \
  --set-env-vars LINKEDIN_API_SECRET=$LINKEDIN_API_SECRET \
  --set-env-vars LINKEDIN_ACCESS_TOKEN=$LINKEDIN_ACCESS_TOKEN \
  --set-env-vars LINKEDIN_RETURN_URL=$LINKEDIN_RETURN_URL 