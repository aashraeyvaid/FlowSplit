"""Security and safety validation tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.config import settings


@pytest.mark.asyncio
async def test_api_keys_never_leaked_in_public_endpoints():
    """Verify that backend keys are strictly secret and not present in any response body."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/config/public")
        body = res.text
        # If any real or dummy server keys exist, verify they aren't printed verbatim
        if settings.GOOGLE_ROUTES_API_KEY:
            assert settings.GOOGLE_ROUTES_API_KEY not in body
        if settings.GOOGLE_STREET_VIEW_API_KEY:
            assert settings.GOOGLE_STREET_VIEW_API_KEY not in body
        if settings.GEMINI_API_KEY:
            assert settings.GEMINI_API_KEY not in body


@pytest.mark.asyncio
async def test_safe_error_handling_masks_internal_tracebacks():
    """Verify that unexpected server errors return sanitized JSON without Python stacktraces."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Invalid route analysis ID returns 404 cleanly
        res = await ac.get("/api/routes/analysis/non-existent-uuid-1234")
        assert res.status_code == 404
        data = res.json()
        assert "Traceback" not in str(data)
        assert "detail" in data
