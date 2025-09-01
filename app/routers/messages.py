"""Message management router for message operations"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request, Body
from typing import Optional, List, Dict, Any
from loguru import logger

from ..dependencies import get_current_user, get_edge_proxy, get_cache_service
from ..models.message import (
    MessageDetail, MessageListItem, EditMessageRequest, RegenerateMessageRequest,
    MessageSearchFilters, MessageThread, MessageStats, BatchMessageOperation
)
from ..models.common import SuccessResponse, PaginatedResponse, PaginationParams
from ..models.user import UserProfile
from ..services.edge_proxy import EdgeFunctionProxy
from ..services.cache_service import CacheService
from ..config import settings

router = APIRouter(prefix="/v1/messages", tags=["Messages"])


@router.get(
    "/{message_id}",
    response_model=SuccessResponse[MessageDetail],
    summary="Get message details",
    description="""
    Get detailed information about a specific message.
    
    Includes:
    - Message content and metadata
    - Author and model information
    - Token usage and cost data
    - Parent/child relationships
    - Branch information
    """
)
async def get_message(
    message_id: str = Path(..., description="Message ID"),
    include_children: bool = Query(False, description="Include child messages"),
    include_siblings: bool = Query(False, description="Include sibling messages"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get detailed information about a message"""
    try:
        # Build query parameters
        query_params = {
            "include_children": include_children,
            "include_siblings": include_siblings
        }
        
        # Try cache first
        cache_key = f"message_detail:{message_id}:{include_children}:{include_siblings}"
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
            path=f"/v1/messages/{message_id}",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=300)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/{message_id}",
    response_model=SuccessResponse[MessageDetail],
    summary="Edit message",
    description="""
    Edit a user message content.
    
    Can optionally create a new branch from the edit point to preserve
    the original conversation flow while exploring alternatives.
    """
)
async def edit_message(
    message_id: str = Path(..., description="Message ID"),
    edit_request: EditMessageRequest = Body(...),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Edit a user message"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path=f"/v1/messages/{message_id}",
            user_token=user_token,
            body=edit_request.model_dump(exclude_unset=True)
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"message_detail:{message_id}:*")
            # Get conversation ID from response to invalidate conversation cache
            if response.get("data") and response["data"].get("conversation_id"):
                conversation_id = response["data"]["conversation_id"]
                await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
                await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{message_id}/regenerate",
    response_model=SuccessResponse[MessageDetail],
    summary="Regenerate message response",
    description="""
    Regenerate an assistant message with different parameters.
    
    This creates a new branch and generates a new response using the
    specified model and parameters, preserving the original response
    in the conversation tree.
    """
)
async def regenerate_message(
    message_id: str = Path(..., description="Message ID to regenerate"),
    regenerate_request: RegenerateMessageRequest = Body(...),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Regenerate an assistant message"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/messages/{message_id}/regenerate",
            user_token=user_token,
            body=regenerate_request.model_dump(exclude_unset=True)
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"message_detail:{message_id}:*")
            # Invalidate conversation-level cache
            if response.get("data") and response["data"].get("conversation_id"):
                conversation_id = response["data"]["conversation_id"]
                await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
                await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{message_id}",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Delete message",
    description="""
    Delete a message and all its children.
    
    Warning: This operation cannot be undone and will remove
    the message and all responses that came after it.
    """
)
async def delete_message(
    message_id: str = Path(..., description="Message ID"),
    delete_children: bool = Query(True, description="Delete child messages"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Delete a message and optionally its children"""
    try:
        # Build query parameters
        query_params = {
            "delete_children": delete_children
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="DELETE",
            path=f"/v1/messages/{message_id}",
            user_token=user_token,
            query_params=query_params
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"message_detail:{message_id}:*")
            # Invalidate conversation-level cache
            if response.get("data") and response["data"].get("conversation_id"):
                conversation_id = response["data"]["conversation_id"]
                await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
                await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{message_id}/thread",
    response_model=SuccessResponse[MessageThread],
    summary="Get message thread",
    description="""
    Get the complete thread (conversation path) that leads to this message.
    
    Returns all messages from the conversation root to the specified message,
    following the branch path.
    """
)
async def get_message_thread(
    message_id: str = Path(..., description="Message ID"),
    include_metadata: bool = Query(False, description="Include message metadata"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get the complete message thread leading to a message"""
    try:
        # Build query parameters
        query_params = {
            "include_metadata": include_metadata
        }
        
        # Try cache first
        cache_key = f"message_thread:{message_id}:{include_metadata}"
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
            path=f"/v1/messages/{message_id}/thread",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=600)  # 10 minutes
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thread for message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{message_id}/children",
    response_model=SuccessResponse[List[MessageListItem]],
    summary="Get message children",
    description="Get all direct children (responses) to this message"
)
async def get_message_children(
    message_id: str = Path(..., description="Message ID"),
    include_metadata: bool = Query(False, description="Include message metadata"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Get all children of a message"""
    try:
        # Build query parameters
        query_params = {
            "include_metadata": include_metadata,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/messages/{message_id}/children",
            user_token=user_token,
            query_params=query_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting children for message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{message_id}/siblings",
    response_model=SuccessResponse[List[MessageListItem]],
    summary="Get message siblings",
    description="Get all sibling messages (alternative responses) to this message"
)
async def get_message_siblings(
    message_id: str = Path(..., description="Message ID"),
    include_self: bool = Query(False, description="Include the message itself in results"),
    include_metadata: bool = Query(False, description="Include message metadata"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Get all sibling messages (alternatives with same parent)"""
    try:
        # Build query parameters
        query_params = {
            "include_self": include_self,
            "include_metadata": include_metadata
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/messages/{message_id}/siblings",
            user_token=user_token,
            query_params=query_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting siblings for message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{message_id}/copy",
    response_model=SuccessResponse[MessageDetail],
    summary="Copy message to another conversation",
    description="Copy a message and optionally its thread to another conversation"
)
async def copy_message(
    message_id: str = Path(..., description="Message ID to copy"),
    target_conversation_id: str = Body(..., embed=True, description="Target conversation ID"),
    copy_thread: bool = Body(False, embed=True, description="Copy entire thread"),
    target_branch_id: Optional[str] = Body(None, embed=True, description="Target branch ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Copy a message to another conversation"""
    try:
        # Build request body
        copy_data = {
            "target_conversation_id": target_conversation_id,
            "copy_thread": copy_thread,
            "target_branch_id": target_branch_id
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/messages/{message_id}/copy",
            user_token=user_token,
            body=copy_data
        )
        
        # Invalidate target conversation cache
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("conversations", f"conversation_detail:{target_conversation_id}")
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{message_id}/bookmark",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Bookmark message",
    description="Add or remove a bookmark for this message"
)
async def toggle_message_bookmark(
    message_id: str = Path(..., description="Message ID"),
    bookmarked: bool = Body(True, embed=True, description="Bookmark status"),
    note: Optional[str] = Body(None, embed=True, description="Optional bookmark note"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Toggle bookmark status for a message"""
    try:
        # Build request body
        bookmark_data = {
            "bookmarked": bookmarked,
            "note": note
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/messages/{message_id}/bookmark",
            user_token=user_token,
            body=bookmark_data
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling bookmark for message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/search",
    response_model=PaginatedResponse[MessageListItem],
    summary="Search messages",
    description="""
    Search through user's messages with advanced filtering options.
    
    Supports full-text search, filtering by model, role, date ranges,
    and various other criteria.
    """
)
async def search_messages(
    # Search parameters
    q: Optional[str] = Query(None, description="Search query"),
    conversation_id: Optional[str] = Query(None, description="Filter by conversation"),
    role: Optional[str] = Query(None, description="Filter by message role"),
    model: Optional[str] = Query(None, description="Filter by model"),
    created_after: Optional[str] = Query(None, description="Created after date"),
    created_before: Optional[str] = Query(None, description="Created before date"),
    has_branches: Optional[bool] = Query(None, description="Has branches filter"),
    min_tokens: Optional[int] = Query(None, description="Minimum token count"),
    max_tokens: Optional[int] = Query(None, description="Maximum token count"),
    bookmarked_only: Optional[bool] = Query(False, description="Only bookmarked messages"),
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Search messages with advanced filtering"""
    try:
        # Build search parameters
        search_params = {
            "page": page,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        # Add search filters
        if q:
            search_params["q"] = q
        if conversation_id:
            search_params["conversation_id"] = conversation_id
        if role:
            search_params["role"] = role
        if model:
            search_params["model"] = model
        if created_after:
            search_params["created_after"] = created_after
        if created_before:
            search_params["created_before"] = created_before
        if has_branches is not None:
            search_params["has_branches"] = has_branches
        if min_tokens is not None:
            search_params["min_tokens"] = min_tokens
        if max_tokens is not None:
            search_params["max_tokens"] = max_tokens
        if bookmarked_only:
            search_params["bookmarked_only"] = bookmarked_only
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path="/v1/messages/search",
            user_token=user_token,
            query_params=search_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/batch",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Batch message operations",
    description="Perform batch operations on multiple messages"
)
async def batch_message_operations(
    operation: BatchMessageOperation = Body(...),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Perform batch operations on messages"""
    try:
        # Validate batch size
        if len(operation.message_ids) > settings.max_batch_operation_size:
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
            path="/v1/messages/batch",
            user_token=user_token,
            body=operation.model_dump()
        )
        
        # Invalidate cache for affected messages
        if settings.redis_enabled and response.get("success"):
            for message_id in operation.message_ids:
                await cache_service.delete_pattern("conversations", f"message_detail:{message_id}:*")
            # Also invalidate conversation lists
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch message operation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")