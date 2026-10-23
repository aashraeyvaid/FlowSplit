"""Health and readiness check endpoints."""

from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint indicating service status and active capabilities."""
    return {
        "status": "healthy",
        "service": "FlowSplit Routing Engine",
        "version": "1.0.0",
        "mode": "online_only",
        "environment": settings.ENVIRONMENT,
        "capabilities": {
            "google_routes_configured": bool(settings.GOOGLE_ROUTES_API_KEY),
            "street_view_configured": bool(settings.GOOGLE_STREET_VIEW_API_KEY),
            "gemini_vision_configured": bool(settings.GEMINI_API_KEY),
            "offline_demo_available": False,
        },
    }
