"""Chat completion endpoints"""

import asyncio
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from ..config import settings
from ..models import (
    ChatCompletionRequest, 
    RegenerateRequest,
    ConversationResponse,
    ErrorResponse
)
from ..dependencies import (
    UserWithBalanceDep,
    SupabaseClientDep, 
    LiteLLMClientDep,
    UserIdDep
)
from ..utils.streaming import (
    create_sse_response, 
    stream_chat_completion,
    StreamAccumulator
)
from ..utils.errors import (
    ChatOrchestratorException,
    EdgeFunctionError,
    LiteLLMError,
    InsufficientBalanceError
)


router = APIRouter()


@router.post(
    "/v1/chat/completions",
    summary="Chat completions",
    description="Create a chat completion, optionally streaming",
    tags=["Chat"],
    responses={
        200: {"description": "Successful response"},
        401: {"description": "Authentication failed"},
        402: {"description": "Insufficient balance"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    authorization: str = Header(...),
    user_profile: UserWithBalanceDep = None,
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None,
    litellm: LiteLLMClientDep = None
):
    """
    Main chat completion endpoint with streaming support
    
    Flow:
    1. Validate user and check balance
    2. Add user message to conversation
    3. Build conversation context
    4. Stream response from LiteLLM
    5. Save assistant response in background
    
    Args:
        request: Chat completion request data
        background_tasks: FastAPI background tasks
        authorization: Bearer token header
        user_profile: User profile with verified balance
        user_id: User ID from token
        supabase: Supabase client
        litellm: LiteLLM client
        
    Returns:
        StreamingResponse for SSE or JSON response
    """
    request_id = f"chat_{user_id}_{request.conversation_id or 'new'}"
    logger.info(f"Chat completion request started: {request_id}")
    
    try:
        # Step 1: Add user message to conversation
        logger.info(f"Adding user message to conversation: {request_id}")
        message_data = await supabase.add_message(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=request.conversation_id,
            content=request.message,
            role="user",
            parent_id=request.parent_message_id
        )
        
        conversation_id = message_data["conversation_id"]
        branch_id = message_data["branch_id"]
        user_message_id = message_data["message_id"]
        
        logger.info(f"User message added: {user_message_id} in conversation {conversation_id}")
        
        # Step 2: Build conversation context
        logger.info(f"Building context for conversation: {conversation_id}")
        context_data = await supabase.build_context(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=conversation_id,
            branch_id=branch_id,
            max_messages=settings.max_context_messages
        )
        
        messages = context_data["messages"]
        model = request.model or context_data.get("model", "gemini/gemini-2.0-flash-exp")
        
        logger.info(f"Context built: {len(messages)} messages, model: {model}")
        
        # Step 3: Prepare LiteLLM request parameters
        llm_params = {
            "messages": messages,
            "model": model,
            "user_key": user_profile.litellm_key,
            "user_id": user_id,
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 2000
        }
        
        # Step 4: Handle streaming vs non-streaming
        if request.stream:
            # Streaming response
            logger.info(f"Starting streaming response: {request_id}")
            
            async def chat_stream():
                """Generate SSE stream with error handling"""
                full_response = ""
                try:
                    async for chunk, accumulated_response in litellm.stream_chat_completion(**llm_params):
                        full_response = accumulated_response
                        yield chunk
                    
                    # Schedule background task to save response
                    background_tasks.add_task(
                        save_assistant_response,
                        supabase=supabase,
                        user_token=authorization.split("Bearer ")[1],
                        conversation_id=conversation_id,
                        branch_id=branch_id,
                        parent_id=user_message_id,
                        content=full_response,
                        model=model,
                        request_id=request_id
                    )
                    
                    logger.info(f"Streaming completed: {request_id}")
                    
                except Exception as e:
                    logger.error(f"Error in streaming: {request_id}, {e}")
                    raise
            
            return await create_sse_response(chat_stream())
        
        else:
            # Non-streaming response
            logger.info(f"Starting non-streaming response: {request_id}")
            
            accumulator = StreamAccumulator()
            
            # Collect entire response
            async def collect_stream():
                async for chunk, _ in litellm.stream_chat_completion(**llm_params):
                    yield chunk
            
            response_data = await accumulator.accumulate_stream(collect_stream())
            
            # Save response in background
            background_tasks.add_task(
                save_assistant_response,
                supabase=supabase,
                user_token=authorization.split("Bearer ")[1],
                conversation_id=conversation_id,
                branch_id=branch_id,
                parent_id=user_message_id,
                content=response_data["choices"][0]["message"]["content"],
                model=model,
                request_id=request_id
            )
            
            logger.info(f"Non-streaming completed: {request_id}")
            return response_data
            
    except InsufficientBalanceError as e:
        logger.warning(f"Insufficient balance for user {user_id}: {e.message}")
        raise HTTPException(
            status_code=402,
            detail={
                "error": e.message,
                "code": e.code,
                "details": e.details
            }
        )
        
    except EdgeFunctionError as e:
        logger.error(f"Edge function error in {request_id}: {e.message}")
        raise HTTPException(
            status_code=500 if e.code != "NOT_FOUND_ERROR" else 404,
            detail={
                "error": e.message,
                "code": e.code,
                "details": e.details
            }
        )
        
    except LiteLLMError as e:
        logger.error(f"LiteLLM error in {request_id}: {e.message}")
        status_code = 429 if e.code == "RATE_LIMIT_EXCEEDED" else 500
        raise HTTPException(
            status_code=status_code,
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


@router.post(
    "/v1/chat/regenerate",
    response_model=ConversationResponse,
    summary="Regenerate response",
    description="Regenerate assistant response by creating a new branch",
    tags=["Chat"]
)
async def regenerate_response(
    request: RegenerateRequest,
    background_tasks: BackgroundTasks,
    authorization: str = Header(...),
    user_profile: UserWithBalanceDep = None,
    user_id: UserIdDep = None,
    supabase: SupabaseClientDep = None,
    litellm: LiteLLMClientDep = None
):
    """
    Regenerate assistant response by creating a new branch
    
    Args:
        request: Regenerate request data
        background_tasks: FastAPI background tasks
        authorization: Bearer token header
        user_profile: User profile with verified balance
        user_id: User ID from token
        supabase: Supabase client
        litellm: LiteLLM client
        
    Returns:
        ConversationResponse with new branch info
    """
    request_id = f"regen_{user_id}_{request.conversation_id}"
    logger.info(f"Regeneration request started: {request_id}")
    
    try:
        # Step 1: Create new branch
        logger.info(f"Creating new branch for regeneration: {request_id}")
        branch_data = await supabase.create_branch(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=request.conversation_id,
            from_message_id=request.message_id,
            name=f"Regeneration {asyncio.get_event_loop().time()}"
        )
        
        new_branch_id = branch_data["branch_id"]
        logger.info(f"New branch created: {new_branch_id}")
        
        # Step 2: Build context for the new branch
        context_data = await supabase.build_context(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=request.conversation_id,
            branch_id=new_branch_id,
            max_messages=settings.max_context_messages
        )
        
        messages = context_data["messages"]
        model = request.model or context_data.get("model", "gemini/gemini-2.0-flash-exp")
        
        # Step 3: Generate new response
        llm_params = {
            "messages": messages,
            "model": model,
            "user_key": user_profile.litellm_key,
            "user_id": user_id,
            "temperature": request.temperature or 0.7,
            "max_tokens": 2000
        }
        
        # Collect response (non-streaming for regeneration)
        accumulator = StreamAccumulator()
        
        async def collect_stream():
            async for chunk, _ in litellm.stream_chat_completion(**llm_params):
                yield chunk
        
        response_data = await accumulator.accumulate_stream(collect_stream())
        response_content = response_data["choices"][0]["message"]["content"]
        
        # Step 4: Save the regenerated response
        await supabase.save_response(
            user_token=authorization.split("Bearer ")[1],
            conversation_id=request.conversation_id,
            branch_id=new_branch_id,
            parent_id=request.message_id,
            content=response_content,
            model=model
        )
        
        logger.info(f"Regeneration completed: {request_id}")
        
        return ConversationResponse(
            conversation_id=request.conversation_id,
            branch_id=new_branch_id,
            message_id="generated"  # We don't get the message ID back immediately
        )
        
    except ChatOrchestratorException as e:
        logger.error(f"Error in regeneration {request_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": e.message,
                "code": e.code,
                "details": e.details
            }
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in regeneration {request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "request_id": request_id
            }
        )


async def save_assistant_response(
    supabase: SupabaseClientDep,
    user_token: str,
    conversation_id: str,
    branch_id: str,
    parent_id: str,
    content: str,
    model: str,
    request_id: str
):
    """
    Background task to save assistant response
    
    Args:
        supabase: Supabase client
        user_token: User JWT token
        conversation_id: Conversation ID
        branch_id: Branch ID
        parent_id: Parent message ID
        content: Assistant response content
        model: Model name used
        request_id: Request ID for logging
    """
    try:
        logger.info(f"Saving assistant response: {request_id}")
        
        await supabase.save_response(
            user_token=user_token,
            conversation_id=conversation_id,
            branch_id=branch_id,
            parent_id=parent_id,
            content=content,
            model=model
        )
        
        logger.info(f"Assistant response saved: {request_id}")
        
    except Exception as e:
        logger.error(f"Failed to save assistant response {request_id}: {e}", exc_info=True)