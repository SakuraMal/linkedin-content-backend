# CORS Configuration Documentation
*Last updated: March 13, 2025, 15:24 UTC*

## Working Configuration

The following CORS configuration has been tested and confirmed working for both preflight requests and actual API calls:

```python
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

# CORS configuration
allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, 
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'OPTIONS'])
```

## Key Points

1. **Order of Operations**
   - CORS must be initialized BEFORE registering any blueprints
   - CORS must be initialized BEFORE defining any routes

2. **Environment Variables**
   - `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g., `http://localhost:3000,https://your-production-domain.com`)

3. **Required Headers**
   - `Content-Type`
   - `Authorization`

4. **Allowed Methods**
   - GET
   - POST
   - OPTIONS (for preflight requests)

## Testing CORS Configuration

You can test if CORS is working correctly using the following curl commands:

```bash
# Test preflight request (OPTIONS)
curl -X OPTIONS -i \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  https://your-api-domain.com/your-endpoint

# Test actual request (POST)
curl -X POST \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  https://your-api-domain.com/your-endpoint
```

## Expected Response Headers

A properly configured CORS response should include these headers:

```
access-control-allow-origin: http://localhost:3000
access-control-allow-headers: Content-Type, Authorization
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
vary: Origin
```

## Common Issues and Solutions

1. **Missing CORS Headers**
   - Ensure CORS is initialized before routes and blueprints
   - Check if any middleware is stripping headers
   - Verify environment variables are set correctly

2. **Preflight Failures**
   - Ensure OPTIONS method is allowed
   - Check that all required headers are in `allow_headers`
   - Verify origin is in allowed origins list

3. **Production Issues**
   - Double-check `CORS_ORIGINS` environment variable in production
   - Ensure all necessary domains are included in allowed origins
   - Verify that load balancers/proxies are not stripping CORS headers

## Implementation Notes

1. The configuration uses `supports_credentials=True` to allow authenticated requests
2. Origins are configured via environment variables for flexibility across environments
3. The `vary: Origin` header is automatically added to help with caching

## Testing Endpoint

A test endpoint is available at `/api/test/test-cors` to verify CORS functionality:

```python
@test_bp.route('/test-cors', methods=['POST', 'OPTIONS'])
@cross_origin()
def test_cors():
    return jsonify({
        "status": "success",
        "message": "CORS test successful",
        "data": {
            "received": True,
            "cors_enabled": True
        }
    }), 200
``` 