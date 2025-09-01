"""Enhanced LiteLLM service with streaming, models management, and health monitoring"""

import json
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Tuple, Optional
import httpx
from loguru import logger
from datetime import datetime, timedelta

from ..config import settings
from ..models.litellm import LiteLLMModel, ModelProvider, ModelStatus, ModelCapability, ModelLimits, ModelPricing, ModelPerformanceMetrics
from ..models.chat import TokenUsage
from ..utils.errors import LiteLLMError, ServiceUnavailableError, RateLimitError


class LiteLLMService:
    """
    Enhanced LiteLLM service with streaming, models management, health monitoring,
    and performance tracking capabilities.
    """
    
    def __init__(self):
        self.base_url = settings.litellm_url
        self.master_key = settings.litellm_master_key
        self.timeout = settings.litellm_timeout
        self.max_retries = settings.litellm_max_retries
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, read=self.timeout),
            limits=httpx.Limits(
                max_connections=settings.max_concurrent_requests,
                max_keepalive_connections=20
            )
        )
        
        # Models cache
        self._models_cache: Optional[List[LiteLLMModel]] = None
        self._models_cache_timestamp: Optional[datetime] = None
        self._models_cache_ttl = timedelta(seconds=settings.cache_ttl_models)
        
        # Performance tracking
        self._performance_metrics: Dict[str, ModelPerformanceMetrics] = {}
        
    @property
    def models_cache_expired(self) -> bool:
        """Check if models cache is expired"""
        if not self._models_cache_timestamp:
            return True
        return datetime.now() - self._models_cache_timestamp > self._models_cache_ttl
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def _parse_model_id(self, model_id: str) -> Tuple[ModelProvider, str]:
        """Parse model ID to extract provider and model name"""
        model_id_lower = model_id.lower()
        
        if model_id_lower.startswith(('gpt-', 'text-', 'davinci', 'curie', 'babbage', 'ada')):
            return ModelProvider.OPENAI, model_id
        elif model_id_lower.startswith(('claude-', 'anthropic')):
            return ModelProvider.ANTHROPIC, model_id
        elif model_id_lower.startswith(('gemini-', 'palm-', 'bison', 'gecko')):
            return ModelProvider.GOOGLE, model_id
        elif model_id_lower.startswith(('llama', 'meta-llama')):
            return ModelProvider.META, model_id
        elif model_id_lower.startswith(('mistral-', 'mixtral-')):
            return ModelProvider.MISTRAL, model_id
        elif model_id_lower.startswith(('command-', 'cohere')):
            return ModelProvider.COHERE, model_id
        elif model_id_lower.startswith(('pplx-', 'perplexity')):
            return ModelProvider.PERPLEXITY, model_id
        else:
            return ModelProvider.OTHER, model_id
    
    def _infer_capabilities(self, model_id: str, model_data: Dict[str, Any]) -> List[ModelCapability]:
        """Infer model capabilities from model ID and metadata"""
        capabilities = [ModelCapability.CHAT]  # Default capability
        
        model_id_lower = model_id.lower()
        
        # Check for specific capabilities based on model ID patterns
        if 'gpt-4' in model_id_lower and 'vision' in model_id_lower:
            capabilities.append(ModelCapability.IMAGE_ANALYSIS)
        
        if any(x in model_id_lower for x in ['code', 'codex', 'davinci-code']):
            capabilities.append(ModelCapability.CODE_GENERATION)
        
        if any(x in model_id_lower for x in ['reasoning', 'o1-', 'o3-']):
            capabilities.append(ModelCapability.REASONING)
        
        # Check metadata for function calling support
        if model_data.get('supports_function_calling'):
            capabilities.append(ModelCapability.FUNCTION_CALLING)
        
        return capabilities
    
    def _create_model_from_data(self, model_data: Dict[str, Any]) -> LiteLLMModel:
        """Create LiteLLMModel from raw LiteLLM API data"""
        model_id = model_data.get('id', '')
        provider, _ = self._parse_model_id(model_id)
        
        # Extract basic information
        name = model_data.get('object', model_id).replace('model', '').strip()
        if not name:
            name = model_id
        
        # Determine status
        status = ModelStatus.AVAILABLE
        if model_data.get('deprecated', False):
            status = ModelStatus.DEPRECATED
        
        # Infer capabilities
        capabilities = self._infer_capabilities(model_id, model_data)
        
        # Create limits based on known model parameters
        context_window = model_data.get('max_tokens', None)
        max_output_tokens = model_data.get('max_output_tokens', None)
        
        limits = ModelLimits(
            max_tokens=max_output_tokens,
            context_window=context_window,
            max_requests_per_minute=model_data.get('max_requests_per_minute'),
            max_tokens_per_minute=model_data.get('max_tokens_per_minute')
        )
        
        # Create pricing information if available
        pricing = None
        if 'pricing' in model_data:
            pricing_data = model_data['pricing']
            pricing = ModelPricing(
                input_cost_per_1k=pricing_data.get('input_cost_per_1k_tokens'),
                output_cost_per_1k=pricing_data.get('output_cost_per_1k_tokens'),
                input_cost_per_token=pricing_data.get('input_cost_per_token'),
                output_cost_per_token=pricing_data.get('output_cost_per_token')
            )
        
        # Extract metadata
        supports_streaming = model_data.get('supports_streaming', True)
        supports_functions = model_data.get('supports_function_calling', False)
        supports_vision = model_data.get('supports_vision', 'vision' in model_id.lower())
        
        return LiteLLMModel(
            id=model_id,
            name=name,
            provider=provider,
            status=status,
            capabilities=capabilities,
            supports_streaming=supports_streaming,
            supports_functions=supports_functions,
            supports_vision=supports_vision,
            limits=limits,
            pricing=pricing,
            description=model_data.get('description'),
            version=model_data.get('version'),
            tags=model_data.get('tags', []),
            metadata=model_data
        )
    
    async def get_models(self, user_key: Optional[str] = None, force_refresh: bool = False) -> List[LiteLLMModel]:
        """
        Get available models from LiteLLM with caching and rich metadata
        
        Args:
            user_key: User's LiteLLM API key (optional, uses master key if not provided)
            force_refresh: Force refresh of models cache
            
        Returns:
            List of available models with metadata
            
        Raises:
            LiteLLMError: If LiteLLM returns an error
            ServiceUnavailableError: If service is unavailable
        """
        # Check cache first
        if not force_refresh and not self.models_cache_expired and self._models_cache:
            logger.info("Returning cached models list")
            return self._models_cache
        
        url = f"{self.base_url}/models"
        headers = {}
        
        # Use provided user key or master key
        api_key = user_key or self.master_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            logger.info("Fetching models from LiteLLM")
            start_time = datetime.now()
            
            response = await self.client.get(url, headers=headers)
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            if response.status_code == 200:
                data = response.json()
                models_data = data.get("data", [])
                
                # Parse models with enhanced metadata
                models = []
                for model_data in models_data:
                    try:
                        model = self._create_model_from_data(model_data)
                        models.append(model)
                    except Exception as e:
                        logger.warning(f"Failed to parse model {model_data.get('id', 'unknown')}: {e}")
                        continue
                
                # Update cache
                self._models_cache = models
                self._models_cache_timestamp = datetime.now()
                
                logger.info(f"Successfully fetched {len(models)} models in {response_time:.2f}s")
                return models
                
            else:
                raise LiteLLMError(
                    message=f"Failed to get models: HTTP {response.status_code}",
                    code="GET_MODELS_ERROR",
                    details={"status_code": response.status_code}
                )
                
        except httpx.RequestError as e:
            logger.error(f"Request error getting models: {e}")
            raise ServiceUnavailableError(
                message=f"Failed to get models: {str(e)}",
                code="SERVICE_UNAVAILABLE",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Unexpected error getting models: {e}")
            raise LiteLLMError(
                message=f"Unexpected error: {str(e)}",
                code="UNEXPECTED_ERROR",
                details={"error": str(e)}
            )
    
    async def get_model_by_id(self, model_id: str, user_key: Optional[str] = None) -> Optional[LiteLLMModel]:
        """
        Get specific model by ID
        
        Args:
            model_id: Model ID to find
            user_key: User's API key
            
        Returns:
            Model information or None if not found
        """
        models = await self.get_models(user_key)
        return next((model for model in models if model.id == model_id), None)
    
    async def get_models_by_provider(self, provider: ModelProvider, user_key: Optional[str] = None) -> List[LiteLLMModel]:
        """
        Get models filtered by provider
        
        Args:
            provider: Model provider to filter by
            user_key: User's API key
            
        Returns:
            List of models from the specified provider
        """
        models = await self.get_models(user_key)
        return [model for model in models if model.provider == provider]
    
    async def get_models_by_capability(self, capability: ModelCapability, user_key: Optional[str] = None) -> List[LiteLLMModel]:
        """
        Get models filtered by capability
        
        Args:
            capability: Model capability to filter by
            user_key: User's API key
            
        Returns:
            List of models with the specified capability
        """
        models = await self.get_models(user_key)
        return [model for model in models if capability in model.capabilities]
    
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
    
    async def health_check(self) -> bool:
        """
        Check if LiteLLM service is healthy
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Use master key if available, otherwise skip auth
            headers = {}
            if self.master_key:
                headers["Authorization"] = f"Bearer {self.master_key}"
            
            response = await self.client.get(
                f"{self.base_url}/health",
                headers=headers,
                timeout=settings.health_check_timeout
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"LiteLLM health check failed: {e}")
            return False
    
    async def get_service_info(self) -> Dict[str, Any]:
        """
        Get LiteLLM service information and status
        
        Returns:
            Service information dictionary
        """
        try:
            start_time = datetime.now()
            is_healthy = await self.health_check()
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Get models count
            models_count = 0
            try:
                models = await self.get_models()
                models_count = len(models)
            except:
                pass
            
            return {
                "service": "LiteLLM",
                "url": self.base_url,
                "healthy": is_healthy,
                "response_time": response_time,
                "models_available": models_count,
                "features": {
                    "streaming": True,
                    "models_api": True,
                    "chat_completions": True
                }
            }
        except Exception as e:
            return {
                "service": "LiteLLM", 
                "url": self.base_url,
                "healthy": False,
                "error": str(e)
            }


# Legacy alias for backward compatibility  
LiteLLMClient = LiteLLMService