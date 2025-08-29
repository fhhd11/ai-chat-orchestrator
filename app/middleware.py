"""Middleware for the FastAPI application"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator

from .config import settings


async def add_request_id_middleware(request: Request, call_next: Callable) -> Response:
    """Add request ID to all requests for tracing"""
    request_id = str(uuid.uuid4())
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    # Add to logger context
    with logger.contextualize(request_id=request_id):
        # Call the next middleware/route handler
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """Log all requests with timing information"""
    start_time = time.time()
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # Log request
    logger.info(
        f"Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        request_id=request_id
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log response
    logger.info(
        f"Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        request_id=request_id
    )
    
    return response


def setup_cors_middleware(app):
    """Setup CORS middleware"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Mx-ReqToken",
            "Keep-Alive",
            "X-Requested-With",
            "If-Modified-Since",
        ],
        expose_headers=["X-Request-ID"],
    )


def setup_metrics_middleware(app):
    """Setup Prometheus metrics middleware"""
    if settings.enable_metrics:
        instrumentator = Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_group_untemplated=False,
            excluded_handlers=["/health", "/metrics"],
        )
        
        instrumentator.instrument(app)
        instrumentator.expose(app, endpoint="/metrics")


async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Don't add HSTS in development
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response


async def error_handling_middleware(request: Request, call_next: Callable) -> Response:
    """Global error handling middleware"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(
            f"Unhandled exception in request {request_id}",
            error=str(e),
            method=request.method,
            url=str(request.url),
            exc_info=True
        )
        
        # Return a generic error response
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "request_id": request_id,
                "code": "INTERNAL_ERROR"
            }
        )