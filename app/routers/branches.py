"""Branch management router for conversation branching operations"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from typing import Optional, List, Dict, Any
from loguru import logger

from ..dependencies import get_current_user, get_edge_proxy, get_cache_service
from ..models.conversation import BranchInfo, CreateBranchRequest, SwitchBranchRequest
from ..models.common import SuccessResponse, ErrorResponse
from ..models.user import UserProfile
from ..services.edge_proxy import EdgeFunctionProxy
from ..services.cache_service import CacheService
from ..config import settings

router = APIRouter(prefix="/v1/conversations/{conversation_id}/branches", tags=["Branches"])


@router.get(
    "",
    response_model=SuccessResponse[List[BranchInfo]],
    summary="List conversation branches",
    description="""
    Get all branches for a specific conversation.
    
    Returns detailed information about each branch including:
    - Branch ID and name
    - Status and activity
    - Message count
    - Creation and update timestamps
    - Parent message information
    """
)
async def list_branches(
    conversation_id: str = Path(..., description="Conversation ID"),
    include_inactive: bool = Query(False, description="Include inactive branches"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """List all branches for a conversation"""
    try:
        # Build query parameters
        query_params = {
            "include_inactive": include_inactive,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        
        # Try cache first
        cache_key = f"conversation_branches:{conversation_id}:{include_inactive}:{sort_by}:{sort_order}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("conversations", cache_key)
            if cached_result:
                logger.info(f"Returning cached branch list for conversation {conversation_id}")
                return cached_result
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/conversations/{conversation_id}/branches",
            user_token=user_token,
            query_params=query_params
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=300)  # 5 minutes
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing branches for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "",
    response_model=SuccessResponse[BranchInfo],
    summary="Create new branch",
    description="""
    Create a new branch from a specific message in the conversation.
    
    This allows users to explore alternative conversation paths by branching
    from any point in the conversation history.
    """
)
async def create_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_request: CreateBranchRequest = None,
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Create a new branch from a message"""
    try:
        # Validate branch limit
        if settings.max_branches_per_conversation > 0:
            # This would typically check the current branch count
            # For now, we'll rely on the Edge Function to enforce limits
            pass
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/conversations/{conversation_id}/branches",
            user_token=user_token,
            body=branch_request.model_dump(exclude_unset=True) if branch_request else {}
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating branch for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{branch_id}/activate",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Activate branch",
    description="""
    Switch the active branch for a conversation.
    
    This changes which branch is used for new messages and responses.
    Only one branch can be active at a time per conversation.
    """
)
async def activate_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID to activate"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Activate a specific branch"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}/activate",
            user_token=user_token
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
            await cache_service.delete_pattern("conversations", f"conversations_list:{current_user.id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating branch {branch_id} for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{branch_id}",
    response_model=SuccessResponse[BranchInfo],
    summary="Get branch details",
    description="Get detailed information about a specific branch"
)
async def get_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get details of a specific branch"""
    try:
        # Try cache first
        cache_key = f"branch_detail:{branch_id}"
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
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}",
            user_token=user_token
        )
        
        # Cache result
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=300)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting branch {branch_id} for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/{branch_id}",
    response_model=SuccessResponse[BranchInfo],
    summary="Update branch",
    description="Update branch properties such as name or status"
)
async def update_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID"),
    name: Optional[str] = Query(None, description="New branch name"),
    status: Optional[str] = Query(None, description="New branch status"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Update branch properties"""
    try:
        # Build update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if status is not None:
            update_data["status"] = status
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="PATCH",
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}",
            user_token=user_token,
            body=update_data
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("conversations", f"branch_detail:{branch_id}")
            await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating branch {branch_id} for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{branch_id}",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Delete branch",
    description="""
    Delete a branch and all its messages.
    
    Note: Cannot delete the main branch or the currently active branch.
    """
)
async def delete_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Delete a branch"""
    try:
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="DELETE",
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}",
            user_token=user_token
        )
        
        # Invalidate related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete("conversations", f"branch_detail:{branch_id}")
            await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting branch {branch_id} for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{branch_id}/messages",
    response_model=SuccessResponse[List[Dict[str, Any]]],
    summary="Get branch messages",
    description="Get all messages in a specific branch"
)
async def get_branch_messages(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID"),
    include_metadata: bool = Query(False, description="Include message metadata"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of messages"),
    offset: Optional[int] = Query(0, ge=0, description="Offset for pagination"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy)
):
    """Get messages in a specific branch"""
    try:
        # Build query parameters
        query_params = {
            "include_metadata": include_metadata
        }
        if limit is not None:
            query_params["limit"] = limit
        if offset is not None:
            query_params["offset"] = offset
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="GET",
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}/messages",
            user_token=user_token,
            query_params=query_params
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages for branch {branch_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{branch_id}/merge",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Merge branch",
    description="""
    Merge a branch back into the main branch.
    
    This operation combines the messages from the specified branch
    into the main conversation branch.
    """
)
async def merge_branch(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID to merge"),
    target_branch_id: Optional[str] = Query(None, description="Target branch (defaults to main branch)"),
    delete_source_branch: bool = Query(True, description="Delete source branch after merge"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Merge branch into another branch"""
    try:
        # Build request data
        merge_data = {
            "target_branch_id": target_branch_id,
            "delete_source_branch": delete_source_branch
        }
        
        # Get JWT token from request
        auth_header = request.headers.get("Authorization", "")
        user_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Proxy request to Edge Function
        response = await edge_proxy.proxy_request(
            method="POST",
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}/merge",
            user_token=user_token,
            body=merge_data
        )
        
        # Invalidate all related cache entries
        if settings.redis_enabled and response.get("success"):
            await cache_service.delete_pattern("conversations", f"conversation_branches:{conversation_id}:*")
            await cache_service.delete("conversations", f"conversation_detail:{conversation_id}")
            await cache_service.delete("conversations", f"branch_detail:{branch_id}")
            if target_branch_id:
                await cache_service.delete("conversations", f"branch_detail:{target_branch_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging branch {branch_id} for conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{branch_id}/stats",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Get branch statistics",
    description="Get detailed statistics for a specific branch"
)
async def get_branch_stats(
    conversation_id: str = Path(..., description="Conversation ID"),
    branch_id: str = Path(..., description="Branch ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    edge_proxy: EdgeFunctionProxy = Depends(get_edge_proxy),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get statistics for a specific branch"""
    try:
        # Try cache first
        cache_key = f"branch_stats:{branch_id}"
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
            path=f"/v1/conversations/{conversation_id}/branches/{branch_id}/stats",
            user_token=user_token
        )
        
        # Cache result for 5 minutes
        if settings.redis_enabled and response.get("success"):
            await cache_service.set("conversations", cache_key, response, ttl=300)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats for branch {branch_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")