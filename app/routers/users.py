"""Enhanced user management router for profile, balance, and analytics"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from ..dependencies import get_current_user, get_edge_proxy, get_cache_service
from ..models.user import (
    UserProfile, UserProfileUpdate, UserPreferences, UserUsageStats, 
    UserBalanceHistory, UserApiKeyInfo, CreateApiKeyRequest, UpdateApiKeyRequest
)
from ..models.common import SuccessResponse, ErrorResponse, PaginatedResponse
from ..services.edge_proxy import EdgeFunctionProxy
from ..services.cache_service import CacheService
from ..services.supabase_direct import SupabaseDirectClient
from ..config import settings
from ..utils.validators import ValidationUtils

router = APIRouter(prefix="/v1/users", tags=["Users"])


@router.get(
    "/me",
    response_model=SuccessResponse[UserProfile],
    summary="Get current user profile",
    description="Get the current user's complete profile information including preferences and statistics"
)
async def get_current_user_profile(
    include_usage_stats: bool = Query(False, description="Include usage statistics"),
    include_balance_info: bool = Query(False, description="Include balance information"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get current user's profile"""
    try:
        # Build cache key
        cache_key = f"user_profile:{current_user.id}:{include_usage_stats}:{include_balance_info}"
        
        # Try cache first (short TTL for user data)
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                logger.info(f"Returning cached profile for user {current_user.id}")
                return cached_result
        
        # Build query parameters
        query_params = {}
        if include_usage_stats:
            query_params["include_usage_stats"] = include_usage_stats
        if include_balance_info:
            query_params["include_balance_info"] = include_balance_info
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Use direct Supabase client instead of Edge Function
        supabase_client = SupabaseDirectClient()
        try:
            profile_data = await supabase_client.get_user_profile(current_user.id, user_token)
            response = {
                "success": True,
                "data": profile_data
            }
        finally:
            await supabase_client.close()
        
        # Cache result for 5 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=300)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/me",
    response_model=SuccessResponse[UserProfile],
    summary="Update user profile",
    description="Update the current user's profile information and preferences"
)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Update current user's profile"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path="/v1/users/me",
            user_token=user_token,
            body=profile_update.model_dump(exclude_unset=True)
        )
        
        # Invalidate user cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("users", f"user_profile:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/usage",
    response_model=SuccessResponse[UserUsageStats],
    summary="Get user usage statistics",
    description="Get detailed usage statistics for the current user"
)
async def get_user_usage_stats(
    period: str = Query("30d", regex="^(24h|7d|30d|90d|1y|all)$", description="Statistics period"),
    model_id: Optional[str] = Query(None, description="Filter by specific model"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get user usage statistics"""
    try:
        # Build cache key
        cache_key = f"user_usage:{current_user.id}:{period}:{model_id or 'all'}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Build query parameters
        query_params = {"period": period}
        if model_id:
            query_params["model_id"] = model_id
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/usage",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result for 10 minutes (usage stats change frequently)
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=600)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user usage stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/balance",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Get user balance",
    description="Get current user balance and spending information"
)
async def get_user_balance(
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get user balance information"""
    try:
        # Build cache key
        cache_key = f"user_balance:{current_user.id}"
        
        # Try cache first (very short TTL for balance)
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/balance",
            user_token=user_token
        )
        
        # Cache result for 2 minutes (balance changes frequently)
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=120)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/balance/history",
    response_model=PaginatedResponse[UserBalanceHistory],
    summary="Get balance history",
    description="Get the current user's balance transaction history"
)
async def get_balance_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get user balance transaction history"""
    try:
        # Build query parameters
        query_params = {
            "page": page,
            "page_size": page_size
        }
        if transaction_type:
            query_params["transaction_type"] = transaction_type
        if date_from:
            query_params["date_from"] = date_from
        if date_to:
            query_params["date_to"] = date_to
        
        # Build cache key
        cache_key = f"balance_history:{current_user.id}:{page}:{page_size}:{transaction_type or 'all'}:{date_from or 'start'}:{date_to or 'end'}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/balance/history",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result for 5 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=300)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting balance history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/preferences",
    response_model=SuccessResponse[UserPreferences],
    summary="Get user preferences",
    description="Get the current user's preferences and settings"
)
async def get_user_preferences(
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get user preferences"""
    try:
        # Build cache key
        cache_key = f"user_preferences:{current_user.id}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/preferences",
            user_token=user_token
        )
        
        # Cache result for 15 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=900)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/me/preferences",
    response_model=SuccessResponse[UserPreferences],
    summary="Update user preferences",
    description="Update the current user's preferences and settings"
)
async def update_user_preferences(
    preferences: UserPreferences,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Update user preferences"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path="/v1/users/me/preferences",
            user_token=user_token,
            body=preferences.model_dump(exclude_unset=True)
        )
        
        # Invalidate preferences cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("users", f"user_preferences:{current_user.id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/api-keys",
    response_model=SuccessResponse[List[UserApiKeyInfo]],
    summary="List user API keys",
    description="Get list of the current user's API keys"
)
async def list_user_api_keys(
    include_inactive: bool = Query(False, description="Include inactive keys"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """List user's API keys"""
    try:
        # Build query parameters
        query_params = {"include_inactive": include_inactive}
        
        # Build cache key
        cache_key = f"user_api_keys:{current_user.id}:{include_inactive}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/api-keys",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result for 10 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=600)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing user API keys: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/me/api-keys",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Create API key",
    description="Create a new API key for the current user"
)
async def create_api_key(
    key_request: CreateApiKeyRequest,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Create new API key"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path="/v1/users/me/api-keys",
            user_token=user_token,
            body=key_request.model_dump(exclude_unset=True)
        )
        
        # Invalidate API keys cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("users", f"user_api_keys:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/me/api-keys/{key_id}",
    response_model=SuccessResponse[UserApiKeyInfo],
    summary="Update API key",
    description="Update an existing API key"
)
async def update_api_key(
    key_id: str = Path(..., description="API key ID"),
    key_update: UpdateApiKeyRequest = None,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Update API key"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path=f"/v1/users/me/api-keys/{key_id}",
            user_token=user_token,
            body=key_update.model_dump(exclude_unset=True) if key_update else {}
        )
        
        # Invalidate API keys cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("users", f"user_api_keys:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API key {key_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/me/api-keys/{key_id}",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Delete API key",
    description="Delete an API key"
)
async def delete_api_key(
    key_id: str = Path(..., description="API key ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Delete API key"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="DELETE",
            path=f"/v1/users/me/api-keys/{key_id}",
            user_token=user_token
        )
        
        # Invalidate API keys cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("users", f"user_api_keys:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting API key {key_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/export",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Export user data",
    description="Export all user data in JSON format (GDPR compliance)"
)
async def export_user_data(
    include_conversations: bool = Query(True, description="Include conversations data"),
    include_usage_history: bool = Query(True, description="Include usage history"),
    include_balance_history: bool = Query(True, description="Include balance history"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Export all user data"""
    try:
        # Build query parameters
        query_params = {
            "include_conversations": include_conversations,
            "include_usage_history": include_usage_history,
            "include_balance_history": include_balance_history
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/export",
            user_token=user_token,
            query_params=query_params
        )
        
        logger.info(f"User data export requested for user {current_user.id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/me",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Delete user account",
    description="Delete the current user's account and all associated data"
)
async def delete_user_account(
    confirmation: str = Query(..., description="Must be 'DELETE' to confirm"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Delete user account"""
    try:
        # Require explicit confirmation
        if confirmation != "DELETE":
            raise HTTPException(
                status_code=400,
                detail="Account deletion requires confirmation parameter to be 'DELETE'"
            )
        
        # Build query parameters
        query_params = {"confirmation": confirmation}
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="DELETE",
            path="/v1/users/me",
            user_token=user_token,
            query_params=query_params
        )
        
        # Clear all user-related cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("users", f"*{current_user.id}*")
            await cache_service.delete_pattern("conversations", f"*{current_user.id}*")
            await cache_service.delete_pattern("models", f"*{current_user.id}*")
        
        logger.warning(f"User account deletion completed for user {current_user.id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user account: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/me/analytics/dashboard",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Get user analytics dashboard",
    description="Get comprehensive analytics data for user dashboard"
)
async def get_user_analytics_dashboard(
    period: str = Query("30d", regex="^(24h|7d|30d|90d|1y)$", description="Analytics period"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get user analytics dashboard data"""
    try:
        # Build cache key
        cache_key = f"user_analytics:{current_user.id}:{period}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("users", cache_key)
            if cached_result:
                return cached_result
        
        # Build query parameters
        query_params = {"period": period}
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/users/me/analytics/dashboard",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result for 15 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("users", cache_key, response, ttl=900)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")