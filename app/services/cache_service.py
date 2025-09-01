"""Redis caching service with fallback support and intelligent cache management"""

import json
import pickle
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from ..config import settings


class CacheService:
    """
    Redis-based caching service with fallback to in-memory cache when Redis is unavailable.
    Provides intelligent caching with TTL, versioning, and cache invalidation strategies.
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.redis_available = False
        self.fallback_cache: Dict[str, Dict[str, Any]] = {}  # In-memory fallback cache
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        
    async def initialize(self) -> bool:
        """
        Initialize Redis connection
        
        Returns:
            True if Redis is available, False if using fallback
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory fallback cache")
            return False
        
        if not settings.redis_enabled:
            logger.info("Redis disabled in settings, using in-memory fallback cache")
            return False
        
        try:
            redis_url = settings.redis_connection_string
            if not redis_url:
                logger.warning("No Redis connection string configured, using fallback cache")
                return False
            
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.redis_available = True
            
            logger.info(f"Redis cache initialized successfully: {settings.redis_host}:{settings.redis_port}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, using fallback cache")
            self.redis_client = None
            self.redis_available = False
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            self.redis_available = False
    
    def _get_cache_key(self, namespace: str, key: str, version: Optional[str] = None) -> str:
        """Generate cache key with namespace and optional versioning"""
        cache_key = f"{settings.app_name}:{namespace}:{key}"
        if version:
            cache_key += f":v{version}"
        return cache_key
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for caching (JSON with pickle fallback)"""
        try:
            # Try JSON first for simple types
            return json.dumps(value)
        except (TypeError, ValueError):
            # Fall back to pickle for complex objects
            return pickle.dumps(value).hex()
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize cached value"""
        try:
            # Try JSON first
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            try:
                # Try pickle
                return pickle.loads(bytes.fromhex(value))
            except:
                # Return as string if all else fails
                return value
    
    async def get(self, namespace: str, key: str, version: Optional[str] = None) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            version: Optional version for cache versioning
            
        Returns:
            Cached value or None if not found
        """
        cache_key = self._get_cache_key(namespace, key, version)
        
        try:
            if self.redis_available and self.redis_client:
                # Try Redis first
                value = await self.redis_client.get(cache_key)
                if value is not None:
                    self.cache_stats["hits"] += 1
                    return self._deserialize_value(value)
            
            # Fall back to in-memory cache
            if cache_key in self.fallback_cache:
                entry = self.fallback_cache[cache_key]
                # Check if expired
                if datetime.now() < entry["expires_at"]:
                    self.cache_stats["hits"] += 1
                    return entry["value"]
                else:
                    # Remove expired entry
                    del self.fallback_cache[cache_key]
            
            self.cache_stats["misses"] += 1
            return None
            
        except Exception as e:
            logger.warning(f"Cache get error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return None
    
    async def set(
        self, 
        namespace: str, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        version: Optional[str] = None
    ) -> bool:
        """
        Set value in cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default from settings)
            version: Optional version for cache versioning
            
        Returns:
            True if successfully cached
        """
        cache_key = self._get_cache_key(namespace, key, version)
        
        # Determine TTL based on namespace if not provided
        if ttl is None:
            if namespace == "models":
                ttl = settings.cache_ttl_models
            elif namespace == "user_profiles":
                ttl = settings.cache_ttl_user_profile
            elif namespace == "conversations":
                ttl = settings.cache_ttl_conversations
            else:
                ttl = 3600  # Default 1 hour
        
        try:
            serialized_value = self._serialize_value(value)
            
            if self.redis_available and self.redis_client:
                # Set in Redis with TTL
                await self.redis_client.setex(cache_key, ttl, serialized_value)
            else:
                # Set in fallback cache with expiration
                self.fallback_cache[cache_key] = {
                    "value": value,
                    "expires_at": datetime.now() + timedelta(seconds=ttl)
                }
                
                # Clean up expired entries periodically
                await self._cleanup_fallback_cache()
            
            self.cache_stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return False
    
    async def delete(self, namespace: str, key: str, version: Optional[str] = None) -> bool:
        """
        Delete value from cache
        
        Args:
            namespace: Cache namespace
            key: Cache key  
            version: Optional version for cache versioning
            
        Returns:
            True if deleted
        """
        cache_key = self._get_cache_key(namespace, key, version)
        
        try:
            deleted = False
            
            if self.redis_available and self.redis_client:
                result = await self.redis_client.delete(cache_key)
                deleted = result > 0
            
            # Also remove from fallback cache
            if cache_key in self.fallback_cache:
                del self.fallback_cache[cache_key]
                deleted = True
            
            if deleted:
                self.cache_stats["deletes"] += 1
                
            return deleted
            
        except Exception as e:
            logger.warning(f"Cache delete error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return False
    
    async def delete_pattern(self, namespace: str, pattern: str) -> int:
        """
        Delete keys matching a pattern
        
        Args:
            namespace: Cache namespace
            pattern: Key pattern (supports * wildcards)
            
        Returns:
            Number of keys deleted
        """
        search_pattern = self._get_cache_key(namespace, pattern)
        deleted_count = 0
        
        try:
            if self.redis_available and self.redis_client:
                # Get matching keys
                keys = await self.redis_client.keys(search_pattern)
                if keys:
                    deleted_count = await self.redis_client.delete(*keys)
            
            # Also clean up fallback cache
            keys_to_delete = []
            for cache_key in self.fallback_cache.keys():
                if cache_key.startswith(f"{settings.app_name}:{namespace}:"):
                    # Simple wildcard matching
                    key_part = cache_key.split(":", 2)[2]
                    if self._matches_pattern(key_part, pattern):
                        keys_to_delete.append(cache_key)
            
            for key in keys_to_delete:
                del self.fallback_cache[key]
                deleted_count += 1
            
            self.cache_stats["deletes"] += deleted_count
            return deleted_count
            
        except Exception as e:
            logger.warning(f"Cache delete pattern error for {search_pattern}: {e}")
            self.cache_stats["errors"] += 1
            return 0
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Simple wildcard pattern matching"""
        import re
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        return re.match(f"^{regex_pattern}$", text) is not None
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """
        Invalidate entire namespace
        
        Args:
            namespace: Namespace to invalidate
            
        Returns:
            Number of keys deleted
        """
        return await self.delete_pattern(namespace, "*")
    
    async def exists(self, namespace: str, key: str, version: Optional[str] = None) -> bool:
        """
        Check if key exists in cache
        
        Args:
            namespace: Cache namespace
            key: Cache key
            version: Optional version for cache versioning
            
        Returns:
            True if key exists
        """
        cache_key = self._get_cache_key(namespace, key, version)
        
        try:
            if self.redis_available and self.redis_client:
                return await self.redis_client.exists(cache_key) > 0
            
            # Check fallback cache
            if cache_key in self.fallback_cache:
                entry = self.fallback_cache[cache_key]
                # Check if expired
                if datetime.now() < entry["expires_at"]:
                    return True
                else:
                    # Remove expired entry
                    del self.fallback_cache[cache_key]
                    return False
            
            return False
            
        except Exception as e:
            logger.warning(f"Cache exists check error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return False
    
    async def get_ttl(self, namespace: str, key: str, version: Optional[str] = None) -> Optional[int]:
        """
        Get remaining TTL for a key
        
        Args:
            namespace: Cache namespace
            key: Cache key
            version: Optional version
            
        Returns:
            Remaining TTL in seconds, None if key doesn't exist, -1 if no expiration
        """
        cache_key = self._get_cache_key(namespace, key, version)
        
        try:
            if self.redis_available and self.redis_client:
                ttl = await self.redis_client.ttl(cache_key)
                return ttl if ttl >= 0 else None
            
            # Check fallback cache
            if cache_key in self.fallback_cache:
                entry = self.fallback_cache[cache_key]
                remaining = entry["expires_at"] - datetime.now()
                return max(0, int(remaining.total_seconds()))
            
            return None
            
        except Exception as e:
            logger.warning(f"Cache TTL check error for {cache_key}: {e}")
            return None
    
    async def _cleanup_fallback_cache(self):
        """Clean up expired entries from fallback cache"""
        try:
            now = datetime.now()
            expired_keys = []
            
            for cache_key, entry in self.fallback_cache.items():
                if now >= entry["expires_at"]:
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self.fallback_cache[key]
                
            # Limit fallback cache size to prevent memory issues
            if len(self.fallback_cache) > 1000:
                # Remove oldest entries
                sorted_entries = sorted(
                    self.fallback_cache.items(),
                    key=lambda x: x[1]["expires_at"]
                )
                entries_to_remove = len(self.fallback_cache) - 800
                for i in range(entries_to_remove):
                    key = sorted_entries[i][0]
                    del self.fallback_cache[key]
                    
        except Exception as e:
            logger.warning(f"Fallback cache cleanup error: {e}")
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache service information and statistics"""
        info = {
            "redis_available": self.redis_available,
            "redis_enabled": settings.redis_enabled,
            "fallback_cache_size": len(self.fallback_cache),
            "stats": self.cache_stats.copy()
        }
        
        if self.redis_available and self.redis_client:
            try:
                redis_info = await self.redis_client.info()
                info["redis_info"] = {
                    "version": redis_info.get("redis_version"),
                    "used_memory": redis_info.get("used_memory_human"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "total_connections_received": redis_info.get("total_connections_received"),
                    "total_commands_processed": redis_info.get("total_commands_processed")
                }
            except:
                pass
        
        return info
    
    async def health_check(self) -> bool:
        """Check cache service health"""
        try:
            if self.redis_available and self.redis_client:
                await self.redis_client.ping()
                return True
            # Fallback cache is always "healthy"
            return True
        except Exception as e:
            logger.warning(f"Cache health check failed: {e}")
            return False


# Global cache service instance
cache_service = CacheService()