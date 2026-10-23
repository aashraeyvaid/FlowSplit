"""FlowSplit Capacity-Aware Route Selection Engine.

Evaluates alternative candidate routes using a multi-factor cost function:
  route_cost = travel_time_cost + congestion_penalty + unsuitable_road_penalty + uncertainty_penalty

Balances travel duration against the severe risk of overloading narrow residential corridors.
"""

from typing import Optional
from backend.app.schemas.api import CostWeightsConfig
from backend.app.schemas.road import VehicleType
from backend.app.schemas.route import (
    CandidateRoute,
    RouteCostBreakdown,
    SelectedRouteDecision,
)
from backend.app.engine.registry import RouteAllocationRegistry, global_allocation_registry


# Standard Bureau of Public Roads (BPR) parameters for congestion penalty modeling
BPR_ALPHA = 0.15
BPR_BETA = 4.0


def calculate_segment_congestion_penalty(
    volume_vph: float,
    capacity_vph: float,
    allocated_demand: float = 0.0,
) -> float:
    """Calculates congestion penalty using non-linear volume/capacity response.

    When volume/capacity ratio (V/C) is below 0.75, friction is mild.
    As V/C exceeds 0.85-1.0, penalty escalates steeply, modeling the rapid
    breakdown of flow and queuing on narrow residential corridors.
    """
    total_effective_volume = max(0.0, volume_vph + allocated_demand * 60.0)  # Scale active allocations to hourly rate
    safe_capacity = max(100.0, capacity_vph)
    vc_ratio = total_effective_volume / safe_capacity

    if vc_ratio <= 0.6:
        return 0.0
    elif vc_ratio <= 0.85:
        # Mild onset of delay
        return round(15.0 * ((vc_ratio - 0.6) / 0.25) ** 2, 2)
    elif vc_ratio <= 1.0:
        # Near capacity, queue forming
        return round(40.0 + 60.0 * ((vc_ratio - 0.85) / 0.15) ** 3, 2)
    else:
        # Severely overloaded (gridlock conditions)
        over_factor = vc_ratio - 1.0
        return round(100.0 + 350.0 * over_factor + 150.0 * (over_factor ** 2), 2)


def evaluate_candidate_route(
    route: CandidateRoute,
    weights: CostWeightsConfig,
    registry: Optional[RouteAllocationRegistry] = None,
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
) -> RouteCostBreakdown:
    """Evaluates the composite cost of a candidate route."""
    reg = registry or global_allocation_registry

    # 1. Travel time cost (traffic-aware duration in seconds)
    travel_time_sec = route.traffic_duration_seconds or route.free_flow_duration_seconds
    travel_time_cost = travel_time_sec * weights.alpha_travel_time

    # 2. Road unsuitability and congestion penalties aggregated across segments
    total_length = max(1.0, sum(seg.length_meters for seg in route.segments) or route.distance_meters)
    weighted_unsuitability = 0.0
    total_congestion_penalty = 0.0
    total_confidence = 0.0
    max_vc_ratio = 0.0
    bottleneck_segment_id: Optional[str] = None
    bottleneck_reason: Optional[str] = None
    worst_penalty = -1.0

    if route.segments:
        for seg in route.segments:
            seg_len = seg.length_meters
            weight_ratio = seg_len / total_length

            # Suitability score contribution
            seg_suitability = seg.suitability.suitability_score if seg.suitability else route.suitability_score
            seg_conf = seg.suitability.confidence if seg.suitability else route.confidence
            total_confidence += seg_conf * weight_ratio

            # (100 - score) represents unsuitability
            unsuitability_penalty_for_seg = (100.0 - seg_suitability) * weight_ratio
            weighted_unsuitability += unsuitability_penalty_for_seg

            # Congestion and capacity calculation
            allocated = reg.get_segment_allocated_demand(seg.segment_id)
            seg_cong_pen = calculate_segment_congestion_penalty(
                seg.current_volume_vph,
                seg.nominal_capacity_vph,
                allocated_demand=allocated,
            )
            total_congestion_penalty += seg_cong_pen * weight_ratio

            # Track bottleneck
            vc = (seg.current_volume_vph + allocated * 60.0) / max(1.0, seg.nominal_capacity_vph)
            if vc > max_vc_ratio:
                max_vc_ratio = vc

            local_penalty = unsuitability_penalty_for_seg * weights.beta_unsuitable + seg_cong_pen * weights.gamma_congestion
            if local_penalty > worst_penalty:
                worst_penalty = local_penalty
                bottleneck_segment_id = seg.segment_id
                if vc > 0.9:
                    bottleneck_reason = f"Capacity constraint on {seg.name} (V/C = {vc:.2f})"
                elif seg_suitability < 40.0:
                    bottleneck_reason = f"Narrow corridor or roadside friction on {seg.name} (Suitability: {seg_suitability:.0f}/100)"
                else:
                    bottleneck_reason = f"Primary delay section on {seg.name}"
    else:
        # Fallback when segment-level breakdown is not parsed
        weighted_unsuitability = 100.0 - route.suitability_score
        total_confidence = route.confidence
        bottleneck_reason = "Evaluated at overall route level"

    mean_confidence = max(0.1, min(1.0, total_confidence or route.confidence))

    # 3. Scaled penalties
    unsuitable_cost = weighted_unsuitability * weights.beta_unsuitable
    congestion_cost = total_congestion_penalty * weights.gamma_congestion
    uncertainty_cost = (1.0 - mean_confidence) * 100.0 * weights.delta_uncertainty

    total_cost = travel_time_cost + unsuitable_cost + congestion_cost + uncertainty_cost

    overall_suitability = max(0.0, min(100.0, 100.0 - weighted_unsuitability))

    return RouteCostBreakdown(
        route_id=route.id,
        route_name=route.name,
        travel_time_seconds=round(travel_time_sec, 1),
        travel_time_cost=round(travel_time_cost, 2),
        congestion_penalty=round(congestion_cost, 2),
        unsuitable_road_penalty=round(unsuitable_cost, 2),
        uncertainty_penalty=round(uncertainty_cost, 2),
        total_cost=round(total_cost, 2),
        overall_suitability_score=round(overall_suitability, 1),
        mean_confidence=round(mean_confidence, 2),
        bottleneck_segment_id=bottleneck_segment_id,
        bottleneck_reason=bottleneck_reason,
        volume_to_capacity_ratio_max=round(max_vc_ratio, 2),
    )


def select_best_route(
    candidates: list[CandidateRoute],
    current_route_id: Optional[str] = None,
    weights: Optional[CostWeightsConfig] = None,
    registry: Optional[RouteAllocationRegistry] = None,
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
    record_choice: bool = True,
) -> SelectedRouteDecision:
    """Core FlowSplit route selector: selects best route while mitigating shortcut gridlock."""
    if not candidates:
        raise ValueError("Cannot select route: candidate routes list is empty.")

    active_weights = weights or CostWeightsConfig()
    reg = registry or global_allocation_registry

    breakdowns: list[RouteCostBreakdown] = [
        evaluate_candidate_route(c, active_weights, reg, vehicle_type) for c in candidates
    ]

    candidate_map = {c.id: c for c in candidates}
    breakdown_map = {b.route_id: b for b in breakdowns}

    # Sort candidates by total cost ascending
    sorted_breakdowns = sorted(breakdowns, key=lambda b: b.total_cost)
    best_candidate_id = sorted_breakdowns[0].route_id

    # Check hysteresis if user currently has an assigned route
    hysteresis_applied = False
    selected_id = best_candidate_id

    if current_route_id and current_route_id in breakdown_map and current_route_id != best_candidate_id:
        current_breakdown = breakdown_map[current_route_id]
        best_breakdown = sorted_breakdowns[0]

        # Require significant improvement to switch route
        if not reg.should_switch_route(
            current_breakdown.total_cost,
            best_breakdown.total_cost,
            threshold_ratio=active_weights.hysteresis_threshold,
        ):
            # Retain current route to prevent oscillating recommendations
            selected_id = current_route_id
            hysteresis_applied = True

    selected_route = candidate_map[selected_id]
    selected_breakdown = breakdown_map[selected_id]

    # Register allocation in the registry to prevent overload on repeated calls
    if record_choice:
        seg_ids = [s.segment_id for s in selected_route.segments]
        reg.record_allocation(selected_id, seg_ids, weight=1.0)

    # Construct rationale explanation
    shortest_time_candidate = min(candidates, key=lambda c: c.traffic_duration_seconds or c.free_flow_duration_seconds)
    time_diff_sec = selected_route.traffic_duration_seconds - shortest_time_candidate.traffic_duration_seconds

    rationale_parts = []
    if selected_route.id == shortest_time_candidate.id:
        rationale_parts.append(
            f"Selected '{selected_route.name}': provides the fastest transit time ({selected_route.traffic_duration_seconds/60:.1f} mins) "
            f"while maintaining high suitability ({selected_breakdown.overall_suitability_score}/100) and acceptable corridor capacity."
        )
    else:
        rationale_parts.append(
            f"Selected '{selected_route.name}' over shorter shortcut '{shortest_time_candidate.name}' (+{time_diff_sec/60:.1f} mins difference). "
            f"The shortcut corridor has lower suitability ({candidate_map[shortest_time_candidate.id].suitability_score}/100) "
            f"or excessive congestion risk ({breakdown_map[shortest_time_candidate.id].bottleneck_reason or 'bottleneck'})."
        )

    if hysteresis_applied:
        rationale_parts.append(
            f"Retained existing route '{selected_route.name}' due to stability hysteresis "
            f"(alternative improvement was under {active_weights.hysteresis_threshold*100:.0f}% threshold)."
        )

    limitations = [
        "Capacities and volumes reflect real-time API traffic bounds, imagery inferences, or simulation models.",
        "FlowSplit recommendations guide application users and do not control third-party navigation traffic.",
    ]

    warnings = []
    if selected_breakdown.volume_to_capacity_ratio_max > 0.85:
        warnings.append(f"Notice: Segment approaching saturation (V/C = {selected_breakdown.volume_to_capacity_ratio_max:.2f}).")
    if selected_breakdown.mean_confidence < 0.6:
        warnings.append("Notice: Confidence is limited due to sparse road imagery or missing segment attributes.")

    return SelectedRouteDecision(
        selected_route_id=selected_id,
        selected_route=selected_route,
        candidate_breakdowns=sorted_breakdowns,
        recommendation_rationale=" ".join(rationale_parts),
        algorithm_mode="flowsplit_capacity_aware",
        hysteresis_applied=hysteresis_applied,
        previous_route_id=current_route_id,
        vehicle_type=vehicle_type,
        data_limitations=limitations,
        warnings=warnings,
    )
