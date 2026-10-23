"""Schemas for the deterministic offline traffic simulation comparison."""

from pydantic import BaseModel, Field
from backend.app.schemas.route import CandidateRoute, RouteCostBreakdown


class SegmentSimulationMetric(BaseModel):
    segment_id: str
    name: str
    length_meters: float
    nominal_capacity_vph: float
    assigned_volume_vph: float
    volume_to_capacity_ratio: float
    effective_speed_kmh: float
    estimated_delay_seconds: float
    estimated_queue_length_vehicles: float
    is_overloaded: bool
    suitability_score: float


class SimulationRunResult(BaseModel):
    strategy_name: str  # "Baseline (Shortest-Time)" vs "FlowSplit (Capacity-Aware)"
    total_trips_simulated: int
    route_allocations: dict[str, int]
    average_travel_time_seconds: float
    worst_travel_time_seconds: float
    overloaded_segments_count: int
    maximum_queue_vehicles: float
    average_network_utilization_pct: float
    segment_metrics: list[SegmentSimulationMetric]
    cost_breakdowns: list[RouteCostBreakdown]
    summary_verdict: str


class OfflineSimulationComparison(BaseModel):
    origin_name: str
    destination_name: str
    total_hourly_demand_vehicles: int
    baseline_result: SimulationRunResult
    flowsplit_result: SimulationRunResult
    travel_time_delta_percent: float
    queue_reduction_percent: float
    overloaded_segments_prevented: int
    notes: list[str]
    candidates: list[CandidateRoute]
