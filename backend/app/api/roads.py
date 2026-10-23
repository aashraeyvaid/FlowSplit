"""FastAPI endpoints for individual road segment inspection and retrieval.

Operates strictly in online mode using Gemini Vision and Street View APIs.
Persistence is SQLite-free (in-memory or optional PostgreSQL).
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.db.models import RoadSegment as DBRoadSegment, RoadObservation as DBRoadObservation
from backend.app.schemas.api import RoadAnalysisRequest, RoadAnalysisResponse
from backend.app.schemas.route import Coordinate
from backend.app.services.street_view import fetch_street_view_image_bytes, check_street_view_availability
from backend.app.services.gemini_vision import analyze_road_imagery_with_gemini
from backend.app.engine.scoring import calculate_road_suitability

router = APIRouter(prefix="/api/roads", tags=["Roads"])


@router.post("/analyze", response_model=RoadAnalysisResponse)
async def analyze_road_segment(
    req: RoadAnalysisRequest,
    db=Depends(get_db),
):
    """Inspects a specific geographic road point online via Street View and Gemini Vision."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key (GEMINI_API_KEY) is not configured in .env. "
                "FlowSplit operates strictly in online mode and requires active API credentials."
            ),
        )

    coord = Coordinate(lat=req.lat, lng=req.lng)

    # Street View image fetch
    image_bytes = None
    has_sv = False
    if settings.GOOGLE_STREET_VIEW_API_KEY:
        meta = await check_street_view_availability(coord)
        has_sv = meta.is_available
        if has_sv:
            image_bytes = await fetch_street_view_image_bytes(coord, heading=req.heading)

    # Online Gemini Vision Analysis
    try:
        vision, source = await analyze_road_imagery_with_gemini(
            image_bytes=image_bytes,
            road_name=req.road_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini Vision analysis error: {str(exc)}")

    # Deterministic suitability score
    suitability = calculate_road_suitability(
        analysis=vision,
        vehicle_type=req.vehicle_type,
    )

    # Store in database
    road_id = str(uuid.uuid4())
    db_segment = DBRoadSegment(
        id=road_id,
        road_name=req.road_name or f"Road at {req.lat:.4f},{req.lng:.4f}",
        start_lat=req.lat,
        start_lng=req.lng,
        end_lat=req.lat,
        end_lng=req.lng,
        suitability_score=suitability.suitability_score,
        confidence=suitability.confidence,
        feature_analysis=vision.model_dump() if vision else None,
        penalties=[p.model_dump() for p in suitability.penalties_applied],
        source=source,
    )
    db.add(db_segment)

    # Add observation record
    obs_id = str(uuid.uuid4())
    db_obs = DBRoadObservation(
        id=obs_id,
        road_segment_id=road_id,
        observation_type="vision_analysis",
        measured_or_estimated_value=vision.model_dump() if vision else {},
        source=source,
        confidence=suitability.confidence,
    )
    db.add(db_obs)
    await db.commit()

    return RoadAnalysisResponse(
        road_id=road_id,
        coordinate=coord,
        road_name=req.road_name,
        vision_analysis=vision,
        suitability=suitability,
        has_street_view=has_sv,
        imagery_timestamp=None,
        source=source,
    )


@router.get("/{road_id}")
async def get_road_segment(
    road_id: str,
    db=Depends(get_db),
):
    """Retrieves an existing road segment analysis and observations by ID."""
    query = select(DBRoadSegment).where(DBRoadSegment.id == road_id)
    result = await db.execute(query)
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail=f"Road segment '{road_id}' not found.")

    return {
        "road_id": seg.id,
        "road_name": seg.road_name,
        "suitability_score": seg.suitability_score,
        "confidence": seg.confidence,
        "feature_analysis": seg.feature_analysis,
        "penalties": seg.penalties,
        "nominal_capacity_vph": seg.nominal_capacity_vph,
        "analysis_timestamp": seg.analysis_timestamp.isoformat() if hasattr(seg.analysis_timestamp, "isoformat") else str(seg.analysis_timestamp),
        "source": seg.source,
        "status": seg.status,
    }
