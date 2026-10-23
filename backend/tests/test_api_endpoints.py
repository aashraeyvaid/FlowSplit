"""Integration and unit tests for FastAPI endpoints in strict online mode."""

from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport, Response
from backend.app.main import app
from backend.app.config import settings
from backend.app.schemas.road import VisionRoadAnalysis, ObstructionLevel, PedestrianContext


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mode"] == "online_only"
        assert data["capabilities"]["offline_demo_available"] is False


@pytest.mark.asyncio
async def test_public_config_redaction():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/config/public")
        assert response.status_code == 200
        data = response.json()
        # Verify URLs are provided and secrets not exposed
        assert "google_maps_js_api_url" in data
        assert "google_routes_api_url" in data
        assert "google_routes_api_key" not in data
        assert "gemini_api_key" not in data
        assert data["online_mode_only"] is True
        assert data["demo_mode_active"] is False


@pytest.mark.asyncio
async def test_candidates_endpoint_requires_online_key():
    """Without GOOGLE_ROUTES_API_KEY in .env, request must return 503 Service Unavailable."""
    with patch.object(settings, "GOOGLE_ROUTES_API_KEY", None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "origin": {"lat": 37.7749, "lng": -122.4494},
                "destination": {"lat": 37.7915, "lng": -122.3999},
            }
            response = await ac.post("/api/routes/candidates", json=payload)
            assert response.status_code == 503
            assert "GOOGLE_ROUTES_API_KEY" in response.json()["detail"]


@pytest.mark.asyncio
async def test_candidates_invalid_coordinates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "origin": {"lat": 95.0, "lng": -122.4494},  # Invalid lat > 90
            "destination": {"lat": 37.7915, "lng": -122.3999},
        }
        response = await ac.post("/api/routes/candidates", json=payload)
        assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_analyze_and_select_endpoints_online():
    """Tests live online candidate retrieval, analysis, and selection using mock HTTP transport."""
    from backend.app.schemas.route import CandidateRoute, Coordinate, RoadSegmentData

    c1 = CandidateRoute(
        id="live-1",
        name="I-80 Central Corridor",
        summary="4.5 km, ~8 mins via Live Google Routes API",
        distance_meters=4500,
        free_flow_duration_seconds=480,
        traffic_duration_seconds=480,
        encoded_polyline="_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        coordinates=[Coordinate(lat=37.77, lng=-122.44), Coordinate(lat=37.79, lng=-122.39)],
        segments=[
            RoadSegmentData(
                segment_id="live-1-seg-0",
                name="I-80 Section 1",
                start_coord=Coordinate(lat=37.77, lng=-122.44),
                end_coord=Coordinate(lat=37.79, lng=-122.39),
                length_meters=4500.0,
                functional_class="arterial",
                nominal_capacity_vph=1800.0,
                current_volume_vph=0.0,
                free_flow_speed_kmh=60.0,
            )
        ],
        is_simulated=False,
        suitability_score=80.0,
        confidence=0.9,
    )
    c2 = CandidateRoute(
        id="live-2",
        name="Market St Boulevard",
        summary="4.2 km, ~8.5 mins via Live Google Routes API",
        distance_meters=4200,
        free_flow_duration_seconds=510,
        traffic_duration_seconds=510,
        encoded_polyline="_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        coordinates=[Coordinate(lat=37.77, lng=-122.44), Coordinate(lat=37.79, lng=-122.39)],
        segments=[
            RoadSegmentData(
                segment_id="live-2-seg-0",
                name="Market St Section 1",
                start_coord=Coordinate(lat=37.77, lng=-122.44),
                end_coord=Coordinate(lat=37.79, lng=-122.39),
                length_meters=4200.0,
                functional_class="arterial",
                nominal_capacity_vph=1200.0,
                current_volume_vph=0.0,
                free_flow_speed_kmh=45.0,
            )
        ],
        is_simulated=False,
        suitability_score=75.0,
        confidence=0.85,
    )

    with patch.object(settings, "GOOGLE_ROUTES_API_KEY", "test-live-key"), \
         patch("backend.app.services.google_routes.fetch_candidate_routes_from_google", return_value=[c1, c2]):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Fetch live candidates
            c_res = await ac.post("/api/routes/candidates", json={
                "origin": {"lat": 37.7749, "lng": -122.4494},
                "destination": {"lat": 37.7915, "lng": -122.3999},
            })
            assert c_res.status_code == 200
            candidates = c_res.json()["candidates"]
            assert len(candidates) == 2
            assert c_res.json()["provider"] == "google_routes_api"
            assert c_res.json()["is_demo"] is False

            # 2. Analyze routes online
            a_res = await ac.post("/api/routes/analyze", json={
                "candidates": candidates,
            })
            assert a_res.status_code == 200
            analyzed = a_res.json()["analyzed_candidates"]
            assert len(analyzed) == 2

            # 3. Select best route
            s_res = await ac.post("/api/routes/select", json={
                "candidates": analyzed,
            })
            assert s_res.status_code == 200
            decision = s_res.json()
            assert "selected_route_id" in decision
            assert len(decision["candidate_breakdowns"]) == 2


@pytest.mark.asyncio
async def test_simulation_run_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/simulation/run", json={"total_hourly_trips": 900})
        assert response.status_code == 200
        data = response.json()
        assert data["baseline_result"]["overloaded_segments_count"] > 0
        assert data["flowsplit_result"]["overloaded_segments_count"] == 0
        assert data["queue_reduction_percent"] > 50.0


@pytest.mark.asyncio
async def test_road_analyze_and_retrieve_online():
    """Tests road analysis online via Gemini and in-memory persistence retrieval."""
    mock_vision = VisionRoadAnalysis(
        usable_road_width_meters=9.5,
        visible_lane_count=2,
        parking_obstruction=ObstructionLevel.LOW,
        visible_obstacles=[],
        pedestrian_cyclist_activity=PedestrianContext.LOW,
        visible_road_restrictions=[],
        confidence=0.92,
        evidence_notes=["Wide 2-lane road analyzed online."],
    )

    with patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch("backend.app.api.roads.analyze_road_imagery_with_gemini", return_value=(mock_vision, "gemini-2.5-flash")):

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            req = {
                "lat": 37.7749,
                "lng": -122.4194,
                "road_name": "Market Street Corridor",
                "vehicle_type": "passenger_car",
            }
            res = await ac.post("/api/roads/analyze", json=req)
            assert res.status_code == 200
            data = res.json()
            assert "road_id" in data
            assert data["suitability"]["suitability_score"] > 60.0

            road_id = data["road_id"]
            get_res = await ac.get(f"/api/roads/{road_id}")
            assert get_res.status_code == 200
            get_data = get_res.json()
            assert get_data["road_id"] == road_id
            assert get_data["road_name"] == "Market Street Corridor"


def test_no_sqlite_file_created():
    """Verify that flowsplit.db does not exist and is never created."""
    db_file = Path("/home/adityasharma/gdg_split/flowsplit.db")
    assert not db_file.exists(), "flowsplit.db SQLite file must not exist."
