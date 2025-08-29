"""
AI Chat Orchestrator - FastAPI Application

Main entry point for the AI Chat Orchestrator microservice that connects
Supabase Edge Functions with LiteLLM Proxy for streaming LLM chat completions.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from loguru import logger
import sys

from .config import settings
from .routers import health, chat, conversations
from .middleware import (
    add_request_id_middleware,
    logging_middleware,
    security_headers_middleware,
    error_handling_middleware,
    setup_cors_middleware,
    setup_metrics_middleware
)
from .dependencies import cleanup_dependencies


# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
    level=settings.log_level,
    colorize=True
)

# Add file logging in production
if not settings.debug:
    logger.add(
        "logs/app.log",
        rotation="100 MB",
        retention="30 days",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        compression="zip"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")
    
    # Create logs directory if needed
    if not settings.debug:
        os.makedirs("logs", exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await cleanup_dependencies()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="""
    AI Chat Orchestrator - A microservice that orchestrates streaming chat completions 
    between Supabase Edge Functions and LiteLLM Proxy.
    
    ## Features
    
    - 🔐 JWT authentication via Supabase
    - 🌊 Server-Sent Events (SSE) streaming
    - 💰 User balance verification
    - 🔄 Response regeneration with branching
    - 📊 Prometheus metrics
    - 🚀 High performance with async/await
    
    ## Authentication
    
    All endpoints (except /health, /ready, /live) require a valid Supabase JWT token
    in the Authorization header:
    
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    """,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Setup middleware (order matters!)
app.middleware("http")(error_handling_middleware)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(add_request_id_middleware)
app.middleware("http")(logging_middleware)

# Setup CORS middleware
setup_cors_middleware(app)

# Setup metrics middleware
setup_metrics_middleware(app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(conversations.router, tags=["Conversations"])


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs in debug mode"""
    if settings.debug:
        return RedirectResponse(url="/docs")
    else:
        return {
            "service": settings.app_name,
            "version": settings.version,
            "status": "running",
            "docs": "Documentation available in development mode only"
        }


@app.get("/info", tags=["System"])
async def info():
    """Get service information"""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "debug": settings.debug,
        "features": {
            "streaming": True,
            "authentication": True,
            "metrics": settings.enable_metrics,
            "regeneration": True
        },
        "endpoints": {
            "health": "/health",
            "chat": "/v1/chat/completions",
            "regenerate": "/v1/chat/regenerate",
            "conversations": "/v1/conversations/{conversation_id}",
            "metrics": "/metrics" if settings.enable_metrics else None
        }
    }


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return {
        "error": "Not Found",
        "message": f"The requested endpoint {request.url.path} was not found",
        "code": "NOT_FOUND"
    }


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    """Custom 405 handler"""
    return {
        "error": "Method Not Allowed",
        "message": f"The method {request.method} is not allowed for {request.url.path}",
        "code": "METHOD_NOT_ALLOWED"
    }


# Development mode warning
if settings.debug:
    logger.warning("⚠️  Application is running in DEBUG mode. Do not use in production!")


# Log startup information
logger.info("Application configured successfully")
logger.info(f"Supabase URL: {settings.supabase_url}")
logger.info(f"LiteLLM URL: {settings.litellm_url}")
logger.info(f"Edge Function URL: {settings.edge_function_url}")
logger.info(f"Max context messages: {settings.max_context_messages}")
logger.info(f"Stream timeout: {settings.stream_timeout}s")


if __name__ == "__main__":
    import uvicorn
    
    # This block only runs when the file is executed directly
    # In production, use: uvicorn app.main:app --host 0.0.0.0 --port 8000
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )