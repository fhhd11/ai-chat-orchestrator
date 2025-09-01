"""Enhanced custom exceptions for the AI Chat Orchestrator"""

from typing import Optional, Dict, Any
from datetime import datetime


class ChatOrchestratorException(Exception):
    """Base exception class for all orchestrator errors with enhanced error tracking"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None
    ):
        self.message = message
        self.code = code or self.__class__.__name__.upper()
        self.details = details or {}
        self.status_code = status_code or 500
        self.retry_after = retry_after
        self.timestamp = datetime.now()
        
        # Add class name to details for debugging
        self.details["exception_type"] = self.__class__.__name__
        self.details["timestamp"] = self.timestamp.isoformat()
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "message": self.message,
            "code": self.code,
            "details": self.details
        }
        
        if self.retry_after:
            result["retry_after"] = self.retry_after
            
        return result


class AuthenticationError(ChatOrchestratorException):
    """Authentication and authorization errors"""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details, status_code=401)


class AuthorizationError(ChatOrchestratorException):
    """Authorization/permission errors"""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code, details, status_code=403)


class EdgeFunctionError(ChatOrchestratorException):
    """Errors when calling Supabase Edge Functions"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        super().__init__(message, code, details, status_code or 500)


class LiteLLMError(ChatOrchestratorException):
    """Errors from LiteLLM service"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        super().__init__(message, code, details, status_code or 500)


class InsufficientBalanceError(ChatOrchestratorException):
    """User has insufficient balance"""
    
    def __init__(self, message: str, available_balance: float, required_amount: Optional[float] = None):
        details = {
            "available_balance": available_balance,
            "required_amount": required_amount
        }
        super().__init__(message, "INSUFFICIENT_BALANCE", details, status_code=402)


class ConversationNotFoundError(ChatOrchestratorException):
    """Conversation not found or access denied"""
    
    def __init__(self, conversation_id: str, message: Optional[str] = None):
        msg = message or f"Conversation {conversation_id} not found or access denied"
        details = {"conversation_id": conversation_id}
        super().__init__(msg, "CONVERSATION_NOT_FOUND", details, status_code=404)


class MessageNotFoundError(ChatOrchestratorException):
    """Message not found or access denied"""
    
    def __init__(self, message_id: str, message: Optional[str] = None):
        msg = message or f"Message {message_id} not found or access denied"
        details = {"message_id": message_id}
        super().__init__(msg, "MESSAGE_NOT_FOUND", details, status_code=404)


class BranchNotFoundError(ChatOrchestratorException):
    """Branch not found or access denied"""
    
    def __init__(self, branch_id: str, conversation_id: Optional[str] = None):
        msg = f"Branch {branch_id} not found or access denied"
        details = {"branch_id": branch_id}
        if conversation_id:
            details["conversation_id"] = conversation_id
        super().__init__(msg, "BRANCH_NOT_FOUND", details, status_code=404)


class ValidationError(ChatOrchestratorException):
    """Request validation errors"""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None):
        details = {"field_errors": field_errors or {}}
        super().__init__(message, "VALIDATION_ERROR", details, status_code=400)


class ServiceUnavailableError(ChatOrchestratorException):
    """External service is unavailable"""
    
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(message, code, details, status_code=503, retry_after=retry_after)


class RateLimitError(ChatOrchestratorException):
    """Rate limit exceeded"""
    
    def __init__(
        self, 
        message: str, 
        retry_after: int,
        limit_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        limit: Optional[int] = None
    ):
        details = {
            "limit_type": limit_type,
            "current_usage": current_usage,
            "limit": limit
        }
        super().__init__(message, "RATE_LIMIT_EXCEEDED", details, status_code=429, retry_after=retry_after)


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""
    
    def __init__(self, message: Optional[str] = None):
        msg = message or "JWT token has expired"
        super().__init__(msg, "TOKEN_EXPIRED")


class InvalidTokenError(AuthenticationError):
    """JWT token is invalid"""
    
    def __init__(self, message: Optional[str] = None):
        msg = message or "JWT token is invalid"
        super().__init__(msg, "INVALID_TOKEN")


class ModelNotFoundError(ChatOrchestratorException):
    """Requested model not found or unavailable"""
    
    def __init__(self, model_id: str, available_models: Optional[list] = None):
        msg = f"Model '{model_id}' not found or unavailable"
        details = {
            "model_id": model_id,
            "available_models": available_models or []
        }
        super().__init__(msg, "MODEL_NOT_FOUND", details, status_code=404)


class ConfigurationError(ChatOrchestratorException):
    """Configuration or setup errors"""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, "CONFIGURATION_ERROR", details, status_code=500)


class CacheError(ChatOrchestratorException):
    """Cache-related errors"""
    
    def __init__(self, message: str, cache_key: Optional[str] = None, operation: Optional[str] = None):
        details = {
            "cache_key": cache_key,
            "operation": operation
        }
        super().__init__(message, "CACHE_ERROR", details, status_code=500)


class StreamingError(ChatOrchestratorException):
    """Streaming-related errors"""
    
    def __init__(self, message: str, stream_id: Optional[str] = None):
        details = {"stream_id": stream_id} if stream_id else {}
        super().__init__(message, "STREAMING_ERROR", details, status_code=500)


class BatchOperationError(ChatOrchestratorException):
    """Batch operation errors"""
    
    def __init__(
        self, 
        message: str, 
        failed_items: Optional[list] = None, 
        successful_items: Optional[list] = None
    ):
        details = {
            "failed_items": failed_items or [],
            "successful_items": successful_items or [],
            "total_failed": len(failed_items) if failed_items else 0,
            "total_successful": len(successful_items) if successful_items else 0
        }
        super().__init__(message, "BATCH_OPERATION_ERROR", details, status_code=400)


# Helper function to create HTTP exceptions from our custom exceptions
def create_http_exception(exc: ChatOrchestratorException):
    """Create FastAPI HTTPException from our custom exception"""
    from fastapi import HTTPException
    
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.to_dict(),
        headers=headers if headers else None
    )