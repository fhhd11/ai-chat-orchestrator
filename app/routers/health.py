"""Health check endpoints"""

from fastapi import APIRouter, Depends
from loguru import logger

from ..config import settings
from ..models import HealthResponse
from ..dependencies import SupabaseClientDep, LiteLLMClientDep


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health of the service and its dependencies",
    tags=["Health"]
)
async def health_check(
    supabase_client: SupabaseClientDep,
    litellm_client: LiteLLMClientDep
) -> HealthResponse:
    """
    Health check endpoint that verifies service status and dependencies
    
    Returns:
        HealthResponse with service status and dependency health
    """
    logger.info("Health check requested")
    
    services = {
        "app": "healthy",
        "supabase": "unknown",
        "litellm": "unknown"
    }
    
    # Check Supabase connectivity (simplified check)
    try:
        # We can't easily health check Supabase Edge Functions without auth,
        # so we'll just check if the client is initialized
        if supabase_client:
            services["supabase"] = "healthy"
        else:
            services["supabase"] = "unhealthy"
    except Exception as e:
        logger.warning(f"Supabase health check failed: {e}")
        services["supabase"] = "unhealthy"
    
    # Check LiteLLM connectivity
    try:
        is_healthy = await litellm_client.health_check()
        services["litellm"] = "healthy" if is_healthy else "unhealthy"
    except Exception as e:
        logger.warning(f"LiteLLM health check failed: {e}")
        services["litellm"] = "unhealthy"
    
    # Overall status
    overall_status = "healthy"
    if any(status == "unhealthy" for status in services.values()):
        overall_status = "degraded"
    
    response = HealthResponse(
        status=overall_status,
        version=settings.version,
        services=services
    )
    
    logger.info(f"Health check completed: {overall_status}")
    return response


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if the service is ready to handle requests",
    tags=["Health"]
)
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes/container orchestration
    
    Returns:
        Simple OK response if service is ready
    """
    return {"status": "ready"}


@router.get(
    "/live",
    summary="Liveness check", 
    description="Check if the service is alive",
    tags=["Health"]
)
async def liveness_check():
    """
    Liveness check endpoint for Kubernetes/container orchestration
    
    Returns:
        Simple OK response if service is alive
    """
    return {"status": "alive"}