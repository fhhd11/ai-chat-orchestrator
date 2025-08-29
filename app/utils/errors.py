"""Custom exceptions for the AI Chat Orchestrator"""


class ChatOrchestratorException(Exception):
    """Base exception class for all orchestrator errors"""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(ChatOrchestratorException):
    """Authentication and authorization errors"""
    pass


class EdgeFunctionError(ChatOrchestratorException):
    """Errors when calling Supabase Edge Functions"""
    pass


class LiteLLMError(ChatOrchestratorException):
    """Errors from LiteLLM service"""
    pass


class InsufficientBalanceError(ChatOrchestratorException):
    """User has insufficient balance"""
    pass


class ConversationNotFoundError(ChatOrchestratorException):
    """Conversation not found or access denied"""
    pass


class ValidationError(ChatOrchestratorException):
    """Request validation errors"""
    pass


class ServiceUnavailableError(ChatOrchestratorException):
    """External service is unavailable"""
    pass


class RateLimitError(ChatOrchestratorException):
    """Rate limit exceeded"""
    pass


class TokenExpiredError(AuthenticationError):
    """JWT token has expired"""
    pass


class InvalidTokenError(AuthenticationError):
    """JWT token is invalid"""
    pass