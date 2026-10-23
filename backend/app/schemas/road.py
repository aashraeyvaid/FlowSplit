"""Pydantic schemas for road analysis, vision outputs, and suitability scoring."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class VehicleType(str, Enum):
    PASSENGER_CAR = "passenger_car"
    DELIVERY_VAN = "delivery_van"
    EMERGENCY_VEHICLE = "emergency_vehicle"
    HEAVY_TRUCK = "heavy_truck"


class ObstructionLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BLOCKED = "blocked"


class PedestrianContext(str, Enum):
    LOW = "low"
    MODERATE_SIDEWALK = "moderate_sidewalk"
    HIGH_PEDESTRIAN_ZONE = "high_pedestrian_zone"
    SCHOOL_ZONE = "school_zone"
    UNPROTECTED_SHARED_SPACE = "unprotected_shared_space"


class VisionRoadAnalysis(BaseModel):
    """Structured output expected from Gemini vision inspection of street imagery."""
    usable_road_width_meters: Optional[float] = Field(
        default=None,
        ge=1.5,
        le=30.0,
        description="Estimated visible usable carriageway width in meters, if inferable."
    )
    visible_lane_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Visible marked or functional travel lanes, if inferable."
    )
    parking_obstruction: ObstructionLevel = Field(
        default=ObstructionLevel.NONE,
        description="Degree to which parked vehicles reduce effective passing width."
    )
    visible_obstacles: list[str] = Field(
        default_factory=list,
        description="Visible physical hazards such as construction, potholes, or double parking."
    )
    pedestrian_cyclist_activity: PedestrianContext = Field(
        default=PedestrianContext.LOW,
        description="Vulnerable road user context observed or indicated by surroundings."
    )
    visible_road_restrictions: list[str] = Field(
        default_factory=list,
        description="Observed signage or markings (e.g. one-way, weight-limit, school)."
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score in the vision interpretation (0.0 to 1.0)."
    )
    missing_or_uncertain_info: list[str] = Field(
        default_factory=list,
        description="Elements that could not be determined with high certainty from imagery."
    )
    evidence_notes: list[str] = Field(
        default_factory=list,
        description="Visual citations/evidence supporting the inferences."
    )


class PenaltyDetail(BaseModel):
    name: str
    penalty_value: float
    reason: str


class RoadSuitabilityResult(BaseModel):
    """Deterministic road suitability score (0-100) and full breakdown."""
    suitability_score: float = Field(ge=0.0, le=100.0, description="Suitability score 0-100.")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence 0-1.")
    data_freshness_seconds: Optional[int] = Field(default=None, description="Age of data in seconds.")
    feature_contributions: dict[str, float] = Field(
        default_factory=dict,
        description="Normalized contribution of each feature to the composite score."
    )
    penalties_applied: list[PenaltyDetail] = Field(
        default_factory=list,
        description="Specific penalties subtracted from the raw score."
    )
    explanation: str = Field(description="Human-readable rationale for the score.")
    is_safe_for_vehicle: bool = Field(default=True, description="Whether road is deemed safe for vehicle type.")
    vehicle_type: VehicleType = Field(default=VehicleType.PASSENGER_CAR)
