"""
Legacy models module for backward compatibility.

This module imports all models from the new structured packages and provides
backward compatibility for existing code. New code should import directly
from the specific model packages.
"""

# Import all models from new structure for backward compatibility
from .models.chat import *
from .models.conversation import *
from .models.message import *
from .models.user import *
from .models.common import *
from .models.litellm import *

# Legacy aliases for backward compatibility
ConversationResponse = ConversationDetail
HealthResponse = SystemInfo

# Keep original legacy models that don't have direct equivalents
from pydantic import BaseModel
from typing import Optional, Dict, Any


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


class EdgeFunctionResponse(BaseModel):
    """Base Edge Function response model"""
    success: bool
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None