"""Conversation management endpoints"""

from typing import Dict, Any
from fastapi import APIRouter, Header, HTTPException
from loguru import logger

from ..dependencies import UserIdDep, SupabaseClientDep
from ..utils.errors import EdgeFunctionError, ChatOrchestratorException


router = APIRouter()


@router.get(
    "/v1/conversations/{conversation_id}",
    summary="Get conversation",
    description="Get conversation information including message tree",
    tags=["Conversations"],
    responses={
        200: {"description": "Conversation data"},
        401: {"description": "Authentication failed"},
        404: {"description": "Conversation not found"},
        403: {"description": "Access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_conversation(
    conversation_id: str,
    authorization: str = Header(...),
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None
) -> Dict[str, Any]:
    """
    Get conversation information including message tree
    
    Args:
        conversation_id: Conversation UUID
        authorization: Bearer token header
        user_id: User ID from token
        supabase: Supabase client
        
    Returns:
        Conversation data with message tree
        
    Raises:
        HTTPException: If conversation not found or access denied
    """
    request_id = f"get_conv_{user_id}_{conversation_id}"
    logger.info(f"Get conversation request: {request_id}")
    
    try:
        # Use build_context to get conversation data
        # This will verify access and return the message tree
        context_data = await supabase.build_context(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=conversation_id,
            max_messages=1000  # Get all messages for conversation view
        )
        
        # The response structure will depend on what the Edge Function returns
        # Typically it would include the conversation metadata and message tree
        response_data = {
            "conversation_id": conversation_id,
            "messages": context_data.get("messages", []),
            "model": context_data.get("model"),
            "branch_id": context_data.get("branch_id"),
            "token_count": context_data.get("token_count", 0),
            "created_at": context_data.get("created_at"),
            "updated_at": context_data.get("updated_at")
        }
        
        logger.info(f"Conversation retrieved: {request_id}, {len(response_data['messages'])} messages")
        return response_data
        
    except EdgeFunctionError as e:
        logger.error(f"Edge function error in {request_id}: {e.message}")
        
        if "not found" in e.message.lower() or e.code == "NOT_FOUND_ERROR":
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Conversation not found or access denied",
                    "code": "CONVERSATION_NOT_FOUND",
                    "conversation_id": conversation_id
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": e.message,
                    "code": e.code,
                    "details": e.details
                }
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in {request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "request_id": request_id
            }
        )


@router.get(
    "/v1/conversations",
    summary="List conversations",
    description="List user's conversations",
    tags=["Conversations"]
)
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    authorization: str = Header(...),
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None
) -> Dict[str, Any]:
    """
    List user's conversations
    
    Note: This endpoint would require an additional Edge Function
    that doesn't exist in the current spec. For now, it returns
    a placeholder response.
    
    Args:
        limit: Maximum number of conversations to return
        offset: Number of conversations to skip
        authorization: Bearer token header
        user_id: User ID from token
        supabase: Supabase client
        
    Returns:
        List of conversations
    """
    request_id = f"list_conv_{user_id}"
    logger.info(f"List conversations request: {request_id}")
    
    # This would require an additional Edge Function to list conversations
    # For now, return a placeholder response
    
    return {
        "conversations": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "message": "Conversation listing not implemented. Use GET /v1/conversations/{conversation_id} to get specific conversations."
    }


@router.delete(
    "/v1/conversations/{conversation_id}",
    summary="Delete conversation",
    description="Delete a conversation and all its messages",
    tags=["Conversations"]
)
async def delete_conversation(
    conversation_id: str,
    authorization: str = Header(...),
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None
) -> Dict[str, Any]:
    """
    Delete a conversation
    
    Note: This endpoint would require an additional Edge Function
    for conversation deletion that doesn't exist in the current spec.
    
    Args:
        conversation_id: Conversation UUID to delete
        authorization: Bearer token header
        user_id: User ID from token
        supabase: Supabase client
        
    Returns:
        Deletion confirmation
    """
    request_id = f"del_conv_{user_id}_{conversation_id}"
    logger.info(f"Delete conversation request: {request_id}")
    
    # This would require an additional Edge Function to delete conversations
    # For now, return a not implemented response
    
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Conversation deletion not implemented",
            "code": "NOT_IMPLEMENTED",
            "message": "This feature requires additional Edge Function implementation"
        }
    )


@router.get(
    "/v1/conversations/{conversation_id}/branches",
    summary="List conversation branches",
    description="List all branches in a conversation",
    tags=["Conversations"]
)
async def list_conversation_branches(
    conversation_id: str,
    authorization: str = Header(...),
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None
) -> Dict[str, Any]:
    """
    List all branches in a conversation
    
    Note: This would require additional Edge Function support
    to list branches that doesn't exist in the current spec.
    
    Args:
        conversation_id: Conversation UUID
        authorization: Bearer token header
        user_id: User ID from token
        supabase: Supabase client
        
    Returns:
        List of branches
    """
    request_id = f"list_branches_{user_id}_{conversation_id}"
    logger.info(f"List branches request: {request_id}")
    
    # This would require additional Edge Function support
    # For now, return a placeholder
    
    return {
        "conversation_id": conversation_id,
        "branches": [],
        "message": "Branch listing not fully implemented. Branches are created during regeneration."
    }