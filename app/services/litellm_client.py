"""LiteLLM streaming client"""

import json
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Tuple
import httpx
from loguru import logger

from ..config import Settings
from ..models import LiteLLMRequest
from ..utils.errors import LiteLLMError, ServiceUnavailableError, RateLimitError


class LiteLLMClient:
    """Client for streaming chat completions from LiteLLM"""
    
    def __init__(self, settings: Settings):
        self.base_url = settings.litellm_url
        self.master_key = settings.litellm_master_key
        self.timeout = settings.stream_timeout
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, read=self.timeout),
            limits=httpx.Limits(max_connections=50)
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        user_key: str,
        user_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Stream chat completion from LiteLLM
        
        Args:
            messages: Conversation messages
            model: Model name
            user_key: User's LiteLLM API key
            user_id: User ID for tracking
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Tuple[chunk_data, full_response]: SSE chunk and accumulated response
            
        Raises:
            LiteLLMError: If LiteLLM returns an error
            ServiceUnavailableError: If service is unavailable
            RateLimitError: If rate limit is exceeded
        """
        url = f"{self.base_url}/chat/completions"
        
        request_data = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "user": user_id,
            **kwargs
        }
        
        headers = {
            "Authorization": f"Bearer {user_key}",
            "Content-Type": "application/json"
        }
        
        full_response = ""
        tokens_count = 0
        
        try:
            logger.info(f"Starting LiteLLM stream for model {model}, user {user_id}")
            
            async with self.client.stream(
                'POST',
                url,
                json=request_data,
                headers=headers
            ) as response:
                
                if response.status_code == 429:
                    error_data = await response.aread()
                    try:
                        error_json = json.loads(error_data.decode())
                        error_msg = error_json.get("error", {}).get("message", "Rate limit exceeded")
                    except:
                        error_msg = "Rate limit exceeded"
                    
                    raise RateLimitError(
                        message=error_msg,
                        code="RATE_LIMIT_EXCEEDED",
                        details={"model": model, "user_id": user_id}
                    )
                
                elif response.status_code == 401:
                    raise LiteLLMError(
                        message="Invalid API key",
                        code="INVALID_API_KEY",
                        details={"model": model, "user_id": user_id}
                    )
                
                elif response.status_code != 200:
                    error_data = await response.aread()
                    try:
                        error_json = json.loads(error_data.decode())
                        error_msg = error_json.get("error", {}).get("message", f"HTTP {response.status_code}")
                    except:
                        error_msg = f"HTTP {response.status_code}"
                    
                    raise LiteLLMError(
                        message=f"LiteLLM error: {error_msg}",
                        code="LITELLM_ERROR",
                        details={
                            "model": model, 
                            "user_id": user_id, 
                            "status_code": response.status_code
                        }
                    )
                
                # Process SSE stream
                async for line in response.aiter_lines():
                    if not line:
                        continue
                        
                    if line.startswith("data: "):
                        data_content = line[6:]  # Remove "data: " prefix
                        
                        # Handle end of stream
                        if data_content == "[DONE]":
                            logger.info(f"LiteLLM stream completed for user {user_id}, tokens: {tokens_count}")
                            yield f"data: [DONE]\n\n", full_response
                            break
                        
                        try:
                            # Parse JSON chunk
                            chunk_data = json.loads(data_content)
                            
                            # Extract content from delta
                            if "choices" in chunk_data and chunk_data["choices"]:
                                choice = chunk_data["choices"][0]
                                if "delta" in choice and "content" in choice["delta"]:
                                    content = choice["delta"]["content"]
                                    full_response += content
                                
                                # Track usage if available
                                if choice.get("finish_reason") == "stop" and "usage" in chunk_data:
                                    tokens_count = chunk_data["usage"].get("total_tokens", 0)
                            
                            # Yield formatted SSE chunk
                            yield f"data: {data_content}\n\n", full_response
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse LiteLLM chunk: {e}, content: {data_content}")
                            continue
                    
                    # Send heartbeat periodically to keep connection alive
                    await asyncio.sleep(0.01)
                
        except httpx.TimeoutException:
            logger.error(f"LiteLLM request timeout for user {user_id}")
            raise ServiceUnavailableError(
                message="Request timeout",
                code="TIMEOUT",
                details={"model": model, "user_id": user_id}
            )
            
        except httpx.RequestError as e:
            logger.error(f"LiteLLM request error for user {user_id}: {e}")
            raise ServiceUnavailableError(
                message=f"Service unavailable: {str(e)}",
                code="SERVICE_UNAVAILABLE",
                details={"model": model, "user_id": user_id, "error": str(e)}
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in LiteLLM stream for user {user_id}: {e}")
            raise LiteLLMError(
                message=f"Unexpected error: {str(e)}",
                code="UNEXPECTED_ERROR",
                details={"model": model, "user_id": user_id, "error": str(e)}
            )
    
    async def get_models(self, user_key: str) -> List[Dict[str, Any]]:
        """Get available models from LiteLLM"""
        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {user_key}"}
        
        try:
            response = await self.client.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json().get("data", [])
            else:
                raise LiteLLMError(
                    message=f"Failed to get models: {response.status_code}",
                    code="GET_MODELS_ERROR",
                    details={"status_code": response.status_code}
                )
                
        except httpx.RequestError as e:
            raise ServiceUnavailableError(
                message=f"Failed to get models: {str(e)}",
                code="SERVICE_UNAVAILABLE",
                details={"error": str(e)}
            )
    
    async def health_check(self) -> bool:
        """Check if LiteLLM service is healthy"""
        try:
            # Use master key if available, otherwise skip auth
            headers = {}
            if self.master_key:
                headers["Authorization"] = f"Bearer {self.master_key}"
            
            response = await self.client.get(
                f"{self.base_url}/health",
                headers=headers,
                timeout=5.0
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"LiteLLM health check failed: {e}")
            return False