"""Short-lived route allocation registry for congestion feedback and demand tracking.

Tracks recently allocated route recommendations across active requests
to avoid concentrating all users onto a single fragile corridor.
Includes expiration of stale allocations and hysteresis thresholds.
"""

import time
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class AllocationRecord:
    route_id: str
    segment_ids: list[str]
    timestamp: float
    vehicle_count_weight: float = 1.0


class RouteAllocationRegistry:
    """In-memory (with optional Redis support) registry of recently recommended routes.

    Note: Route allocations track application recommendations, not confirmed
    physical road occupancy.
    """

    def __init__(self, time_window_seconds: float = 300.0, max_records: int = 1000):
        self.time_window_seconds = time_window_seconds
        self.max_records = max_records
        self.records: list[AllocationRecord] = []
        self._segment_allocated_flow: dict[str, float] = {}

    def _prune_expired(self, current_time: float) -> None:
        """Removes allocations older than the time window."""
        cutoff = current_time - self.time_window_seconds
        self.records = [rec for rec in self.records if rec.timestamp >= cutoff]

    def record_allocation(self, route_id: str, segment_ids: list[str], weight: float = 1.0) -> None:
        """Registers a route recommendation."""
        now = time.time()
        self._prune_expired(now)
        if len(self.records) >= self.max_records:
            self.records.pop(0)
        self.records.append(AllocationRecord(route_id=route_id, segment_ids=segment_ids, timestamp=now, vehicle_count_weight=weight))

    def get_segment_allocated_demand(self, segment_id: str) -> float:
        """Returns the current synthetic allocated vehicle demand on a segment."""
        now = time.time()
        self._prune_expired(now)
        total = 0.0
        for rec in self.records:
            if segment_id in rec.segment_ids:
                # Linear decay over the time window
                elapsed = now - rec.timestamp
                decay = max(0.0, 1.0 - (elapsed / self.time_window_seconds))
                total += rec.vehicle_count_weight * decay
        return total

    def should_switch_route(
        self,
        current_cost: float,
        proposed_cost: float,
        threshold_ratio: float = 0.08,
    ) -> bool:
        """Applies hysteresis to prevent erratic route oscillation.

        Returns True only if proposed_cost improves upon current_cost by at least threshold_ratio.
        """
        if current_cost <= 0:
            return True
        improvement = (current_cost - proposed_cost) / current_cost
        return improvement >= threshold_ratio

    def clear(self) -> None:
        self.records.clear()


# Default process-level registry
global_allocation_registry = RouteAllocationRegistry()
