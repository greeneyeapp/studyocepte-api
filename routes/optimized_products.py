from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache
from loguru import logger

from core.firebase_config import db
from core.storage_config import storage_client
from core.models import UserData, ProductListResponse, ProductPhotoBase
from core.dependencies import get_current_user
from core.config import settings

router = APIRouter()

# Cache for signed URLs (15 minutes TTL)
url_cache = TTLCache(maxsize=1000, ttl=900)  # 15 minutes
metadata_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour

class OptimizedImageService:
    """Optimize image loading and URL generation."""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def get_signed_url_cached(self, gcs_path: str) -> str:
        """Get signed URL with caching."""
        if not gcs_path or not gcs_path.startswith(f"gs://{settings.STORAGE_BUCKET_NAME}/"):
            return ""
        
        # Check cache first
        if gcs_path in url_cache:
            return url_cache[gcs_path]
        
        try:
            blob_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
            bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
            blob = bucket.blob(blob_path)
            
            # Generate signed URL
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=30),  # Longer expiration
                method="GET"
            )
            
            # Cache the result
            url_cache[gcs_path] = signed_url
            return signed_url
            
        except Exception as e:
            logger.warning(f"Signed URL generation failed for {gcs_path}: {e}")
            return ""
    
    async def get_image_metadata(self, gcs_path: str) -> dict:
        """Get image metadata with caching."""
        if gcs_path in metadata_cache:
            return metadata_cache[gcs_path]
        
        try:
            blob_path = gcs_path.replace(f"gs://{settings.STORAGE_BUCKET_NAME}/", "")
            bucket = storage_client.bucket(settings.STORAGE_BUCKET_NAME)
            blob = bucket.blob(blob_path)
            
            # Get blob metadata
            blob.reload()
            metadata = {
                'size': blob.size,
                'contentType': blob.content_type,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'updated': blob.updated.isoformat() if blob.updated else None,
            }
            
            metadata_cache[gcs_path] = metadata
            return metadata
            
        except Exception as e:
            logger.warning(f"Metadata retrieval failed for {gcs_path}: {e}")
            return {}
    
    async def generate_multiple_signed_urls(self, gcs_paths: List[str]) -> List[str]:
        """Generate multiple signed URLs concurrently."""
        if not gcs_paths:
            return []
        
        # Use asyncio to run concurrent tasks
        tasks = [self.get_signed_url_cached(path) for path in gcs_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)

# Global service instance
image_service = OptimizedImageService()

@router.get("/", response_model=List[ProductListResponse])
async def get_user_products_optimized(
    current_user: UserData = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100, description="Number of products to return"),
    offset: int = Query(0, ge=0, description="Number of products to skip"),
    include_photos: bool = Query(False, description="Include photo count and cover image"),
    sort_by: str = Query("createdAt", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)")
):
    """Get user products with pagination and optimization."""
    try:
        # Build query
        products_query = db.collection('products').where('userId', '==', current_user.uid)
        
        # Apply sorting
        direction = firestore.Query.DESCENDING if sort_order == "desc" else firestore.Query.ASCENDING
        products_query = products_query.order_by(sort_by, direction=direction)
        
        # Apply pagination
        products_query = products_query.offset(offset).limit(limit)
        
        # Execute query
        products_docs = list(products_query.stream())
        
        if not include_photos:
            # Fast path - no photo data needed
            products_list = []
            for doc in products_docs:
                product_data = doc.to_dict()
                product_data['id'] = doc.id
                product_data['photoCount'] = 0
                product_data['coverThumbnailUrl'] = ""
                products_list.append(ProductListResponse.model_validate(product_data))
            
            logger.info(f"Fast product list returned for user {current_user.uid}: {len(products_list)} items")
            return products_list
        
        # Slow path - include photo data
        products_list = []
        cover_image_paths = []
        
        # First pass: collect product data and cover image paths
        for doc in products_docs:
            product_data = doc.to_dict()
            product_data['id'] = doc.id
            
            # Get first completed photo for cover
            cover_photo_query = doc.reference.collection('photos').where(
                'status', '==', 'completed'
            ).order_by('createdAt', direction=firestore.Query.DESCENDING).limit(1)
            
            cover_photos = list(cover_photo_query.stream())
            
            # Count total photos efficiently
            photo_count = len(list(doc.reference.collection('photos').stream()))
            product_data['photoCount'] = photo_count
            
            if cover_photos:
                cover_thumbnail_path = cover_photos[0].to_dict().get('thumbnailUrl', '')
                cover_image_paths.append(cover_thumbnail_path)
                product_data['_cover_index'] = len(cover_image_paths) - 1
            else:
                product_data['_cover_index'] = -1
                cover_image_paths.append('')
            
            products_list.append(product_data)
        
        # Second pass: generate all signed URLs concurrently
        signed_urls = await image_service.generate_multiple_signed_urls(cover_image_paths)
        
        # Third pass: assign signed URLs to products
        final_products = []
        for product_data in products_list:
            cover_index = product_data.pop('_cover_index', -1)
            if cover_index >= 0 and cover_index < len(signed_urls):
                product_data['coverThumbnailUrl'] = signed_urls[cover_index] if not isinstance(signed_urls[cover_index], Exception) else ""
            else:
                product_data['coverThumbnailUrl'] = ""
            
            final_products.append(ProductListResponse.model_validate(product_data))
        
        logger.info(f"Optimized product list returned for user {current_user.uid}: {len(final_products)} items")
        return final_products
        
    except Exception as e:
        logger.error(f"Error fetching optimized products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Products could not be loaded.")

@router.get("/{product_id}/photos/summary")
async def get_product_photos_summary(
    product_id: str,
    current_user: UserData = Depends(get_current_user),
    include_thumbnails: bool = Query(True, description="Include thumbnail URLs"),
    quality: str = Query("medium", description="Thumbnail quality (low/medium/high)")
):
    """Get optimized photo summary for a product."""
    try:
        # Verify product ownership
        product_ref = db.collection('products').document(product_id)
        product_doc = product_ref.get()
        
        if not product_doc.exists or product_doc.to_dict().get('userId') != current_user.uid:
            raise HTTPException(status_code=404, detail="Product not found.")
        
        # Get photos with minimal data
        photos_query = product_ref.collection('photos').select(['id', 'status', 'createdAt', 'thumbnailUrl'])
        photos_docs = list(photos_query.stream())
        
        photos_summary = []
        thumbnail_paths = []
        
        for photo_doc in photos_docs:
            photo_data = photo_doc.to_dict()
            photo_data['id'] = photo_doc.id
            
            if include_thumbnails and photo_data.get('thumbnailUrl'):
                thumbnail_paths.append(photo_data['thumbnailUrl'])
                photo_data['_thumbnail_index'] = len(thumbnail_paths) - 1
            else:
                photo_data['_thumbnail_index'] = -1
            
            photos_summary.append(photo_data)
        
        # Generate signed URLs concurrently if needed
        if include_thumbnails and thumbnail_paths:
            signed_urls = await image_service.generate_multiple_signed_urls(thumbnail_paths)
            
            for photo_data in photos_summary:
                thumbnail_index = photo_data.pop('_thumbnail_index', -1)
                if thumbnail_index >= 0 and thumbnail_index < len(signed_urls):
                    photo_data['thumbnailUrl'] = signed_urls[thumbnail_index] if not isinstance(signed_urls[thumbnail_index], Exception) else ""
                else:
                    photo_data['thumbnailUrl'] = ""
        
        return {
            'productId': product_id,
            'totalCount': len(photos_summary),
            'completedCount': len([p for p in photos_summary if p.get('status') == 'completed']),
            'processingCount': len([p for p in photos_summary if p.get('status') == 'processing']),
            'failedCount': len([p for p in photos_summary if p.get('status') == 'failed']),
            'photos': photos_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching photo summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Photo summary could not be loaded.")
