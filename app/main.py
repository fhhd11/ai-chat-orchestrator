"""
AI Chat Orchestrator - FastAPI Application

Main entry point for the AI Chat Orchestrator microservice that connects
Supabase Edge Functions with LiteLLM Proxy for streaming LLM chat completions.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.openapi.utils import get_openapi
from loguru import logger
import sys

from .config import settings
from .routers import health, chat, conversations, branches, messages, models, users
from .middleware import (
    add_request_id_middleware,
    logging_middleware,
    security_headers_middleware,
    error_handling_middleware,
    setup_cors_middleware,
    setup_metrics_middleware
)
from .dependencies import initialize_dependencies, cleanup_dependencies


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
    """Enhanced application lifespan management with dependency initialization"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")
    
    # Create necessary directories
    if not settings.debug:
        os.makedirs("logs", exist_ok=True)
    
    try:
        # Initialize all dependencies and services
        logger.info("Initializing application dependencies...")
        await initialize_dependencies()
        logger.info("Dependencies initialized successfully")
        
        # Log service status
        logger.info(f"Redis enabled: {settings.redis_enabled}")
        logger.info(f"Metrics enabled: {settings.enable_metrics}")
        logger.info(f"Rate limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}")
        
        logger.info(f"Application startup complete - {settings.app_name} v{settings.version}")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        await cleanup_dependencies()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        raise


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
    docs_url="/docs" if settings.enable_swagger else None,
    redoc_url="/redoc" if settings.enable_redoc else None,
    openapi_url="/openapi.json" if settings.enable_openapi else None,
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

# Define security scheme for Swagger UI
security = HTTPBearer()

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your Supabase JWT token"
        }
    }
    
    # Apply security globally to all endpoints except health endpoints
    for path_item in openapi_schema["paths"].values():
        for method in path_item.values():
            if isinstance(method, dict) and "tags" in method:
                if "Health" not in method.get("tags", []):
                    method["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(conversations.router, tags=["Conversations"])
app.include_router(branches.router, tags=["Branches"])
app.include_router(messages.router, tags=["Messages"])
app.include_router(models.router, tags=["Models"])
app.include_router(users.router, tags=["Users"])


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
    """Get enhanced service information"""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "debug": settings.debug,
        "features": {
            "streaming": settings.enable_streaming,
            "authentication": True,
            "metrics": settings.enable_metrics,
            "regeneration": settings.enable_regeneration,
            "branching": settings.enable_branching,
            "search": settings.enable_search,
            "batch_operations": settings.enable_batch_operations,
            "analytics": settings.enable_analytics,
            "caching": settings.redis_enabled
        },
        "endpoints": {
            "health": "/health",
            "chat": "/v1/chat/completions",
            "regenerate": "/v1/chat/regenerate",
            "conversations": "/v1/conversations",
            "conversation_detail": "/v1/conversations/{conversation_id}",
            "conversation_full": "/v1/conversations/{conversation_id}/full",
            "branches": "/v1/conversations/{conversation_id}/branches",
            "messages": "/v1/messages/{message_id}",
            "models": "/v1/models",
            "user_profile": "/v1/user/profile",
            "user_balance": "/v1/user/balance",
            "metrics": "/metrics" if settings.enable_metrics else None,
            "docs": "/docs" if settings.enable_swagger else None
        },
        "limits": {
            "max_conversations_per_user": settings.max_conversations_per_user,
            "max_messages_per_conversation": settings.max_messages_per_conversation,
            "max_branches_per_conversation": settings.max_branches_per_conversation,
            "max_export_conversations": settings.max_export_conversations,
            "max_batch_operation_size": settings.max_batch_operation_size,
            "default_page_size": settings.default_page_size,
            "max_page_size": settings.max_page_size
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