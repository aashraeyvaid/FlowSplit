"""Public configuration endpoint for client bootstrap."""

from fastapi import APIRouter
from backend.app.config import settings
from backend.app.schemas.api import PublicConfigResponse

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("/public", response_model=PublicConfigResponse)
async def get_public_config():
    """Returns safe, redacted configuration for frontend client initialization."""
    return PublicConfigResponse(
        google_maps_browser_key=settings.GOOGLE_MAPS_BROWSER_KEY,
        google_maps_js_api_url=settings.GOOGLE_MAPS_JS_API_URL,
        google_routes_api_url=settings.GOOGLE_ROUTES_API_URL,
        api_base_url=settings.API_BASE_URL,
        has_routes_backend_key=bool(settings.GOOGLE_ROUTES_API_KEY),
        has_street_view_backend_key=bool(settings.GOOGLE_STREET_VIEW_API_KEY),
        has_gemini_backend_key=bool(settings.GEMINI_API_KEY),
        gemini_model=settings.GEMINI_MODEL,
        online_mode_only=True,
        demo_mode_active=False,
        environment=settings.ENVIRONMENT,
        api_version="1.0.0",
    )
