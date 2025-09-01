"""Message-related Pydantic models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .chat import Role, TokenUsage


class MessageType(str, Enum):
    """Message type enumeration"""
    CHAT = "chat"
    SYSTEM = "system"
    FUNCTION = "function"
    TOOL = "tool"


class MessageStatus(str, Enum):
    """Message status enumeration"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageDetail(BaseModel):
    """Detailed message information"""
    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    branch_id: str = Field(..., description="Branch ID")
    parent_id: Optional[str] = Field(None, description="Parent message ID")
    
    # Content
    role: Role = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    type: MessageType = Field(MessageType.CHAT, description="Message type")
    status: MessageStatus = Field(MessageStatus.COMPLETED, description="Message status")
    
    # Metadata
    model: Optional[str] = Field(None, description="Model used (for assistant messages)")
    temperature: Optional[float] = Field(None, description="Temperature used")
    max_tokens: Optional[int] = Field(None, description="Max tokens setting")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    
    # Usage and cost
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage information")
    estimated_cost: Optional[float] = Field(None, ge=0, description="Estimated cost in USD")
    
    # Additional data
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    error_info: Optional[Dict[str, Any]] = Field(None, description="Error information if failed")
    
    # Children messages
    children: List[str] = Field(default_factory=list, description="Child message IDs")
    has_branches: bool = Field(False, description="Whether this message has branches")
    branch_count: int = Field(0, ge=0, description="Number of branches from this message")
    
    class Config:
        use_enum_values = True


class MessageListItem(BaseModel):
    """Message list item (for conversation display)"""
    id: str = Field(..., description="Message ID")
    role: Role = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    type: MessageType = Field(MessageType.CHAT, description="Message type")
    status: MessageStatus = Field(MessageStatus.COMPLETED, description="Message status")
    model: Optional[str] = Field(None, description="Model used (for assistant messages)")
    created_at: datetime = Field(..., description="Creation timestamp")
    parent_id: Optional[str] = Field(None, description="Parent message ID")
    children_count: int = Field(0, ge=0, description="Number of child messages")
    has_branches: bool = Field(False, description="Whether this message has branches")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage information")
    
    class Config:
        use_enum_values = True


class EditMessageRequest(BaseModel):
    """Edit message request"""
    content: str = Field(..., description="New message content", min_length=1, max_length=32000)
    create_branch: bool = Field(False, description="Create new branch for edit")
    branch_name: Optional[str] = Field(None, description="Name for new branch", max_length=100)
    
    @validator('branch_name')
    def validate_branch_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class RegenerateMessageRequest(BaseModel):
    """Regenerate message request"""
    model: Optional[str] = Field(None, description="Model to use for regeneration", max_length=100)
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, le=8192, description="Maximum tokens to generate")
    create_branch: bool = Field(True, description="Create new branch for regeneration")
    branch_name: Optional[str] = Field(None, description="Name for new branch", max_length=100)
    
    @validator('model')
    def validate_model(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v
    
    @validator('branch_name')
    def validate_branch_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class MessageSearchFilters(BaseModel):
    """Message search and filtering"""
    q: Optional[str] = Field(None, description="Search query in content", max_length=200)
    role: Optional[Role] = Field(None, description="Filter by message role")
    type: Optional[MessageType] = Field(None, description="Filter by message type")
    status: Optional[MessageStatus] = Field(None, description="Filter by message status")
    model: Optional[str] = Field(None, description="Filter by model used", max_length=100)
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    has_branches: Optional[bool] = Field(None, description="Filter messages with/without branches")
    min_tokens: Optional[int] = Field(None, ge=0, description="Minimum token count")
    max_tokens: Optional[int] = Field(None, ge=0, description="Maximum token count")
    
    class Config:
        use_enum_values = True


class MessageThread(BaseModel):
    """Message thread (conversation path)"""
    conversation_id: str = Field(..., description="Conversation ID")
    branch_id: str = Field(..., description="Branch ID")
    messages: List[MessageListItem] = Field(..., description="Messages in chronological order")
    total_tokens: int = Field(0, ge=0, description="Total tokens in thread")
    estimated_cost: float = Field(0.0, ge=0, description="Estimated thread cost")


class MessageStats(BaseModel):
    """Message statistics"""
    total_messages: int = Field(..., ge=0, description="Total message count")
    user_messages: int = Field(..., ge=0, description="User message count")
    assistant_messages: int = Field(..., ge=0, description="Assistant message count")
    system_messages: int = Field(..., ge=0, description="System message count")
    failed_messages: int = Field(..., ge=0, description="Failed message count")
    total_tokens: int = Field(..., ge=0, description="Total token usage")
    total_cost: float = Field(..., ge=0, description="Total estimated cost")
    models_used: Dict[str, int] = Field(..., description="Model usage counts")
    messages_by_day: Dict[str, int] = Field(..., description="Messages created by day")


class BatchMessageOperation(BaseModel):
    """Batch operation on messages"""
    message_ids: List[str] = Field(..., description="Message IDs", min_items=1, max_items=50)
    operation: str = Field(..., description="Operation to perform")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")