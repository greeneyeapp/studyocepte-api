# routes/caching.py - Router ile birlikte Redis Cache Implementation
from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Optional
import json
import hashlib
from datetime import timedelta
import redis
from loguru import logger
from core.config import settings
from core.dependencies import get_current_user
from core.models import UserData

# Router tanımı eklendi
router = APIRouter()

class CacheService:
    """Redis-based caching service."""
    
    def __init__(self):
        self.redis_client = None
        self.enabled = False
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection if available."""
        try:
            if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                self.enabled = True
                logger.info("Redis cache enabled")
            else:
                logger.info("Redis URL not configured, caching disabled")
        except Exception as e:
            logger.warning(f"Redis connection failed, caching disabled: {e}")
            self.enabled = False
    
    def _make_key(self, prefix: str, *args) -> str:
        """Generate cache key from prefix and arguments."""
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return f"studyo:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def get(self, prefix: str, *args) -> Optional[Any]:
        """Get value from cache."""
        if not self.enabled:
            return None
        
        try:
            key = self._make_key(prefix, *args)
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None
    
    async def set(self, prefix: str, value: Any, ttl_seconds: int = 3600, *args):
        """Set value in cache with TTL."""
        if not self.enabled:
            return
        
        try:
            key = self._make_key(prefix, *args)
            data = json.dumps(value, default=str)
            self.redis_client.setex(key, ttl_seconds, data)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
    
    async def delete(self, prefix: str, *args):
        """Delete value from cache."""
        if not self.enabled:
            return
        
        try:
            key = self._make_key(prefix, *args)
            self.redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
    
    async def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern."""
        if not self.enabled:
            return
        
        try:
            keys = self.redis_client.keys(f"studyo:*{pattern}*")
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache clear pattern failed: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            info = self.redis_client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_ratio": info.get("keyspace_hits", 0) / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0))
            }
        except Exception as e:
            logger.warning(f"Cache stats failed: {e}")
            return {"enabled": True, "error": str(e)}

# Global cache instance
cache = CacheService()

# Cache management endpoints
@router.get("/stats")
async def get_cache_stats(current_user: UserData = Depends(get_current_user)):
    """Get cache statistics - Admin only."""
    return cache.get_stats()

@router.delete("/clear")
async def clear_cache(
    pattern: Optional[str] = None,
    current_user: UserData = Depends(get_current_user)
):
    """Clear cache entries - Admin only."""
    if not cache.enabled:
        raise HTTPException(status_code=503, detail="Cache not available")
    
    try:
        if pattern:
            await cache.clear_pattern(pattern)
            return {"message": f"Cache cleared for pattern: {pattern}"}
        else:
            # Clear all app cache
            await cache.clear_pattern("")
            return {"message": "All cache cleared"}
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail="Cache clear failed")

@router.post("/warm-up")
async def warm_up_cache(current_user: UserData = Depends(get_current_user)):
    """Warm up cache with frequently accessed data."""
    if not cache.enabled:
        raise HTTPException(status_code=503, detail="Cache not available")
    
    try:
        # Cache backgrounds
        from routes.backgrounds import STATIC_BACKGROUNDS
        await cache.set("backgrounds", STATIC_BACKGROUNDS, ttl_seconds=3600)
        
        # Cache user products count
        user_id = current_user.uid
        await cache.set("user_product_count", 0, user_id, ttl_seconds=1800)
        
        return {
            "message": "Cache warmed up successfully",
            "cached_items": ["backgrounds", "user_product_count"]
        }
    except Exception as e:
        logger.error(f"Cache warm-up failed: {e}")
        raise HTTPException(status_code=500, detail="Cache warm-up failed")