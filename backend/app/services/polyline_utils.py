"""Geospatial utilities for polyline decoding, distance calculations, headings, and sampling."""

import math
from typing import Optional
import polyline
from backend.app.schemas.route import Coordinate


def haversine_distance_meters(coord1: Coordinate, coord2: Coordinate) -> float:
    """Calculates great-circle distance between two coordinates in meters."""
    R = 6371000.0  # Earth's radius in meters
    lat1_rad = math.radians(coord1.lat)
    lat2_rad = math.radians(coord2.lat)
    dlat = math.radians(coord2.lat - coord1.lat)
    dlng = math.radians(coord2.lng - coord1.lng)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_bearing(coord1: Coordinate, coord2: Coordinate) -> float:
    """Calculates compass heading/bearing from coord1 to coord2 in degrees (0-360)."""
    lat1 = math.radians(coord1.lat)
    lat2 = math.radians(coord2.lat)
    dlng = math.radians(coord2.lng - coord1.lng)

    y = math.sin(dlng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def decode_encoded_polyline(encoded_str: str) -> list[Coordinate]:
    """Decodes Google encoded polyline string into list of Coordinates."""
    if not encoded_str:
        return []
    try:
        points = polyline.decode(encoded_str)
        return [Coordinate(lat=pt[0], lng=pt[1]) for pt in points]
    except Exception:
        return []


def sample_coordinates_at_interval(
    coords: list[Coordinate],
    interval_meters: float = 100.0,
    max_samples: int = 20,
) -> list[tuple[Coordinate, Optional[float], float]]:
    """Samples coordinates along a path at approximately interval_meters.

    Returns list of: (sampled_coordinate, heading_degrees, cumulative_distance_meters).
    """
    if not coords:
        return []
    if len(coords) == 1:
        return [(coords[0], None, 0.0)]

    samples: list[tuple[Coordinate, Optional[float], float]] = []
    cumulative_dist = 0.0
    last_sampled_dist = 0.0

    # Always include first point
    initial_bearing = calculate_bearing(coords[0], coords[1]) if len(coords) > 1 else None
    samples.append((coords[0], initial_bearing, 0.0))

    for i in range(len(coords) - 1):
        c1 = coords[i]
        c2 = coords[i + 1]
        step_dist = haversine_distance_meters(c1, c2)
        bearing = calculate_bearing(c1, c2)

        cumulative_dist += step_dist

        if (cumulative_dist - last_sampled_dist) >= interval_meters and len(samples) < max_samples:
            samples.append((c2, bearing, cumulative_dist))
            last_sampled_dist = cumulative_dist

    # Include final point if not already added
    if samples[-1][0] != coords[-1] and len(samples) < max_samples:
        samples.append((coords[-1], None, cumulative_dist))

    return samples
