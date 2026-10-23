"""Unit tests for the deterministic road suitability scoring engine."""

import pytest
from backend.app.schemas.road import (
    ObstructionLevel,
    PedestrianContext,
    VehicleType,
    VisionRoadAnalysis,
)
from backend.app.engine.scoring import calculate_road_suitability


def test_wide_arterial_high_suitability():
    """Arterial with 4 lanes, generous width, no parking should score >= 80."""
    vision = VisionRoadAnalysis(
        usable_road_width_meters=14.0,
        visible_lane_count=4,
        parking_obstruction=ObstructionLevel.NONE,
        visible_obstacles=[],
        pedestrian_cyclist_activity=PedestrianContext.LOW,
        visible_road_restrictions=[],
        confidence=0.95,
        evidence_notes=["Wide multi-lane divided arterial"],
    )
    result = calculate_road_suitability(vision, functional_class="arterial", vehicle_type=VehicleType.PASSENGER_CAR)
    assert result.suitability_score >= 80.0
    assert result.confidence >= 0.85
    assert result.is_safe_for_vehicle is True
    assert len(result.penalties_applied) == 0


def test_narrow_residential_with_parking_and_school_zone():
    """Narrow residential alley with heavy parking and school zone should receive severe penalties."""
    vision = VisionRoadAnalysis(
        usable_road_width_meters=3.5,
        visible_lane_count=1,
        parking_obstruction=ObstructionLevel.HIGH,
        visible_obstacles=["double_parking"],
        pedestrian_cyclist_activity=PedestrianContext.SCHOOL_ZONE,
        visible_road_restrictions=["resident_only"],
        confidence=0.85,
    )
    result = calculate_road_suitability(vision, functional_class="narrow_residential", vehicle_type=VehicleType.PASSENGER_CAR)
    # Score should be depressed (< 40) due to compounded penalties
    assert result.suitability_score < 40.0
    penalties = [p.name for p in result.penalties_applied]
    assert "severe_parking_choke" in penalties
    assert "vulnerable_pedestrian_corridor" in penalties
    assert "residential_traffic_calming" in penalties


def test_unknown_features_explicitly_penalized_not_safe():
    """When vision is unable to infer width and lanes, it must not assume safe conditions."""
    vision = VisionRoadAnalysis(
        usable_road_width_meters=None,
        visible_lane_count=None,
        parking_obstruction=ObstructionLevel.MODERATE,
        confidence=0.6,
        missing_or_uncertain_info=["road_width", "lane_count"],
    )
    result = calculate_road_suitability(vision, functional_class="residential")
    penalties = [p.name for p in result.penalties_applied]
    assert "unknown_road_width" in penalties
    assert "unknown_lane_count" in penalties
    # Confidence must reflect uncertainty
    assert result.confidence < 0.6
    # Score should be conservative, not high
    assert result.suitability_score < 55.0


def test_missing_vision_analysis_fallback():
    """Completely missing imagery must trigger explicit fallback with heavy penalty."""
    result = calculate_road_suitability(None, functional_class="residential")
    assert result.suitability_score <= 35.0
    assert result.confidence == 0.2
    assert any(p.name == "missing_road_imagery_analysis" for p in result.penalties_applied)


def test_vehicle_type_width_thresholds():
    """A 4.0m road is passable for a passenger car but substandard for a heavy truck."""
    vision = VisionRoadAnalysis(
        usable_road_width_meters=4.0,
        visible_lane_count=1,
        parking_obstruction=ObstructionLevel.LOW,
        confidence=0.9,
    )
    car_result = calculate_road_suitability(vision, vehicle_type=VehicleType.PASSENGER_CAR)
    truck_result = calculate_road_suitability(vision, vehicle_type=VehicleType.HEAVY_TRUCK)

    assert car_result.suitability_score > truck_result.suitability_score
    truck_penalties = [p.name for p in truck_result.penalties_applied]
    assert "substandard_width_for_vehicle" in truck_penalties


def test_prohibited_access_violation():
    """Signage indicating no-entry must set is_safe_for_vehicle to False."""
    vision = VisionRoadAnalysis(
        usable_road_width_meters=7.0,
        visible_lane_count=2,
        visible_road_restrictions=["no_entry_except_buses"],
        confidence=0.9,
    )
    result = calculate_road_suitability(vision)
    assert result.is_safe_for_vehicle is False
    assert any(p.name == "access_restriction" for p in result.penalties_applied)
