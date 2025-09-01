"""Utility modules for the AI Chat Orchestrator"""

from .errors import *
from .streaming import *
from .validators import *
from .logging import *
from .metrics import *

__all__ = [
    # Error handling
    "ChatOrchestratorException",
    "AuthenticationError", 
    "AuthorizationError",
    "EdgeFunctionError",
    "LiteLLMError",
    "ValidationError",
    "ServiceUnavailableError",
    "RateLimitError",
    "ConversationNotFoundError",
    "MessageNotFoundError",
    "BranchNotFoundError",
    "ModelNotFoundError",
    "ConfigurationError",
    "CacheError",
    "StreamingError",
    "BatchOperationError",
    "create_http_exception",
    
    # Streaming utilities
    "stream_response",
    "SSEHandler",
    
    # Validation utilities  
    "ValidationUtils",
    "PaginationValidator",
    "validate_uuid_field",
    "validate_email_field",
    "validate_model_field",
    "validate_temperature",
    "validate_max_tokens",
    "validate_search_query",
    "validate_conversation_title",
    "validate_message_content",
    
    # Logging utilities
    "StructuredLogger",
    "RequestLogger", 
    "ServiceLogger",
    "BusinessLogger",
    "SecurityLogger",
    "generate_request_id",
    "setup_structured_logging",
    "slog",
    "request_logger",
    "service_logger", 
    "business_logger",
    "security_logger",
    
    # Metrics utilities
    "MetricsCollector",
    "metrics",
    "record_request",
    "record_chat",
    "record_error"
]