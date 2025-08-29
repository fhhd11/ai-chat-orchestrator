"""SSE streaming utilities"""

import json
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse
from loguru import logger

from ..utils.errors import ChatOrchestratorException


class SSEFormatter:
    """Format data for Server-Sent Events (SSE)"""
    
    @staticmethod
    def format_data(data: Dict[str, Any]) -> str:
        """Format data as SSE event"""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_error(error: str, code: str = None, details: Dict[str, Any] = None) -> str:
        """Format error as SSE event"""
        error_data = {
            "error": error,
        }
        if code:
            error_data["code"] = code
        if details:
            error_data["details"] = details
            
        return f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_done() -> str:
        """Format 'done' signal as SSE event"""
        return "data: [DONE]\n\n"
    
    @staticmethod
    def format_chunk(content: str, chunk_id: str = None, finish_reason: str = None) -> str:
        """Format chat completion chunk as SSE event"""
        chunk_data = {
            "choices": [{
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason
            }]
        }
        
        if chunk_id:
            chunk_data["id"] = chunk_id
            
        return f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
    
    @staticmethod
    def format_heartbeat() -> str:
        """Format heartbeat event to keep connection alive"""
        return ": heartbeat\n\n"


async def create_sse_response(
    generator: AsyncGenerator[str, None],
    media_type: str = "text/plain; charset=utf-8"
) -> StreamingResponse:
    """
    Create SSE streaming response
    
    Args:
        generator: Async generator yielding SSE formatted strings
        media_type: Response media type
        
    Returns:
        StreamingResponse configured for SSE
    """
    
    async def event_stream():
        """Event stream generator with error handling"""
        try:
            async for chunk in generator:
                yield chunk
        except ChatOrchestratorException as e:
            logger.error(f"SSE stream error: {e.message}")
            yield SSEFormatter.format_error(
                error=e.message,
                code=e.code,
                details=e.details
            )
        except Exception as e:
            logger.error(f"Unexpected SSE stream error: {e}")
            yield SSEFormatter.format_error(
                error="Internal server error",
                code="INTERNAL_ERROR"
            )
        finally:
            # Always end with DONE signal
            yield SSEFormatter.format_done()
    
    return StreamingResponse(
        event_stream(),
        media_type=media_type,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


async def stream_chat_completion(
    messages: list,
    model: str,
    user_id: str,
    litellm_client,
    user_key: str,
    **kwargs
) -> AsyncGenerator[str, None]:
    """
    Stream chat completion with proper SSE formatting
    
    Args:
        messages: Chat messages
        model: Model name
        user_id: User ID
        litellm_client: LiteLLM client instance
        user_key: User's API key
        **kwargs: Additional parameters
        
    Yields:
        SSE formatted chunks
    """
    try:
        logger.info(f"Starting chat completion stream for user {user_id}")
        
        # Stream from LiteLLM
        async for chunk_data, full_response in litellm_client.stream_chat_completion(
            messages=messages,
            model=model,
            user_key=user_key,
            user_id=user_id,
            **kwargs
        ):
            # Forward the chunk (it's already SSE formatted by LiteLLM client)
            yield chunk_data
            
        logger.info(f"Chat completion stream completed for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in chat completion stream: {e}")
        # Let the error bubble up to be handled by create_sse_response
        raise


async def generate_sse_heartbeat() -> AsyncGenerator[str, None]:
    """
    Generate heartbeat events to keep SSE connection alive
    
    Yields:
        SSE heartbeat events
    """
    import asyncio
    
    while True:
        yield SSEFormatter.format_heartbeat()
        await asyncio.sleep(30)  # Send heartbeat every 30 seconds


class StreamAccumulator:
    """Accumulate streaming response for non-streaming endpoints"""
    
    def __init__(self):
        self.content = ""
        self.metadata = {}
    
    async def accumulate_stream(
        self,
        stream_generator: AsyncGenerator[str, None]
    ) -> Dict[str, Any]:
        """
        Accumulate entire stream into a single response
        
        Args:
            stream_generator: SSE stream generator
            
        Returns:
            Complete response data
        """
        try:
            async for chunk in stream_generator:
                if chunk.startswith("data: "):
                    data_content = chunk[6:].strip()
                    
                    if data_content == "[DONE]":
                        break
                    
                    try:
                        chunk_data = json.loads(data_content)
                        
                        # Extract content from OpenAI format
                        if "choices" in chunk_data and chunk_data["choices"]:
                            choice = chunk_data["choices"][0]
                            if "delta" in choice and "content" in choice["delta"]:
                                self.content += choice["delta"]["content"]
                            
                            # Store metadata from final chunk
                            if choice.get("finish_reason"):
                                self.metadata["finish_reason"] = choice["finish_reason"]
                        
                        # Store other metadata
                        for key in ["id", "model", "usage"]:
                            if key in chunk_data:
                                self.metadata[key] = chunk_data[key]
                                
                    except json.JSONDecodeError:
                        continue
            
            return {
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.content
                    },
                    "finish_reason": self.metadata.get("finish_reason", "stop")
                }],
                "id": self.metadata.get("id"),
                "model": self.metadata.get("model"),
                "usage": self.metadata.get("usage", {})
            }
            
        except Exception as e:
            logger.error(f"Error accumulating stream: {e}")
            raise