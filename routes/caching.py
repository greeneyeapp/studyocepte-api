# routes/caching.py - Redis Cache Implementation
from fastapi import APIRouter
from typing import Any, Optional
import json
import hashlib
from datetime import timedelta
import redis
from loguru import logger
from core.config import settings

router = APIRouter()  # Bu satır eksikti

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
            }
        except Exception as e:
            logger.warning(f"Cache stats failed: {e}")
            return {"enabled": True, "error": str(e)}

# Global cache instance
cache = CacheService()