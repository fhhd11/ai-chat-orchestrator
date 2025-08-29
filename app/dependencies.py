"""FastAPI dependencies for dependency injection"""

from typing import Annotated
from fastapi import Depends, Header, HTTPException
from cachetools import TTLCache
from loguru import logger

from .config import settings
from .services.supabase_client import SupabaseClient
from .services.litellm_client import LiteLLMClient
from .services.auth_service import AuthService
from .models import UserProfile
from .utils.errors import (
    AuthenticationError,
    InsufficientBalanceError,
    EdgeFunctionError
)


# Global instances
_supabase_client: SupabaseClient = None
_litellm_client: LiteLLMClient = None
_auth_service: AuthService = None

# User profile cache
user_profile_cache = TTLCache(maxsize=500, ttl=600)  # 10 minutes TTL


async def get_supabase_client() -> SupabaseClient:
    """Get Supabase client instance"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient(settings)
    return _supabase_client


async def get_litellm_client() -> LiteLLMClient:
    """Get LiteLLM client instance"""
    global _litellm_client
    if _litellm_client is None:
        _litellm_client = LiteLLMClient(settings)
    return _litellm_client


async def get_auth_service() -> AuthService:
    """Get authentication service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(settings)
    return _auth_service


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


# Cleanup function for application shutdown
async def cleanup_dependencies():
    """Cleanup resources on application shutdown"""
    global _supabase_client, _litellm_client
    
    if _supabase_client:
        await _supabase_client.close()
        _supabase_client = None
    
    if _litellm_client:
        await _litellm_client.close()
        _litellm_client = None
    
    # Clear caches
    user_profile_cache.clear()
    
    if _auth_service:
        _auth_service.clear_cache()
    
    logger.info("Dependencies cleaned up")


# Type aliases for cleaner imports
SupabaseClientDep = Annotated[SupabaseClient, Depends(get_supabase_client)]
LiteLLMClientDep = Annotated[LiteLLMClient, Depends(get_litellm_client)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserIdDep = Annotated[str, Depends(get_current_user_id)]
UserProfileDep = Annotated[UserProfile, Depends(get_user_profile)]
UserWithBalanceDep = Annotated[UserProfile, Depends(get_user_with_balance)]