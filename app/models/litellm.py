"""LiteLLM-related Pydantic models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ModelProvider(str, Enum):
    """LLM model provider enumeration"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    META = "meta"
    MISTRAL = "mistral"
    COHERE = "cohere"
    PERPLEXITY = "perplexity"
    OTHER = "other"


class ModelCapability(str, Enum):
    """Model capability enumeration"""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    IMAGE_ANALYSIS = "image_analysis"
    FUNCTION_CALLING = "function_calling"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"


class ModelStatus(str, Enum):
    """Model availability status"""
    AVAILABLE = "available"
    DEPRECATED = "deprecated"
    UNAVAILABLE = "unavailable"
    BETA = "beta"


class ModelPricing(BaseModel):
    """Model pricing information"""
    input_cost_per_token: Optional[float] = Field(None, ge=0, description="Cost per input token in USD")
    output_cost_per_token: Optional[float] = Field(None, ge=0, description="Cost per output token in USD")
    input_cost_per_1k: Optional[float] = Field(None, ge=0, description="Cost per 1K input tokens in USD")
    output_cost_per_1k: Optional[float] = Field(None, ge=0, description="Cost per 1K output tokens in USD")
    currency: str = Field("USD", description="Currency for pricing")
    last_updated: Optional[datetime] = Field(None, description="Pricing last updated")


class ModelLimits(BaseModel):
    """Model limits and constraints"""
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens per request")
    context_window: Optional[int] = Field(None, gt=0, description="Context window size")
    max_requests_per_minute: Optional[int] = Field(None, gt=0, description="Rate limit - requests per minute")
    max_tokens_per_minute: Optional[int] = Field(None, gt=0, description="Rate limit - tokens per minute")
    max_concurrent_requests: Optional[int] = Field(None, gt=0, description="Maximum concurrent requests")


class LiteLLMModel(BaseModel):
    """LiteLLM model information"""
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model display name")
    provider: ModelProvider = Field(..., description="Model provider")
    status: ModelStatus = Field(ModelStatus.AVAILABLE, description="Model status")
    
    # Capabilities
    capabilities: List[ModelCapability] = Field(..., description="Model capabilities")
    supports_streaming: bool = Field(True, description="Supports streaming responses")
    supports_functions: bool = Field(False, description="Supports function calling")
    supports_vision: bool = Field(False, description="Supports image input")
    
    # Technical details
    limits: ModelLimits = Field(..., description="Model limits and constraints")
    pricing: Optional[ModelPricing] = Field(None, description="Pricing information")
    
    # Metadata
    description: Optional[str] = Field(None, description="Model description")
    documentation_url: Optional[str] = Field(None, description="Documentation URL")
    release_date: Optional[datetime] = Field(None, description="Model release date")
    version: Optional[str] = Field(None, description="Model version")
    
    # Performance metrics
    average_response_time: Optional[float] = Field(None, ge=0, description="Average response time in seconds")
    quality_score: Optional[float] = Field(None, ge=0, le=10, description="Quality score (0-10)")
    popularity_rank: Optional[int] = Field(None, ge=1, description="Popularity ranking")
    
    # Additional metadata
    tags: List[str] = Field(default_factory=list, description="Model tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    class Config:
        use_enum_values = True


class ModelGroup(BaseModel):
    """Group of related models"""
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    provider: ModelProvider = Field(..., description="Provider")
    models: List[LiteLLMModel] = Field(..., description="Models in group")
    default_model: Optional[str] = Field(None, description="Default model ID")
    
    class Config:
        use_enum_values = True


class ModelSearchFilters(BaseModel):
    """Model search and filtering parameters"""
    provider: Optional[ModelProvider] = Field(None, description="Filter by provider")
    capability: Optional[ModelCapability] = Field(None, description="Filter by capability")
    status: Optional[ModelStatus] = Field(None, description="Filter by status")
    supports_streaming: Optional[bool] = Field(None, description="Filter by streaming support")
    supports_functions: Optional[bool] = Field(None, description="Filter by function calling")
    supports_vision: Optional[bool] = Field(None, description="Filter by vision capabilities")
    max_cost_per_1k: Optional[float] = Field(None, ge=0, description="Maximum cost per 1K tokens")
    min_context_window: Optional[int] = Field(None, gt=0, description="Minimum context window size")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    
    class Config:
        use_enum_values = True


class LiteLLMRequest(BaseModel):
    """LiteLLM chat completion request"""
    model: str = Field(..., description="Model ID", min_length=1)
    messages: List[Dict[str, str]] = Field(..., description="Conversation messages", min_items=1)
    stream: bool = Field(True, description="Enable streaming")
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(2000, gt=0, le=8192, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(None, ge=0, le=1, description="Top-p sampling")
    frequency_penalty: Optional[float] = Field(None, ge=-2, le=2, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, ge=-2, le=2, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    user: str = Field(..., description="User ID for tracking")
    
    # Additional parameters
    functions: Optional[List[Dict[str, Any]]] = Field(None, description="Available functions")
    function_call: Optional[str] = Field(None, description="Function call mode")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Available tools")
    tool_choice: Optional[str] = Field(None, description="Tool choice mode")
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError("Messages cannot be empty")
        return v


class ModelPerformanceMetrics(BaseModel):
    """Model performance metrics"""
    model_id: str = Field(..., description="Model ID")
    
    # Response metrics
    average_response_time: float = Field(..., ge=0, description="Average response time in seconds")
    median_response_time: float = Field(..., ge=0, description="Median response time in seconds")
    p95_response_time: float = Field(..., ge=0, description="95th percentile response time")
    p99_response_time: float = Field(..., ge=0, description="99th percentile response time")
    
    # Quality metrics
    success_rate: float = Field(..., ge=0, le=1, description="Request success rate")
    error_rate: float = Field(..., ge=0, le=1, description="Request error rate")
    timeout_rate: float = Field(..., ge=0, le=1, description="Request timeout rate")
    
    # Usage metrics
    total_requests: int = Field(..., ge=0, description="Total requests")
    total_tokens: int = Field(..., ge=0, description="Total tokens processed")
    average_tokens_per_request: float = Field(..., ge=0, description="Average tokens per request")
    
    # Cost metrics
    total_cost: float = Field(..., ge=0, description="Total cost incurred")
    average_cost_per_request: float = Field(..., ge=0, description="Average cost per request")
    
    # Time period
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")
    last_updated: datetime = Field(..., description="Last update timestamp")


class ModelComparison(BaseModel):
    """Comparison between multiple models"""
    models: List[str] = Field(..., description="Model IDs being compared", min_items=2)
    comparison_type: str = Field(..., description="Type of comparison")
    
    # Comparison results
    performance: Dict[str, ModelPerformanceMetrics] = Field(..., description="Performance metrics by model")
    recommendations: List[str] = Field(..., description="Recommendations based on comparison")
    best_for_cost: Optional[str] = Field(None, description="Best model for cost efficiency")
    best_for_speed: Optional[str] = Field(None, description="Best model for response speed")
    best_for_quality: Optional[str] = Field(None, description="Best model for response quality")
    
    # Metadata
    generated_at: datetime = Field(..., description="Comparison generation timestamp")
    criteria: Dict[str, Any] = Field(..., description="Comparison criteria used")