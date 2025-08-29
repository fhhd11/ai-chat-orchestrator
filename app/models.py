from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class Role(str, Enum):
    """Chat message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Chat message model"""
    role: Role
    content: str


class ChatCompletionRequest(BaseModel):
    """Chat completion request model"""
    conversation_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    temperature: Optional[float] = Field(0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)
    stream: bool = True
    parent_message_id: Optional[str] = None


class RegenerateRequest(BaseModel):
    """Regenerate response request model"""
    conversation_id: str
    message_id: str
    model: Optional[str] = None
    temperature: Optional[float] = None


class ConversationResponse(BaseModel):
    """Conversation response model"""
    conversation_id: str
    branch_id: str
    message_id: str


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    details: Optional[Dict[str, Any]] = None
    code: Optional[str] = None


class UserProfile(BaseModel):
    """User profile model from Supabase"""
    id: str
    litellm_key: str
    email: str
    spend: float
    max_budget: float
    available_balance: Optional[float] = None


class EdgeFunctionRequest(BaseModel):
    """Base Edge Function request model"""
    pass


class AddMessageRequest(EdgeFunctionRequest):
    """Add message to conversation request"""
    conversation_id: Optional[str] = None
    content: str
    role: str
    parent_id: Optional[str] = None


class BuildContextRequest(EdgeFunctionRequest):
    """Build context request"""
    conversation_id: str
    branch_id: Optional[str] = None
    max_messages: int = 50


class SaveResponseRequest(EdgeFunctionRequest):
    """Save response request"""
    conversation_id: str
    branch_id: str
    parent_id: str
    content: str
    model: str
    tokens_count: Optional[int] = None


class CreateBranchRequest(EdgeFunctionRequest):
    """Create branch request"""
    conversation_id: str
    from_message_id: str
    name: Optional[str] = None


class EdgeFunctionResponse(BaseModel):
    """Base Edge Function response model"""
    success: bool
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class LiteLLMRequest(BaseModel):
    """LiteLLM chat completion request"""
    model: str
    messages: List[Dict[str, str]]
    stream: bool = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2000
    user: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    services: Dict[str, str]