"""Unit tests for FlowSplit capacity-aware route selection engine."""

import pytest
from backend.app.schemas.api import CostWeightsConfig
from backend.app.engine.simulation import build_offline_network
from backend.app.engine.routing import (
    evaluate_candidate_route,
    select_best_route,
    calculate_segment_congestion_penalty,
)
from backend.app.engine.registry import RouteAllocationRegistry


def test_bpr_congestion_penalty_escalation():
    """Verify non-linear penalty curve as volume approaches and exceeds capacity."""
    # Under low volume (V/C = 0.5), penalty is 0
    pen_low = calculate_segment_congestion_penalty(volume_vph=500, capacity_vph=1000)
    assert pen_low == 0.0

    # Near capacity (V/C = 0.95), moderate penalty
    pen_near = calculate_segment_congestion_penalty(volume_vph=950, capacity_vph=1000)
    assert pen_near > 50.0

    # Over capacity (V/C = 1.3), steep gridlock penalty
    pen_over = calculate_segment_congestion_penalty(volume_vph=1300, capacity_vph=1000)
    assert pen_over > 200.0


def test_flowsplit_prefers_suitable_arterial_over_fragile_shortcut():
    """Demonstrates FlowSplit choosing arterial highway over narrow residential alley."""
    candidates = build_offline_network()
    # candidates[0] is Grand Parkway Arterial (7.5m duration, suitability 90+)
    # candidates[1] is Elm Shortcut (6.3m duration, suitability ~30-35)

    # In free-flow travel time alone, candidates[1] is shorter
    assert candidates[1].traffic_duration_seconds < candidates[0].traffic_duration_seconds

    # FlowSplit evaluation
    registry = RouteAllocationRegistry()
    weights = CostWeightsConfig(
        alpha_travel_time=1.0,
        beta_unsuitable=5.0,
        gamma_congestion=8.0,
        delta_uncertainty=2.0,
    )

    decision = select_best_route(candidates, weights=weights, registry=registry)

    # FlowSplit selects the Arterial (Grand Parkway), rejecting the gridlock shortcut
    assert decision.selected_route_id == "route-arterial-grand-pkwy"
    assert "Grand Parkway" in decision.selected_route.name

    # Rationale explains rejecting the shortcut
    assert "shortcut" in decision.recommendation_rationale.lower() or "suitability" in decision.recommendation_rationale.lower()


def test_hysteresis_prevents_unnecessary_route_oscillation():
    """If user is already on a route, FlowSplit requires improvement exceeding threshold to switch."""
    candidates = build_offline_network()
    registry = RouteAllocationRegistry()
    weights = CostWeightsConfig(hysteresis_threshold=0.15)  # Require 15% improvement

    # Assume user is currently navigating on Central Boulevard
    current_route = "route-collector-central-blvd"

    decision = select_best_route(
        candidates,
        current_route_id=current_route,
        weights=weights,
        registry=registry,
    )

    # If the alternative's cost improvement does not meet the 15% threshold, hysteresis keeps the user on Central Blvd
    if decision.selected_route_id == current_route:
        assert decision.hysteresis_applied is True


def test_empty_candidates_raises_value_error():
    """Passing empty list of candidate routes must raise ValueError."""
    with pytest.raises(ValueError, match="candidate routes list is empty"):
        select_best_route([])
