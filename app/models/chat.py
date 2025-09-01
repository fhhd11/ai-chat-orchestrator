"""Chat-related Pydantic models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Role(str, Enum):
    """Chat message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Chat message model"""
    role: Role = Field(..., description="Message role")
    content: str = Field(..., description="Message content", min_length=1)
    name: Optional[str] = Field(None, description="Optional message name")
    
    class Config:
        use_enum_values = True


class ChatCompletionRequest(BaseModel):
    """Chat completion request model"""
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    message: str = Field(..., description="User message content", min_length=1, max_length=32000)
    model: Optional[str] = Field(None, description="LLM model to use", max_length=100)
    temperature: Optional[float] = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(2000, gt=0, le=8192, description="Maximum tokens to generate")
    stream: bool = Field(True, description="Enable streaming response")
    parent_message_id: Optional[str] = Field(None, description="Parent message ID for branching")
    
    @validator('model')
    def validate_model(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class RegenerateRequest(BaseModel):
    """Regenerate response request model"""
    conversation_id: str = Field(..., description="Conversation ID", min_length=1)
    message_id: str = Field(..., description="Message ID to regenerate", min_length=1)
    model: Optional[str] = Field(None, description="LLM model to use", max_length=100)
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, le=8192, description="Maximum tokens to generate")
    
    @validator('model')
    def validate_model(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class ChatCompletionResponse(BaseModel):
    """Chat completion response model"""
    conversation_id: str = Field(..., description="Conversation ID")
    branch_id: str = Field(..., description="Branch ID")
    message_id: str = Field(..., description="Generated message ID")
    model: str = Field(..., description="Model used for generation")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")
    created_at: datetime = Field(..., description="Response creation time")


class StreamingChunk(BaseModel):
    """Streaming response chunk model"""
    id: str = Field(..., description="Chunk ID")
    object: str = Field("chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model name")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Optional[Dict[str, Any]] = Field(None, description="Token usage information")


class ChatContext(BaseModel):
    """Chat context model for building conversation history"""
    conversation_id: str = Field(..., description="Conversation ID")
    branch_id: Optional[str] = Field(None, description="Specific branch ID")
    messages: List[ChatMessage] = Field(..., description="Context messages")
    max_messages: int = Field(50, gt=0, le=200, description="Maximum messages to include")
    system_message: Optional[str] = Field(None, description="System message override")


class ChatSession(BaseModel):
    """Chat session information"""
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    conversation_id: Optional[str] = Field(None, description="Active conversation ID")
    model: Optional[str] = Field(None, description="Default model")
    temperature: float = Field(0.7, ge=0, le=2, description="Default temperature")
    max_tokens: int = Field(2000, gt=0, le=8192, description="Default max tokens")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")


class TokenUsage(BaseModel):
    """Token usage information"""
    prompt_tokens: int = Field(..., ge=0, description="Tokens in prompt")
    completion_tokens: int = Field(..., ge=0, description="Tokens in completion")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    cost_usd: Optional[float] = Field(None, ge=0, description="Estimated cost in USD")