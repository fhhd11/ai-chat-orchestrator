"""LiteLLM models management router for model listing and information"""

from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from ..dependencies import get_current_user, get_litellm_service, get_cache_service
from ..models.litellm import LiteLLMModel
from ..models.common import SuccessResponse, ErrorResponse, PaginatedResponse
from ..models.user import UserProfile
from ..services.litellm_client import LiteLLMService
from ..services.cache_service import CacheService
from ..config import settings

router = APIRouter(prefix="/v1/models", tags=["Models"])


@router.get(
    "",
    response_model=SuccessResponse[List[LiteLLMModel]],
    summary="List available models",
    description="""
    Get list of all available LiteLLM models with filtering and sorting options.
    
    Returns model information including:
    - Model ID and display name
    - Provider information
    - Pricing and token limits
    - Capabilities and features
    - Current availability status
    """
)
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider (openai, anthropic, google, etc.)"),
    model_type: Optional[str] = Query(None, description="Filter by model type (chat, completion, embedding)"),
    supports_streaming: Optional[bool] = Query(None, description="Filter by streaming support"),
    supports_functions: Optional[bool] = Query(None, description="Filter by function calling support"),
    supports_vision: Optional[bool] = Query(None, description="Filter by vision/image support"),
    max_input_tokens: Optional[int] = Query(None, description="Filter by minimum input token limit"),
    max_output_tokens: Optional[int] = Query(None, description="Filter by minimum output token limit"),
    max_cost_per_1k_input: Optional[float] = Query(None, description="Filter by maximum cost per 1K input tokens"),
    available_only: bool = Query(True, description="Show only currently available models"),
    sort_by: Optional[str] = Query("display_name", description="Sort field (display_name, provider, cost_input, max_input_tokens)"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """List available LiteLLM models with filtering"""
    try:
        # Build cache key based on filters
        cache_key = f"models_list:{provider or 'all'}:{model_type or 'all'}:{supports_streaming}:{supports_functions}:{supports_vision}:{max_input_tokens}:{max_output_tokens}:{max_cost_per_1k_input}:{available_only}:{sort_by}:{sort_order}"
        
        # Try cache first
        if settings.redis_enabled:
            cached_result = await cache_service.get("models", cache_key)
            if cached_result:
                logger.info("Returning cached models list")
                return cached_result
        
        # Get models from service
        models = await litellm_service.get_models()
        
        # Apply filters
        filtered_models = []
        for model in models:
            # Provider filter
            if provider and model.provider.lower() != provider.lower():
                continue
            
            # Model type filter
            if model_type and model.model_type != model_type:
                continue
            
            # Feature filters
            if supports_streaming is not None and model.supports_streaming != supports_streaming:
                continue
            
            if supports_functions is not None and model.supports_functions != supports_functions:
                continue
            
            if supports_vision is not None and model.supports_vision != supports_vision:
                continue
            
            # Token limit filters
            if max_input_tokens and (not model.max_input_tokens or model.max_input_tokens < max_input_tokens):
                continue
            
            if max_output_tokens and (not model.max_output_tokens or model.max_output_tokens < max_output_tokens):
                continue
            
            # Cost filter
            if max_cost_per_1k_input and model.cost_per_1k_input and model.cost_per_1k_input > max_cost_per_1k_input:
                continue
            
            # Availability filter
            if available_only and not model.available:
                continue
            
            filtered_models.append(model)
        
        # Sort results
        reverse = sort_order == "desc"
        if sort_by == "provider":
            filtered_models.sort(key=lambda x: x.provider.lower(), reverse=reverse)
        elif sort_by == "cost_input":
            filtered_models.sort(key=lambda x: x.cost_per_1k_input or 0, reverse=reverse)
        elif sort_by == "max_input_tokens":
            filtered_models.sort(key=lambda x: x.max_input_tokens or 0, reverse=reverse)
        else:  # default to display_name
            filtered_models.sort(key=lambda x: x.display_name.lower(), reverse=reverse)
        
        response = {
            "success": True,
            "data": filtered_models,
            "metadata": {
                "total": len(filtered_models),
                "filters_applied": {
                    "provider": provider,
                    "model_type": model_type,
                    "supports_streaming": supports_streaming,
                    "supports_functions": supports_functions,
                    "supports_vision": supports_vision,
                    "max_input_tokens": max_input_tokens,
                    "max_output_tokens": max_output_tokens,
                    "max_cost_per_1k_input": max_cost_per_1k_input,
                    "available_only": available_only
                }
            }
        }
        
        # Cache result
        if settings.redis_enabled:
            await cache_service.set("models", cache_key, response, ttl=settings.cache_ttl_models)
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{model_id}",
    response_model=SuccessResponse[LiteLLMModel],
    summary="Get model details",
    description="Get detailed information about a specific model"
)
async def get_model(
    model_id: str = Path(..., description="Model ID"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get details of a specific model"""
    try:
        # Try cache first
        cache_key = f"model_detail:{model_id}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("models", cache_key)
            if cached_result:
                return cached_result
        
        # Get model from service
        model = await litellm_service.get_model_by_id(model_id)
        
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        
        response = {
            "success": True,
            "data": model
        }
        
        # Cache result
        if settings.redis_enabled:
            await cache_service.set("models", cache_key, response, ttl=settings.cache_ttl_models)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/providers",
    response_model=SuccessResponse[List[Dict[str, Any]]],
    summary="List model providers",
    description="Get list of all available model providers with their statistics"
)
async def list_providers(
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """List all model providers with statistics"""
    try:
        # Try cache first
        cache_key = "model_providers"
        if settings.redis_enabled:
            cached_result = await cache_service.get("models", cache_key)
            if cached_result:
                return cached_result
        
        # Get all models
        models = await litellm_service.get_models()
        
        # Group by provider
        providers_data = {}
        for model in models:
            provider = model.provider
            if provider not in providers_data:
                providers_data[provider] = {
                    "name": provider,
                    "display_name": provider.title(),
                    "total_models": 0,
                    "available_models": 0,
                    "model_types": set(),
                    "features": {
                        "streaming": 0,
                        "functions": 0,
                        "vision": 0
                    },
                    "price_range": {
                        "min_input_cost": None,
                        "max_input_cost": None,
                        "min_output_cost": None,
                        "max_output_cost": None
                    },
                    "models": []
                }
            
            provider_info = providers_data[provider]
            provider_info["total_models"] += 1
            
            if model.available:
                provider_info["available_models"] += 1
            
            if model.model_type:
                provider_info["model_types"].add(model.model_type)
            
            # Count features
            if model.supports_streaming:
                provider_info["features"]["streaming"] += 1
            if model.supports_functions:
                provider_info["features"]["functions"] += 1
            if model.supports_vision:
                provider_info["features"]["vision"] += 1
            
            # Update price ranges
            if model.cost_per_1k_input:
                if provider_info["price_range"]["min_input_cost"] is None:
                    provider_info["price_range"]["min_input_cost"] = model.cost_per_1k_input
                else:
                    provider_info["price_range"]["min_input_cost"] = min(
                        provider_info["price_range"]["min_input_cost"],
                        model.cost_per_1k_input
                    )
                
                if provider_info["price_range"]["max_input_cost"] is None:
                    provider_info["price_range"]["max_input_cost"] = model.cost_per_1k_input
                else:
                    provider_info["price_range"]["max_input_cost"] = max(
                        provider_info["price_range"]["max_input_cost"],
                        model.cost_per_1k_input
                    )
            
            if model.cost_per_1k_output:
                if provider_info["price_range"]["min_output_cost"] is None:
                    provider_info["price_range"]["min_output_cost"] = model.cost_per_1k_output
                else:
                    provider_info["price_range"]["min_output_cost"] = min(
                        provider_info["price_range"]["min_output_cost"],
                        model.cost_per_1k_output
                    )
                
                if provider_info["price_range"]["max_output_cost"] is None:
                    provider_info["price_range"]["max_output_cost"] = model.cost_per_1k_output
                else:
                    provider_info["price_range"]["max_output_cost"] = max(
                        provider_info["price_range"]["max_output_cost"],
                        model.cost_per_1k_output
                    )
            
            # Add basic model info
            provider_info["models"].append({
                "id": model.id,
                "display_name": model.display_name,
                "available": model.available,
                "model_type": model.model_type
            })
        
        # Convert model_types set to list
        providers_list = []
        for provider_info in providers_data.values():
            provider_info["model_types"] = list(provider_info["model_types"])
            providers_list.append(provider_info)
        
        # Sort by name
        providers_list.sort(key=lambda x: x["name"])
        
        response = {
            "success": True,
            "data": providers_list,
            "metadata": {
                "total_providers": len(providers_list),
                "total_models": sum(p["total_models"] for p in providers_list),
                "total_available": sum(p["available_models"] for p in providers_list)
            }
        }
        
        # Cache result
        if settings.redis_enabled:
            await cache_service.set("models", cache_key, response, ttl=settings.cache_ttl_models)
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/refresh",
    response_model=SuccessResponse[Dict[str, str]],
    summary="Refresh models cache",
    description="Force refresh of the models cache from LiteLLM"
)
async def refresh_models_cache(
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Refresh the models cache"""
    try:
        # Clear all model-related cache entries
        if settings.redis_enabled:
            await cache_service.delete_pattern("models", "models_list:*")
            await cache_service.delete_pattern("models", "model_detail:*")
            await cache_service.delete("models", "model_providers")
        
        # Force refresh models in LiteLLM service
        models = await litellm_service.get_models(force_refresh=True)
        
        logger.info(f"Models cache refreshed successfully. Found {len(models)} models.")
        
        return {
            "success": True,
            "data": {
                "message": "Models cache refreshed successfully",
                "models_count": str(len(models)),
                "timestamp": str(datetime.utcnow().isoformat())
            }
        }
        
    except Exception as e:
        logger.error(f"Error refreshing models cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/search",
    response_model=SuccessResponse[List[LiteLLMModel]],
    summary="Search models",
    description="Search models by name, description, or capabilities"
)
async def search_models(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Search models by query"""
    try:
        # Sanitize search query
        query = q.strip().lower()
        
        # Try cache first
        cache_key = f"models_search:{query}:{limit}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("models", cache_key)
            if cached_result:
                return cached_result
        
        # Get all models
        models = await litellm_service.get_models()
        
        # Search through models
        matching_models = []
        for model in models:
            # Search in various fields
            searchable_text = [
                model.id.lower(),
                model.display_name.lower(),
                model.provider.lower(),
                model.model_type.lower() if model.model_type else "",
                model.description.lower() if model.description else ""
            ]
            
            # Check if query matches any searchable field
            if any(query in text for text in searchable_text):
                matching_models.append(model)
            
            # Also search in capabilities
            capabilities = []
            if model.supports_streaming:
                capabilities.append("streaming")
            if model.supports_functions:
                capabilities.append("functions")
            if model.supports_vision:
                capabilities.append("vision")
            
            if any(query in cap for cap in capabilities):
                if model not in matching_models:
                    matching_models.append(model)
        
        # Limit results
        matching_models = matching_models[:limit]
        
        # Sort by relevance (exact matches first, then partial)
        def relevance_score(model):
            score = 0
            if query == model.id.lower():
                score += 100
            elif query in model.id.lower():
                score += 50
            if query == model.display_name.lower():
                score += 80
            elif query in model.display_name.lower():
                score += 40
            if query == model.provider.lower():
                score += 60
            elif query in model.provider.lower():
                score += 30
            return score
        
        matching_models.sort(key=relevance_score, reverse=True)
        
        response = {
            "success": True,
            "data": matching_models,
            "metadata": {
                "query": q,
                "results_count": len(matching_models),
                "total_searched": len(models)
            }
        }
        
        # Cache result for 5 minutes (searches change less frequently)
        if settings.redis_enabled:
            await cache_service.set("models", cache_key, response, ttl=300)
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching models with query '{q}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/compare",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Compare models",
    description="Compare multiple models side by side"
)
async def compare_models(
    model_ids: str = Query(..., description="Comma-separated list of model IDs to compare"),
    request: Request = None,
    current_user: UserProfile = Depends(get_current_user),
    litellm_service: LiteLLMService = Depends(get_litellm_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Compare multiple models"""
    try:
        # Parse model IDs
        ids = [id.strip() for id in model_ids.split(",") if id.strip()]
        
        if len(ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 model IDs required for comparison")
        
        if len(ids) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 models can be compared at once")
        
        # Try cache first
        cache_key = f"models_compare:{'_'.join(sorted(ids))}"
        if settings.redis_enabled:
            cached_result = await cache_service.get("models", cache_key)
            if cached_result:
                return cached_result
        
        # Get models
        models = []
        not_found = []
        
        for model_id in ids:
            model = await litellm_service.get_model_by_id(model_id)
            if model:
                models.append(model)
            else:
                not_found.append(model_id)
        
        if not_found:
            raise HTTPException(
                status_code=404,
                detail=f"Models not found: {', '.join(not_found)}"
            )
        
        # Create comparison matrix
        comparison = {
            "models": models,
            "comparison_matrix": {
                "basic_info": {
                    "providers": [m.provider for m in models],
                    "model_types": [m.model_type for m in models],
                    "availability": [m.available for m in models]
                },
                "capabilities": {
                    "streaming": [m.supports_streaming for m in models],
                    "functions": [m.supports_functions for m in models],
                    "vision": [m.supports_vision for m in models]
                },
                "limits": {
                    "max_input_tokens": [m.max_input_tokens for m in models],
                    "max_output_tokens": [m.max_output_tokens for m in models]
                },
                "pricing": {
                    "cost_per_1k_input": [m.cost_per_1k_input for m in models],
                    "cost_per_1k_output": [m.cost_per_1k_output for m in models]
                }
            },
            "summary": {
                "cheapest_input": None,
                "cheapest_output": None,
                "highest_input_limit": None,
                "highest_output_limit": None,
                "most_capable": None
            }
        }
        
        # Calculate summary statistics
        input_costs = [m.cost_per_1k_input for m in models if m.cost_per_1k_input is not None]
        if input_costs:
            min_input_cost = min(input_costs)
            comparison["summary"]["cheapest_input"] = next(
                m.id for m in models if m.cost_per_1k_input == min_input_cost
            )
        
        output_costs = [m.cost_per_1k_output for m in models if m.cost_per_1k_output is not None]
        if output_costs:
            min_output_cost = min(output_costs)
            comparison["summary"]["cheapest_output"] = next(
                m.id for m in models if m.cost_per_1k_output == min_output_cost
            )
        
        input_limits = [m.max_input_tokens for m in models if m.max_input_tokens is not None]
        if input_limits:
            max_input_limit = max(input_limits)
            comparison["summary"]["highest_input_limit"] = next(
                m.id for m in models if m.max_input_tokens == max_input_limit
            )
        
        output_limits = [m.max_output_tokens for m in models if m.max_output_tokens is not None]
        if output_limits:
            max_output_limit = max(output_limits)
            comparison["summary"]["highest_output_limit"] = next(
                m.id for m in models if m.max_output_tokens == max_output_limit
            )
        
        # Find most capable (supports most features)
        capability_scores = []
        for model in models:
            score = 0
            if model.supports_streaming:
                score += 1
            if model.supports_functions:
                score += 1
            if model.supports_vision:
                score += 1
            capability_scores.append((model.id, score))
        
        if capability_scores:
            most_capable = max(capability_scores, key=lambda x: x[1])
            comparison["summary"]["most_capable"] = most_capable[0]
        
        response = {
            "success": True,
            "data": comparison,
            "metadata": {
                "compared_models": len(models),
                "requested_ids": ids,
                "not_found": not_found
            }
        }
        
        # Cache result
        if settings.redis_enabled:
            await cache_service.set("models", cache_key, response, ttl=1800)  # 30 minutes
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing models {model_ids}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


