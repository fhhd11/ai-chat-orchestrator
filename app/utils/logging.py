"""Enhanced logging utilities with structured logging and request tracing"""

import json
import uuid
from typing import Optional, Dict, Any, Union
from datetime import datetime
from contextvars import ContextVar
from loguru import logger

from ..config import settings

# Context variables for request tracing
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredLogger:
    """Structured logger with context awareness"""
    
    @staticmethod
    def get_request_id() -> Optional[str]:
        """Get current request ID from context"""
        return request_id_ctx.get()
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get current user ID from context"""
        return user_id_ctx.get()
    
    @staticmethod
    def set_request_context(request_id: str, user_id: Optional[str] = None):
        """Set request context for logging"""
        request_id_ctx.set(request_id)
        if user_id:
            user_id_ctx.set(user_id)
    
    @staticmethod
    def clear_request_context():
        """Clear request context"""
        request_id_ctx.set(None)
        user_id_ctx.set(None)
    
    @staticmethod
    def _add_context(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add request context to log data"""
        context = {
            "request_id": request_id_ctx.get(),
            "user_id": user_id_ctx.get(),
            "timestamp": datetime.now().isoformat(),
            "service": settings.app_name,
            "version": settings.version,
            "environment": settings.environment
        }
        
        # Remove None values
        context = {k: v for k, v in context.items() if v is not None}
        
        if extra:
            context.update(extra)
        
        return context
    
    @staticmethod
    def info(message: str, **kwargs):
        """Log info message with context"""
        extra = StructuredLogger._add_context(kwargs)
        logger.bind(**extra).info(message)
    
    @staticmethod
    def debug(message: str, **kwargs):
        """Log debug message with context"""
        extra = StructuredLogger._add_context(kwargs)
        logger.bind(**extra).debug(message)
    
    @staticmethod
    def warning(message: str, **kwargs):
        """Log warning message with context"""
        extra = StructuredLogger._add_context(kwargs)
        logger.bind(**extra).warning(message)
    
    @staticmethod
    def error(message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with context"""
        extra = StructuredLogger._add_context(kwargs)
        
        if error:
            extra.update({
                "error_type": type(error).__name__,
                "error_message": str(error)
            })
        
        logger.bind(**extra).error(message)
    
    @staticmethod
    def critical(message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message with context"""
        extra = StructuredLogger._add_context(kwargs)
        
        if error:
            extra.update({
                "error_type": type(error).__name__,
                "error_message": str(error)
            })
        
        logger.bind(**extra).critical(message)


class RequestLogger:
    """Logger for HTTP requests and responses"""
    
    @staticmethod
    def log_request(
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body_size: Optional[int] = None,
        user_id: Optional[str] = None
    ):
        """Log HTTP request"""
        log_data = {
            "event": "http_request",
            "method": method,
            "url": url,
            "user_id": user_id,
            "body_size": body_size
        }
        
        if query_params:
            log_data["query_params"] = query_params
        
        # Log selected headers (avoid logging sensitive data)
        if headers:
            safe_headers = {
                k: v for k, v in headers.items() 
                if k.lower() not in ['authorization', 'cookie', 'x-api-key']
            }
            if safe_headers:
                log_data["headers"] = safe_headers
        
        StructuredLogger.info("HTTP request received", **log_data)
    
    @staticmethod
    def log_response(
        status_code: int,
        response_time: float,
        response_size: Optional[int] = None,
        cache_hit: bool = False,
        error: Optional[str] = None
    ):
        """Log HTTP response"""
        log_data = {
            "event": "http_response",
            "status_code": status_code,
            "response_time": response_time,
            "response_size": response_size,
            "cache_hit": cache_hit
        }
        
        if error:
            log_data["error"] = error
        
        if status_code >= 400:
            StructuredLogger.error("HTTP request failed", **log_data)
        else:
            StructuredLogger.info("HTTP request completed", **log_data)


class ServiceLogger:
    """Logger for service interactions"""
    
    @staticmethod
    def log_service_call(
        service: str,
        operation: str,
        endpoint: Optional[str] = None,
        duration: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs
    ):
        """Log service call (Edge Functions, LiteLLM, etc.)"""
        log_data = {
            "event": "service_call",
            "service": service,
            "operation": operation,
            "endpoint": endpoint,
            "duration": duration,
            "success": success
        }
        
        if error:
            log_data["error"] = error
        
        log_data.update(kwargs)
        
        if success:
            StructuredLogger.info(f"Service call to {service} completed", **log_data)
        else:
            StructuredLogger.error(f"Service call to {service} failed", **log_data)
    
    @staticmethod
    def log_cache_operation(
        operation: str,
        key: str,
        namespace: str,
        hit: Optional[bool] = None,
        ttl: Optional[int] = None,
        size: Optional[int] = None,
        error: Optional[str] = None
    ):
        """Log cache operations"""
        log_data = {
            "event": "cache_operation",
            "operation": operation,
            "cache_key": key,
            "namespace": namespace,
            "hit": hit,
            "ttl": ttl,
            "size": size
        }
        
        if error:
            log_data["error"] = error
            StructuredLogger.error(f"Cache {operation} failed", **log_data)
        else:
            StructuredLogger.debug(f"Cache {operation}", **log_data)


class BusinessLogger:
    """Logger for business events"""
    
    @staticmethod
    def log_conversation_event(
        event: str,
        conversation_id: str,
        user_id: str,
        model: Optional[str] = None,
        message_count: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        **kwargs
    ):
        """Log conversation-related events"""
        log_data = {
            "event": "conversation_event",
            "conversation_event": event,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "model": model,
            "message_count": message_count,
            "tokens_used": tokens_used,
            "cost": cost
        }
        
        log_data.update(kwargs)
        
        StructuredLogger.info(f"Conversation {event}", **log_data)
    
    @staticmethod
    def log_user_event(
        event: str,
        user_id: str,
        balance_before: Optional[float] = None,
        balance_after: Optional[float] = None,
        amount: Optional[float] = None,
        **kwargs
    ):
        """Log user-related events"""
        log_data = {
            "event": "user_event",
            "user_event": event,
            "user_id": user_id,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "amount": amount
        }
        
        log_data.update(kwargs)
        
        StructuredLogger.info(f"User {event}", **log_data)


class SecurityLogger:
    """Logger for security events"""
    
    @staticmethod
    def log_auth_event(
        event: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        reason: Optional[str] = None
    ):
        """Log authentication events"""
        log_data = {
            "event": "auth_event",
            "auth_event": event,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "reason": reason
        }
        
        if success:
            StructuredLogger.info(f"Authentication {event}", **log_data)
        else:
            StructuredLogger.warning(f"Authentication {event} failed", **log_data)
    
    @staticmethod
    def log_security_event(
        event: str,
        severity: str = "medium",
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security events"""
        log_data = {
            "event": "security_event",
            "security_event": event,
            "severity": severity,
            "user_id": user_id,
            "ip_address": ip_address
        }
        
        if details:
            log_data["details"] = details
        
        if severity in ["high", "critical"]:
            StructuredLogger.critical(f"Security event: {event}", **log_data)
        else:
            StructuredLogger.warning(f"Security event: {event}", **log_data)


def generate_request_id() -> str:
    """Generate unique request ID"""
    return str(uuid.uuid4())


def setup_structured_logging():
    """Setup structured logging configuration"""
    if not settings.structured_logging:
        return
    
    # Remove default logger
    logger.remove()
    
    # Add structured logger
    log_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {extra[request_id]} | {message}"
    
    logger.add(
        sink=logger._core.handlers[0]._sink if logger._core.handlers else None,
        format=log_format,
        level=settings.log_level,
        serialize=True if settings.environment == "production" else False
    )


# Global instances for easy access
slog = StructuredLogger()
request_logger = RequestLogger()
service_logger = ServiceLogger()
business_logger = BusinessLogger()
security_logger = SecurityLogger()