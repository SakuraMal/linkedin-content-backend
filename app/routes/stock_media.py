import logging
from flask import Blueprint, request, jsonify
from ..services.storage.image_storage import image_storage_service

# Create a blueprint for stock media endpoints
stock_media_bp = Blueprint('stock_media', __name__, url_prefix='/api/stock-media')
logger = logging.getLogger(__name__)

@stock_media_bp.route('/register', methods=['POST'])
def register_stock_media():
    """
    Register stock media URLs for later use in video generation.
    
    Request body:
    {
        "items": [
            {
                "id": "stock_123abc",
                "url": "https://example.com/image.jpg",
                "type": "image"
            }
        ]
    }
    
    Returns:
        JSON response with registration status
    """
    try:
        data = request.json
        
        if not data or 'items' not in data or not isinstance(data['items'], list):
            return jsonify({
                'success': False,
                'error': 'Invalid request format. Expected "items" array.'
            }), 400
            
        items = data['items']
        results = []
        
        for item in items:
            if 'id' not in item or 'url' not in item:
                results.append({
                    'id': item.get('id', 'unknown'),
                    'success': False,
                    'error': 'Missing required fields (id, url)'
                })
                continue
                
            media_type = item.get('type', 'image')
            success = image_storage_service.store_stock_media_url(
                item['id'],
                item['url'],
                media_type
            )
            
            results.append({
                'id': item['id'],
                'success': success,
                'error': None if success else 'Failed to store URL'
            })
            
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error registering stock media: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stock_media_bp.route('/lookup/<stock_id>', methods=['GET'])
def lookup_stock_media(stock_id):
    """
    Look up the original URL for a stock media item.
    
    Args:
        stock_id: The ID of the stock media item
        
    Returns:
        JSON response with the original URL
    """
    try:
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
                'error': 'Stock media URL not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error looking up stock media: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 