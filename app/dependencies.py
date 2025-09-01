"""Enhanced FastAPI dependencies for dependency injection with new services"""

from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, Request
from cachetools import TTLCache
from loguru import logger

from .config import settings
from .services.supabase_client import SupabaseClient
from .services.litellm_client import LiteLLMService
from .services.auth_service import AuthService
from .services.edge_proxy import EdgeFunctionProxy
from .services.cache_service import CacheService, cache_service
from .models.user import UserProfile
from .utils.errors import (
    AuthenticationError,
    InsufficientBalanceError,
    EdgeFunctionError
)


# Global instances
_supabase_client: Optional[SupabaseClient] = None
_litellm_service: Optional[LiteLLMService] = None
_auth_service: Optional[AuthService] = None
_edge_proxy: Optional[EdgeFunctionProxy] = None

# User profile cache (fallback when Redis is not available)
user_profile_cache = TTLCache(maxsize=500, ttl=600)  # 10 minutes TTL


async def get_supabase_client() -> SupabaseClient:
    """Get Supabase client instance"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient(settings)
    return _supabase_client


async def get_litellm_service() -> LiteLLMService:
    """Get LiteLLM service instance"""
    global _litellm_service
    if _litellm_service is None:
        _litellm_service = LiteLLMService()
    return _litellm_service


# Legacy alias for backward compatibility
async def get_litellm_client() -> LiteLLMService:
    """Get LiteLLM client instance (legacy alias)"""
    return await get_litellm_service()


async def get_auth_service() -> AuthService:
    """Get authentication service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(settings)
    return _auth_service


async def get_edge_proxy() -> EdgeFunctionProxy:
    """Get Edge Function proxy service instance"""
    global _edge_proxy
    if _edge_proxy is None:
        _edge_proxy = EdgeFunctionProxy()
    return _edge_proxy


async def get_cache_service() -> CacheService:
    """Get cache service instance"""
    return cache_service


async def verify_token(
    authorization: Annotated[str, Header()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> dict:
    """
    Verify JWT token and return user info
    
    Args:
        authorization: Authorization header with Bearer token
        auth_service: Authentication service
        
    Returns:
        Token payload with user info
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    try:
        return auth_service.validate_token_and_get_user(authorization)
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {e.message}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": e.message,
                "code": e.code
            }
        )


async def get_current_user_id(
    token_payload: Annotated[dict, Depends(verify_token)]
) -> str:
    """
    Extract user ID from verified token
    
    Args:
        token_payload: Verified JWT token payload
        
    Returns:
        User ID string
    """
    return token_payload["sub"]


async def get_user_profile(
    user_id: Annotated[str, Depends(get_current_user_id)],
    authorization: Annotated[str, Header()],
    supabase_client: Annotated[SupabaseClient, Depends(get_supabase_client)]
) -> UserProfile:
    """
    Get user profile with caching
    
    Args:
        user_id: User ID from token
        authorization: Authorization header
        supabase_client: Supabase client
        
    Returns:
        User profile data
        
    Raises:
        HTTPException: If user profile cannot be retrieved
    """
    # Check cache first
    cache_key = f"user_profile_{user_id}"
    if cache_key in user_profile_cache:
        logger.debug(f"User profile cache hit for user {user_id}")
        return user_profile_cache[cache_key]
    
    try:
        profile = await supabase_client.get_user_profile(user_id, authorization.split("Bearer ")[1])
        
        # Cache the profile
        user_profile_cache[cache_key] = profile
        logger.debug(f"User profile cached for user {user_id}")
        
        return profile
        
    except EdgeFunctionError as e:
        logger.error(f"Failed to get user profile for {user_id}: {e.message}")
        raise HTTPException(
            status_code=403 if "not found" in e.message.lower() else 500,
            detail={
                "error": e.message,
                "code": e.code
            }
        )


async def verify_user_balance(
    user_profile: Annotated[UserProfile, Depends(get_user_profile)]
) -> UserProfile:
    """
    Verify user has sufficient balance
    
    Args:
        user_profile: User profile data
        
    Returns:
        User profile if balance is sufficient
        
    Raises:
        HTTPException: If balance is insufficient
    """
    if user_profile.available_balance is not None and user_profile.available_balance <= 0:
        logger.warning(f"Insufficient balance for user {user_profile.id}")
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "Insufficient balance",
                "code": "INSUFFICIENT_BALANCE",
                "details": {
                    "available_balance": user_profile.available_balance,
                    "max_budget": user_profile.max_budget
                }
            }
        )
    
    return user_profile


async def get_user_with_balance(
    user_profile: Annotated[UserProfile, Depends(verify_user_balance)]
) -> UserProfile:
    """
    Get user profile with verified balance
    
    Args:
        user_profile: User profile with verified balance
        
    Returns:
        User profile
    """
    return user_profile


async def get_current_user(
    authorization: Annotated[str, Header()],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> UserProfile:
    """
    Get current user profile from JWT token with intelligent caching
    
    Args:
        authorization: Authorization header with Bearer token
        cache_service: Cache service for user profile caching
        auth_service: Authentication service
        
    Returns:
        Current user profile
        
    Raises:
        HTTPException: If authentication fails or user not found
    """
    try:
        # Extract and validate token
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        token = authorization.split("Bearer ")[1]
        token_payload = auth_service.validate_token_and_get_user(authorization)
        user_id = token_payload["sub"]
        
        # Try cache first
        cache_key = f"user_profile:{user_id}"
        cached_profile = await cache_service.get("user_profiles", cache_key)
        if cached_profile:
            logger.debug(f"User profile cache hit for user {user_id}")
            # Reconstruct UserProfile from cached data
            return UserProfile(**cached_profile["data"]) if "data" in cached_profile else UserProfile(**cached_profile)
        
        # Fallback to in-memory cache
        fallback_key = f"user_profile_{user_id}"
        if fallback_key in user_profile_cache:
            logger.debug(f"User profile fallback cache hit for user {user_id}")
            return user_profile_cache[fallback_key]
        
        # Get fresh profile from Supabase
        supabase_client = await get_supabase_client()
        profile = await supabase_client.get_user_profile(user_id, token)
        
        # Cache the profile in both systems
        if settings.redis_enabled:
            await cache_service.set("user_profiles", cache_key, profile.model_dump())
        
        # Also cache in fallback
        user_profile_cache[fallback_key] = profile
        logger.debug(f"User profile cached for user {user_id}")
        
        return profile
        
    except AuthenticationError as e:
        logger.warning(f"Authentication failed: {e.message}")
        raise HTTPException(
            status_code=401,
            detail={
                "error": e.message,
                "code": e.code
            }
        )
    except EdgeFunctionError as e:
        logger.error(f"Failed to get user profile: {e.message}")
        raise HTTPException(
            status_code=403 if "not found" in e.message.lower() else 500,
            detail={
                "error": e.message,
                "code": e.code
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error getting current user: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR"
            }
        )


# Application lifecycle management
async def initialize_dependencies():
    """Initialize all services and dependencies"""
    try:
        # Initialize cache service first
        await cache_service.initialize()
        logger.info("Cache service initialized")
        
        # Initialize other services as needed
        logger.info("All dependencies initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {e}")
        raise


async def cleanup_dependencies():
    """Cleanup resources on application shutdown"""
    global _supabase_client, _litellm_service, _edge_proxy
    
    try:
        # Close all service connections
        if _supabase_client:
            await _supabase_client.close()
            _supabase_client = None
        
        if _litellm_service:
            await _litellm_service.close()
            _litellm_service = None
        
        if _edge_proxy:
            await _edge_proxy.close()
            _edge_proxy = None
        
        # Close cache service
        if cache_service:
            await cache_service.close()
        
        # Clear caches
        user_profile_cache.clear()
        
        if _auth_service:
            _auth_service.clear_cache()
        
        logger.info("Dependencies cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# Type aliases for cleaner imports (enhanced with new services)
SupabaseClientDep = Annotated[SupabaseClient, Depends(get_supabase_client)]
LiteLLMServiceDep = Annotated[LiteLLMService, Depends(get_litellm_service)]
LiteLLMClientDep = Annotated[LiteLLMService, Depends(get_litellm_client)]  # Legacy alias
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
EdgeProxyDep = Annotated[EdgeFunctionProxy, Depends(get_edge_proxy)]
CacheServiceDep = Annotated[CacheService, Depends(get_cache_service)]

# User-related dependencies
CurrentUserDep = Annotated[UserProfile, Depends(get_current_user)]
UserIdDep = Annotated[str, Depends(get_current_user_id)]
UserProfileDep = Annotated[UserProfile, Depends(get_user_profile)]
UserWithBalanceDep = Annotated[UserProfile, Depends(get_user_with_balance)]