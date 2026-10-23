"""Google Routes API v2 client for real-time traffic-aware routing.

Operates strictly in online mode using Google Routes API v2.
All endpoints and API keys are dynamically loaded from environment configuration (.env).
Offline demo fallback and predefined data have been completely removed.
"""

import logging
from typing import Optional
import httpx
from backend.app.config import settings
from backend.app.schemas.route import (
    CandidateRoute,
    Coordinate,
    RoadSegmentData,
)
from backend.app.schemas.road import VehicleType
from backend.app.services.polyline_utils import (
    decode_encoded_polyline,
    haversine_distance_meters,
    sample_coordinates_at_interval,
)

logger = logging.getLogger(__name__)


def parse_duration_string(duration_str: Optional[str]) -> float:
    """Parses Google duration string like '345s' to float seconds."""
    if not duration_str:
        return 0.0
    val = duration_str.rstrip("s")
    try:
        return float(val)
    except ValueError:
        return 0.0


async def fetch_candidate_routes_from_google(
    origin: Coordinate,
    destination: Coordinate,
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
) -> list[CandidateRoute]:
    """Calls Google Routes API v2 with alternative routes and traffic awareness."""
    api_key = settings.GOOGLE_ROUTES_API_KEY
    if not api_key:
        raise ValueError(
            "GOOGLE_ROUTES_API_KEY is not configured in .env. "
            "FlowSplit runs strictly in online mode and requires a valid Google Routes API key."
        )

    api_url = settings.GOOGLE_ROUTES_API_URL or "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,"
            "routes.description,routes.warnings,routes.legs.steps"
        ),
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {"latitude": origin.lat, "longitude": origin.lng}
            }
        },
        "destination": {
            "location": {
                "latLng": {"latitude": destination.lat, "longitude": destination.lng}
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": True,
        "languageCode": "en-US",
        "units": "METRIC",
    }

    async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(api_url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error("Google Routes API error (%d): %s", response.status_code, response.text)
            raise RuntimeError(
                f"Google Routes API request failed with status {response.status_code}: {response.text[:250]}"
            )

        data = response.json()
        raw_routes = data.get("routes", [])
        if not raw_routes:
            logger.warning("Google Routes API returned 0 routes for coordinates.")
            return []

        results: list[CandidateRoute] = []
        colors = ["#2563eb", "#dc2626", "#10b981", "#d97706", "#8b5cf6"]

        for idx, r in enumerate(raw_routes):
            encoded = r.get("polyline", {}).get("encodedPolyline", "")
            coords = decode_encoded_polyline(encoded)
            dist_meters = float(r.get("distanceMeters", 0.0))
            duration_sec = parse_duration_string(r.get("duration", "0s"))
            summary = r.get("description", f"Route Alternative {idx + 1}")

            # Extract road segments at sample intervals
            sampled = sample_coordinates_at_interval(
                coords,
                interval_meters=settings.SAMPLE_INTERVAL_METERS,
                max_samples=settings.MAX_IMAGE_BUDGET_PER_ROUTE,
            )

            segments: list[RoadSegmentData] = []
            for s_idx in range(len(sampled) - 1):
                start_c, bearing, _ = sampled[s_idx]
                end_c, _, _ = sampled[s_idx + 1]
                seg_len = haversine_distance_meters(start_c, end_c)

                seg = RoadSegmentData(
                    segment_id=f"rt-{idx}-seg-{s_idx}",
                    name=f"{summary} Sec {s_idx + 1}",
                    start_coord=start_c,
                    end_coord=end_c,
                    length_meters=max(20.0, round(seg_len, 1)),
                    functional_class="arterial" if idx == 0 else "residential",
                    nominal_capacity_vph=1200.0 if idx == 0 else 450.0,
                    current_volume_vph=0.0,
                    free_flow_speed_kmh=50.0 if idx == 0 else 35.0,
                    street_view_heading=bearing,
                )
                segments.append(seg)

            candidate = CandidateRoute(
                id=f"google-route-{idx}",
                name=summary,
                summary=f"{dist_meters / 1000.0:.1f} km, ~{duration_sec / 60.0:.1f} mins via Live Google Routes API",
                distance_meters=dist_meters,
                free_flow_duration_seconds=duration_sec,
                traffic_duration_seconds=duration_sec,
                encoded_polyline=encoded,
                coordinates=coords,
                segments=segments,
                is_simulated=False,
                suitability_score=70.0,
                confidence=0.85,
                route_color=colors[idx % len(colors)],
            )
            results.append(candidate)

        return results


async def get_candidate_routes(
    origin: Coordinate,
    destination: Coordinate,
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
) -> tuple[list[CandidateRoute], str, list[str]]:
    """Retrieves live candidate routes from Google Routes API.
    
    Offline fallback and predefined data are completely disabled.
    """
    warnings: list[str] = []

    if not settings.GOOGLE_ROUTES_API_KEY:
        raise ValueError(
            "GOOGLE_ROUTES_API_KEY is not configured in .env. "
            "Offline demo mode and predefined data are disabled. Live online mode requires an active key."
        )

    routes = await fetch_candidate_routes_from_google(origin, destination, vehicle_type)
    if not routes:
        raise ValueError(
            "Google Routes API returned zero paths between the specified origin and destination."
        )

    return routes, "google_routes_api", warnings
