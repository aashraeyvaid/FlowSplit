"""Request and response schemas for FlowSplit API endpoints."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.road import RoadSuitabilityResult, VehicleType, VisionRoadAnalysis
from backend.app.schemas.route import CandidateRoute, Coordinate, SelectedRouteDecision, RoadSegmentData


class CandidatesRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    origin_address: Optional[str] = None
    destination_address: Optional[str] = None
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR
    demo_mode: bool = False  # Deprecated: offline mode is disabled; system runs strictly online


class CandidatesResponse(BaseModel):
    candidates: list[CandidateRoute]
    origin: Coordinate
    destination: Coordinate
    provider: str = "google_routes_api"
    is_demo: bool = False
    message: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRoutesRequest(BaseModel):
    candidates: list[CandidateRoute]
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR
    sample_interval_meters: float = 100.0
    use_cache: bool = True
    demo_mode: bool = False  # Deprecated: offline mode is disabled


class AnalyzeRoutesResponse(BaseModel):
    analyzed_candidates: list[CandidateRoute]
    total_segments_analyzed: int
    imagery_coverage_ratio: float
    analysis_provenance: str
    warnings: list[str] = Field(default_factory=list)


class CostWeightsConfig(BaseModel):
    alpha_travel_time: float = Field(default=1.0, ge=0.0, description="Weight for travel time in seconds")
    beta_unsuitable: float = Field(default=5.0, ge=0.0, description="Weight for unsuitable road penalty")
    gamma_congestion: float = Field(default=8.0, ge=0.0, description="Weight for volume/capacity congestion penalty")
    delta_uncertainty: float = Field(default=2.5, ge=0.0, description="Weight for low confidence penalty")
    hysteresis_threshold: float = Field(default=0.08, ge=0.0, le=0.5, description="Min cost improvement (e.g. 8%) to switch route")


class SelectRouteRequest(BaseModel):
    candidates: list[CandidateRoute]
    current_route_id: Optional[str] = None
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR
    weights: Optional[CostWeightsConfig] = None
    demo_mode: bool = False


class RoadAnalysisRequest(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    road_name: Optional[str] = None
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR


class RoadAnalysisResponse(BaseModel):
    road_id: str
    coordinate: Coordinate
    road_name: Optional[str]
    vision_analysis: Optional[VisionRoadAnalysis]
    suitability: RoadSuitabilityResult
    has_street_view: bool
    imagery_timestamp: Optional[str]
    source: str


class PublicConfigResponse(BaseModel):
    google_maps_browser_key: Optional[str] = None
    google_maps_js_api_url: str = "https://maps.googleapis.com/maps/api/js"
    google_routes_api_url: str = "https://routes.googleapis.com/directions/v2:computeRoutes"
    api_base_url: Optional[str] = None
    has_routes_backend_key: bool = False
    has_street_view_backend_key: bool = False
    has_gemini_backend_key: bool = False
    gemini_model: str = "gemini-2.5-flash"
    online_mode_only: bool = True
    demo_mode_active: bool = False
    environment: str = "development"
    api_version: str = "1.0.0"
