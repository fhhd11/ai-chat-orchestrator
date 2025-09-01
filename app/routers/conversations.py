"""Enhanced conversation management router with full CRUD operations and search"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from typing import Optional, List, Dict, Any
from loguru import logger

from ..dependencies import get_current_user, get_edge_proxy, get_cache_service
from ..models.conversation import (
    ConversationListItem, ConversationDetail, ConversationSearchFilters,
    UpdateConversationRequest, CreateConversationRequest, ConversationStats,
    BatchConversationOperation, ConversationExportRequest
)
from ..models.common import PaginatedResponse, PaginationParams, SuccessResponse, ErrorResponse
from ..models.user import UserProfile
from ..services.edge_proxy import EdgeFunctionProxy
from ..services.cache_service import CacheService
from ..config import settings

router = APIRouter(prefix="/v1/conversations", tags=["Conversations"])


@router.get(
    "",
    response_model=PaginatedResponse[ConversationListItem],
    summary="List conversations",
    description="""
    Get paginated list of user conversations with optional search and filtering.
    
    Supports:
    - Pagination with configurable page size
    - Full-text search in conversation titles
    - Filtering by model, status, creation date
    - Sorting by various fields
    - Caching for performance
    """
)
async def list_conversations(
    request: Request,
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: Optional[str] = Query("updated_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    
    # Search and filtering
    q: Optional[str] = Query(None, min_length=1, max_length=200, description="Search query"),
    model: Optional[str] = Query(None, description="Filter by model"),
    status: Optional[str] = Query(None, description="Filter by status"),
    created_after: Optional[str] = Query(None, description="Created after date (ISO format)"),
    created_before: Optional[str] = Query(None, description="Created before date (ISO format)"),
    has_branches: Optional[bool] = Query(None, description="Filter conversations with branches"),
    min_messages: Optional[int] = Query(None, ge=0, description="Minimum message count"),
    max_messages: Optional[int] = Query(None, ge=0, description="Maximum message count"),
    
    # Dependencies
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """List user conversations with pagination and filtering"""
    try:
        # Build query parameters
        query_params = {
            "page": page,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        # Add search and filter parameters
        if q:
            query_params["q"] = q
        if model:
            query_params["model"] = model
        if status:
            query_params["status"] = status
        if created_after:
            query_params["created_after"] = created_after
        if created_before:
            query_params["created_before"] = created_before
        if has_branches is not None:
            query_params["has_branches"] = has_branches
        if min_messages is not None:
            query_params["min_messages"] = min_messages
        if max_messages is not None:
            query_params["max_messages"] = max_messages
        
        # Try cache first for simple queries (no search/complex filters)
        cache_key = None
        if settings.redis_enabled and not any([q, created_after, created_before, has_branches, min_messages, max_messages]):
            cache_key = f"conversations_list:{current_user.id}:{page}:{limit}:{sort_by}:{sort_order}:{model}:{status}"
            cached_result = await cache_service.get("conversations", cache_key)
            if cached_result:
                logger.info(f"Returning cached conversation list for user {current_user.id}")
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/conversations",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result if applicable
        if cache_key and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=settings.cache_ttl_conversations)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing conversations for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{conversation_id}",
    response_model=SuccessResponse[ConversationDetail],
    summary="Get conversation details",
    description="Get basic conversation information without full message history"
)
async def get_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get conversation basic details"""
    try:
        # Try cache first
        cache_key = f"conversation_detail:{conversation_id}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("conversations", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/conversations/{conversation_id}",
            user_token=user_token
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=settings.cache_ttl_conversations)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{conversation_id}/full",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Get full conversation",
    description="Get complete conversation with all branches and messages"
)
async def get_conversation_full(
    conversation_id: str = Path(..., description="Conversation ID"),
    include_metadata: bool = Query(True, description="Include message metadata"),
    branch_id: Optional[str] = Query(None, description="Specific branch ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Get full conversation with all branches and messages"""
    try:
        # Build query parameters
        query_params = {
            "include_metadata": include_metadata
        }
        if branch_id:
            query_params["branch_id"] = branch_id
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/conversations/{conversation_id}/full",
            user_token=user_token,
            query_params=query_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting full conversation {conversation_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/{conversation_id}",
    response_model=SuccessResponse[ConversationDetail],
    summary="Update conversation",
    description="Update conversation title, model, or other properties"
)
async def update_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    update_data: UpdateConversationRequest = None,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Update conversation properties"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path=f"/v1/conversations/{conversation_id}",
            user_token=user_token,
            body=update_data.model_dump(exclude_unset=True) if update_data else {}
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation {conversation_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "",
    response_model=SuccessResponse[ConversationDetail],
    summary="Create conversation",
    description="Create a new conversation"
)
async def create_conversation(
    create_data: CreateConversationRequest = None,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Create a new conversation"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path="/v1/conversations",
            user_token=user_token,
            body=create_data.model_dump(exclude_unset=True) if create_data else {}
        )
        
        # Invalidate list cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{conversation_id}",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Delete conversation",
    description="Delete a conversation and all its data"
)
async def delete_conversation(
    conversation_id: str = Path(..., description="Conversation ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Delete conversation"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="DELETE",
            path=f"/v1/conversations/{conversation_id}",
            user_token=user_token
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/search/advanced",
    response_model=PaginatedResponse[ConversationListItem],
    summary="Advanced conversation search",
    description="Advanced search with multiple criteria and aggregations"
)
async def search_conversations(
    # Advanced search parameters
    query: Optional[str] = Query(None, description="Search query"),
    search_in: Optional[str] = Query("title", regex="^(title|content|all)$", description="Search scope"),
    models: Optional[str] = Query(None, description="Comma-separated list of models"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    min_messages: Optional[int] = Query(None, ge=0, description="Minimum messages"),
    max_messages: Optional[int] = Query(None, ge=0, description="Maximum messages"),
    has_branches: Optional[bool] = Query(None, description="Has branches filter"),
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    
    # Dependencies
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Advanced conversation search with multiple criteria"""
    try:
        # Build search parameters
        search_params = {
            "page": page,
            "limit": limit
        }
        
        if query:
            search_params["q"] = query
        if search_in:
            search_params["search_in"] = search_in
        if models:
            search_params["models"] = models
        if date_from:
            search_params["date_from"] = date_from
        if date_to:
            search_params["date_to"] = date_to
        if min_messages is not None:
            search_params["min_messages"] = min_messages
        if max_messages is not None:
            search_params["max_messages"] = max_messages
        if has_branches is not None:
            search_params["has_branches"] = has_branches
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/conversations/search",
            user_token=user_token,
            query_params=search_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching conversations for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/stats/overview",
    response_model=SuccessResponse[ConversationStats],
    summary="Get conversation statistics",
    description="Get user's conversation statistics and analytics"
)
async def get_conversation_stats(
    period: Optional[str] = Query("month", regex="^(week|month|year|all)$", description="Statistics period"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get conversation statistics"""
    try:
        # Try cache first
        cache_key = f"conversation_stats:{current_user.id}:{period}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("user_profiles", cache_key)
            if cached_result:
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/conversations/stats",
            user_token=user_token,
            query_params={"period": period}
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("user_profiles", cache_key, response, ttl=900)  # 15 minutes
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation stats for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/batch",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Batch conversation operations",
    description="Perform batch operations on multiple conversations"
)
async def batch_conversation_operations(
    operation: BatchConversationOperation,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Perform batch operations on conversations"""
    try:
        # Validate batch size
        if len(operation.conversation_ids) > settings.max_batch_operation_size:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size exceeds maximum of {settings.max_batch_operation_size}"
            )
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path="/v1/conversations/batch",
            user_token=user_token,
            body=operation.model_dump()
        )
        
        # Invalidate cache for affected conversations
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
            for conversation_id in operation.conversation_ids:
                await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch conversation operation for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/export",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Export conversations",
    description="Export selected conversations to various formats"
)
async def export_conversations(
    export_request: ConversationExportRequest,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Export conversations to various formats"""
    try:
        # Validate export size
        if len(export_request.conversation_ids) > settings.max_export_conversations:
            raise HTTPException(
                status_code=400,
                detail=f"Export size exceeds maximum of {settings.max_export_conversations}"
            )
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path="/v1/conversations/export",
            user_token=user_token,
            body=export_request.model_dump()
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting conversations for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")