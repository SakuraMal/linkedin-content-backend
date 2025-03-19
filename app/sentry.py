import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_sentry():
    """Initialize Sentry with Flask integration"""
    # Get release from environment if available
    release = os.environ.get('SENTRY_RELEASE', None)
    
    sentry_sdk.init(
        dsn="https://6aff86cb9438a1ad675197e0eb14441a@o4509004253495296.ingest.de.sentry.io/4509004264374352",
        integrations=[FlaskIntegration()],
        # Add user data like request headers and IP addresses
        send_default_pii=True,
        # Set the environment
        environment=os.environ.get('ENVIRONMENT', 'production'),
        # Include release version if available
        release=release,
    )
    
    return True 