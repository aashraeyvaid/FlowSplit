"""FastAPI endpoints for candidate route generation, analysis, and selection.

Operates strictly in online mode using Google Routes API and Gemini Vision.
Persistence is SQLite-free (in-memory or optional PostgreSQL).
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.db.models import RouteAnalysis as DBRouteAnalysis
from backend.app.schemas.api import (
    AnalyzeRoutesRequest,
    AnalyzeRoutesResponse,
    CandidatesRequest,
    CandidatesResponse,
    SelectRouteRequest,
)
from backend.app.schemas.route import SelectedRouteDecision
from backend.app.services.google_routes import get_candidate_routes
from backend.app.services.pipeline import analyze_candidate_routes_pipeline
from backend.app.engine.routing import select_best_route
from backend.app.config import settings

router = APIRouter(prefix="/api/routes", tags=["Routes"])


@router.post("/candidates", response_model=CandidatesResponse)
async def generate_candidate_routes(req: CandidatesRequest):
    """Generates real-time alternative candidate routes between origin and destination using Google Routes API."""
    # Validate coordinate bounds
    if not (-90.0 <= req.origin.lat <= 90.0 and -180.0 <= req.origin.lng <= 180.0):
        raise HTTPException(status_code=400, detail="Invalid origin latitude/longitude bounds.")
    if not (-90.0 <= req.destination.lat <= 90.0 and -180.0 <= req.destination.lng <= 180.0):
        raise HTTPException(status_code=400, detail="Invalid destination latitude/longitude bounds.")

    if not settings.GOOGLE_ROUTES_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Routes API key (GOOGLE_ROUTES_API_KEY) is not configured in .env. "
                "FlowSplit operates strictly in online mode and requires active API credentials."
            ),
        )

    try:
        candidates, provider, warnings = await get_candidate_routes(
            origin=req.origin,
            destination=req.destination,
            vehicle_type=req.vehicle_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Routes API error: {str(exc)}")

    return CandidatesResponse(
        candidates=candidates,
        origin=req.origin,
        destination=req.destination,
        provider="google_routes_api",
        is_demo=False,
        message="Live online routes retrieved successfully.",
        warnings=warnings,
    )


@router.post("/analyze", response_model=AnalyzeRoutesResponse)
async def analyze_routes(req: AnalyzeRoutesRequest):
    """Performs real-time street imagery inspection and road suitability scoring on candidates."""
    if not req.candidates:
        raise HTTPException(status_code=400, detail="Candidate routes list is empty.")

    try:
        analyzed, total_segs, coverage, prov = await analyze_candidate_routes_pipeline(
            candidates=req.candidates,
            vehicle_type=req.vehicle_type,
            sample_interval_meters=req.sample_interval_meters,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Road analysis failed: {str(exc)}")

    return AnalyzeRoutesResponse(
        analyzed_candidates=analyzed,
        total_segments_analyzed=total_segs,
        imagery_coverage_ratio=coverage,
        analysis_provenance=prov,
        warnings=[],
    )


@router.post("/select", response_model=SelectedRouteDecision)
async def select_route(
    req: SelectRouteRequest,
    db=Depends(get_db),
):
    """Executes capacity-aware route selection cost function."""
    if not req.candidates:
        raise HTTPException(status_code=400, detail="No candidate routes provided for selection.")

    try:
        decision = select_best_route(
            candidates=req.candidates,
            current_route_id=req.current_route_id,
            weights=req.weights,
            vehicle_type=req.vehicle_type,
        )

        # Store persistent analysis record
        analysis_id = str(uuid.uuid4())
        record = DBRouteAnalysis(
            id=analysis_id,
            origin_text=f"Lat {req.candidates[0].coordinates[0].lat:.4f}, Lng {req.candidates[0].coordinates[0].lng:.4f}" if req.candidates[0].coordinates else "Origin",
            destination_text=f"Lat {req.candidates[0].coordinates[-1].lat:.4f}, Lng {req.candidates[0].coordinates[-1].lng:.4f}" if req.candidates[0].coordinates else "Destination",
            origin_lat=req.candidates[0].coordinates[0].lat if req.candidates[0].coordinates else 0.0,
            origin_lng=req.candidates[0].coordinates[0].lng if req.candidates[0].coordinates else 0.0,
            destination_lat=req.candidates[0].coordinates[-1].lat if req.candidates[0].coordinates else 0.0,
            destination_lng=req.candidates[0].coordinates[-1].lng if req.candidates[0].coordinates else 0.0,
            candidate_summaries=[
                {"id": c.id, "name": c.name, "distance_m": c.distance_meters, "duration_s": c.traffic_duration_seconds}
                for c in req.candidates
            ],
            scoring_configuration=req.weights.model_dump() if req.weights else None,
            selected_route_id=decision.selected_route_id,
            selected_route_name=decision.selected_route.name,
            decision_rationale=decision.recommendation_rationale,
            is_simulated="false",
        )
        db.add(record)
        await db.commit()

        return decision

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Route selection error: {str(exc)}")


@router.get("/analysis/{analysis_id}")
async def get_saved_analysis(
    analysis_id: str,
    db=Depends(get_db),
):
    """Retrieves a historical route analysis record by ID."""
    query = select(DBRouteAnalysis).where(DBRouteAnalysis.id == analysis_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Route analysis '{analysis_id}' not found.")

    return {
        "analysis_id": record.id,
        "origin_text": record.origin_text,
        "destination_text": record.destination_text,
        "selected_route_id": record.selected_route_id,
        "selected_route_name": record.selected_route_name,
        "decision_rationale": record.decision_rationale,
        "candidate_summaries": record.candidate_summaries,
        "scoring_configuration": record.scoring_configuration,
        "analysis_timestamp": record.analysis_timestamp.isoformat() if hasattr(record.analysis_timestamp, "isoformat") else str(record.analysis_timestamp),
        "is_simulated": record.is_simulated,
    }
