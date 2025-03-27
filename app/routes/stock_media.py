import logging
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from ..services.storage.image_storage import image_storage_service
from ..services.auth import require_auth

logger = logging.getLogger(__name__)

# Create stock media blueprint
stock_media_bp = Blueprint('stock_media', __name__, url_prefix='/api/stock-media')

@stock_media_bp.route('/register', methods=['POST'])
@cross_origin()
@require_auth
def register_stock_media():
    """
    Register original URLs for stock media items.
    This allows the backend to serve the original URLs when it can't find the stock media files in storage.
    """
    try:
        logger.info("Received request to register stock media URLs")
        
        # Get request data
        data = request.json
        if not data or not isinstance(data, dict) or 'items' not in data:
            logger.error("Invalid request data: missing items")
            return jsonify({
                'success': False,
                'error': 'Invalid request data: missing items'
            }), 400
            
        items = data['items']
        if not isinstance(items, list) or len(items) == 0:
            logger.error("Invalid items: must be a non-empty list")
            return jsonify({
                'success': False,
                'error': 'Invalid items: must be a non-empty list'
            }), 400
            
        # Process each item
        success_count = 0
        failed_items = []
        
        for item in items:
            try:
                # Validate item
                if not isinstance(item, dict) or 'id' not in item or 'url' not in item:
                    logger.error(f"Invalid item format: {item}")
                    failed_items.append({
                        'id': item.get('id', 'unknown'),
                        'error': 'Missing required fields (id, url)'
                    })
                    continue
                    
                stock_id = item['id']
                url = item['url']
                media_type = item.get('type', 'image')
                
                if not stock_id.startswith('stock_'):
                    logger.error(f"Invalid stock ID format: {stock_id}")
                    failed_items.append({
                        'id': stock_id,
                        'error': 'ID must start with stock_'
                    })
                    continue
                    
                # Store the URL
                result = image_storage_service.store_stock_media_url(stock_id, url, media_type)
                
                if result:
                    success_count += 1
                    logger.info(f"Successfully registered stock media URL for {stock_id}")
                else:
                    failed_items.append({
                        'id': stock_id,
                        'error': 'Failed to store URL'
                    })
                    
            except Exception as e:
                logger.error(f"Error processing item {item.get('id', 'unknown')}: {str(e)}")
                failed_items.append({
                    'id': item.get('id', 'unknown'),
                    'error': str(e)
                })
                
        # Return result
        return jsonify({
            'success': True,
            'registered': success_count,
            'failed': len(failed_items),
            'failedItems': failed_items
        })
        
    except Exception as e:
        logger.error(f"Error in stock media registration: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_media_bp.route('/lookup/<stock_id>', methods=['GET'])
@cross_origin()
def lookup_stock_media(stock_id):
    """
    Look up the original URL for a stock media item
    """
    try:
        logger.info(f"Looking up stock media URL for {stock_id}")
        
        if not stock_id.startswith('stock_'):
            logger.error(f"Invalid stock ID format: {stock_id}")
            return jsonify({
                'success': False,
                'error': 'ID must start with stock_'
            }), 400
            
        # Get the URL
        url = image_storage_service.get_stock_media_url(stock_id)
        
        if url:
            return jsonify({
                'success': True,
                'id': stock_id,
                'url': url
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Stock media not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error looking up stock media URL: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 