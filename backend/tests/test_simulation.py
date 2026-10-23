"""Unit tests for offline traffic simulation and baseline vs FlowSplit comparison."""

import pytest
from backend.app.engine.simulation import (
    build_offline_network,
    bpr_travel_time,
    run_traffic_simulation,
    compare_baseline_vs_flowsplit,
)


def test_offline_network_integrity():
    """Verify offline candidate network has 3 routes with distinct properties."""
    routes = build_offline_network()
    assert len(routes) == 3

    route_names = [r.name for r in routes]
    assert any("Grand Parkway" in name for name in route_names)
    assert any("Elm & Pine" in name for name in route_names)
    assert any("Central Boulevard" in name for name in route_names)

    # Check segment-level data
    shortcut = next(r for r in routes if "Elm" in r.name)
    assert len(shortcut.segments) == 2
    assert shortcut.segments[0].nominal_capacity_vph <= 300.0


def test_bpr_travel_time_behavior():
    """Verify delay increases exponentially when volume exceeds capacity."""
    free_flow = 300.0  # 5 minutes
    cap = 1000.0

    # Under-capacity flow: 400 veh/hr
    t_under, delay_under, queue_under = bpr_travel_time(free_flow, volume_vph=400, capacity_vph=cap)
    assert delay_under < 10.0
    assert queue_under == 0.0

    # Over-capacity flow: 2000 veh/hr
    t_over, delay_over, queue_over = bpr_travel_time(free_flow, volume_vph=2000, capacity_vph=cap)
    assert delay_over > 500.0
    assert queue_over > 50.0


def test_simulation_comparison_demonstrates_benefit():
    """Verifies that FlowSplit measurably reduces overloaded segments and queue buildup."""
    comparison = compare_baseline_vs_flowsplit(total_trips=900)

    # Baseline creates overloaded segments on Elm & Pine
    assert comparison.baseline_result.overloaded_segments_count >= 1
    assert comparison.baseline_result.maximum_queue_vehicles > 20.0

    # FlowSplit prevents overloading narrow residential corridors
    assert comparison.flowsplit_result.overloaded_segments_count == 0
    assert comparison.overloaded_segments_prevented >= 1

    # Queue reduction should be significant (> 50%)
    assert comparison.queue_reduction_percent > 50.0

    # Average travel time under FlowSplit should be superior to gridlocked baseline
    assert comparison.flowsplit_result.average_travel_time_seconds < comparison.baseline_result.average_travel_time_seconds
    assert comparison.travel_time_delta_percent > 0.0
