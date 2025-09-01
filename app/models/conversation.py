"""Conversation and branch-related Pydantic models"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ConversationStatus(str, Enum):
    """Conversation status enumeration"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class BranchStatus(str, Enum):
    """Branch status enumeration"""
    ACTIVE = "active"
    MERGED = "merged"
    ABANDONED = "abandoned"


class ConversationListItem(BaseModel):
    """Conversation list item (for paginated lists)"""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    model: Optional[str] = Field(None, description="Primary model used")
    status: ConversationStatus = Field(ConversationStatus.ACTIVE, description="Conversation status")
    message_count: int = Field(0, ge=0, description="Total message count")
    branch_count: int = Field(1, ge=1, description="Total branch count")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    preview: Optional[str] = Field(None, description="First user message preview", max_length=200)
    
    class Config:
        use_enum_values = True


class BranchInfo(BaseModel):
    """Branch information"""
    id: str = Field(..., description="Branch ID")
    name: Optional[str] = Field(None, description="Branch name")
    status: BranchStatus = Field(BranchStatus.ACTIVE, description="Branch status")
    is_main: bool = Field(False, description="Whether this is the main branch")
    is_active: bool = Field(False, description="Whether this is the currently active branch")
    message_count: int = Field(0, ge=0, description="Message count in this branch")
    created_at: datetime = Field(..., description="Branch creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    parent_message_id: Optional[str] = Field(None, description="Parent message ID")
    created_from_message: Optional[str] = Field(None, description="Message this branch was created from")
    
    class Config:
        use_enum_values = True


class ConversationDetail(BaseModel):
    """Detailed conversation information"""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    model: Optional[str] = Field(None, description="Primary model used")
    status: ConversationStatus = Field(ConversationStatus.ACTIVE, description="Conversation status")
    user_id: str = Field(..., description="Owner user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    
    # Branch information
    active_branch_id: str = Field(..., description="Currently active branch ID")
    branches: List[BranchInfo] = Field(..., description="All conversation branches")
    
    # Statistics
    total_messages: int = Field(0, ge=0, description="Total message count across all branches")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    estimated_cost: float = Field(0.0, ge=0, description="Estimated total cost in USD")
    
    class Config:
        use_enum_values = True


class CreateConversationRequest(BaseModel):
    """Create new conversation request"""
    title: Optional[str] = Field(None, description="Conversation title", max_length=200)
    model: Optional[str] = Field(None, description="Default model", max_length=100)
    system_message: Optional[str] = Field(None, description="System message", max_length=2000)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class UpdateConversationRequest(BaseModel):
    """Update conversation request"""
    title: Optional[str] = Field(None, description="New conversation title", max_length=200)
    model: Optional[str] = Field(None, description="New default model", max_length=100)
    status: Optional[ConversationStatus] = Field(None, description="New conversation status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    
    class Config:
        use_enum_values = True
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class CreateBranchRequest(BaseModel):
    """Create branch request"""
    from_message_id: str = Field(..., description="Message ID to branch from", min_length=1)
    name: Optional[str] = Field(None, description="Branch name", max_length=100)
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v


class SwitchBranchRequest(BaseModel):
    """Switch active branch request"""
    branch_id: str = Field(..., description="Branch ID to switch to", min_length=1)


class ConversationSearchFilters(BaseModel):
    """Conversation search and filtering"""
    q: Optional[str] = Field(None, description="Search query", max_length=200)
    model: Optional[str] = Field(None, description="Filter by model", max_length=100)
    status: Optional[ConversationStatus] = Field(None, description="Filter by status")
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    has_branches: Optional[bool] = Field(None, description="Filter conversations with/without branches")
    min_messages: Optional[int] = Field(None, ge=0, description="Minimum message count")
    max_messages: Optional[int] = Field(None, ge=0, description="Maximum message count")
    
    class Config:
        use_enum_values = True


class ConversationStats(BaseModel):
    """Conversation statistics"""
    total_conversations: int = Field(..., ge=0, description="Total conversation count")
    active_conversations: int = Field(..., ge=0, description="Active conversation count")
    archived_conversations: int = Field(..., ge=0, description="Archived conversation count")
    total_messages: int = Field(..., ge=0, description="Total message count")
    total_tokens: int = Field(..., ge=0, description="Total token usage")
    total_cost: float = Field(..., ge=0, description="Total estimated cost")
    models_used: Dict[str, int] = Field(..., description="Model usage counts")
    conversations_by_month: Dict[str, int] = Field(..., description="Conversations created by month")


class BatchConversationOperation(BaseModel):
    """Batch operation on conversations"""
    conversation_ids: List[str] = Field(..., description="Conversation IDs", min_items=1, max_items=50)
    operation: str = Field(..., description="Operation to perform")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation parameters")


class ConversationExportRequest(BaseModel):
    """Conversation export request"""
    conversation_ids: List[str] = Field(..., description="Conversation IDs to export", min_items=1, max_items=20)
    format: str = Field("json", description="Export format")
    include_metadata: bool = Field(True, description="Include metadata in export")
    include_branches: bool = Field(True, description="Include all branches")
    compress: bool = Field(False, description="Compress export file")