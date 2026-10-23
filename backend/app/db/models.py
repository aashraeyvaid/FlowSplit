"""SQLAlchemy persistent data models for road segments, observations, and route analyses."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    JSON,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    road_name = Column(String(256), nullable=True)
    functional_class = Column(String(64), default="residential")
    
    # Supported geometry representation: GeoJSON LineString / coordinates
    geometry_data = Column(JSON, nullable=True)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)
    end_lat = Column(Float, nullable=False)
    end_lng = Column(Float, nullable=False)
    length_meters = Column(Float, default=100.0)

    # Suitability & Vision Analysis
    suitability_score = Column(Float, nullable=False, default=50.0)
    confidence = Column(Float, nullable=False, default=0.5)
    feature_analysis = Column(JSON, nullable=True)  # Structured VisionRoadAnalysis + contributions
    penalties = Column(JSON, nullable=True)
    
    # Capacity & Speed
    nominal_capacity_vph = Column(Float, default=500.0)
    free_flow_speed_kmh = Column(Float, default=40.0)

    # Metadata & Provenance
    analysis_timestamp = Column(DateTime(timezone=True), default=utcnow)
    source = Column(String(128), default="gemini-vision")  # e.g. "gemini-2.5-flash", "survey", "offline_cache"
    status = Column(String(32), default="active")  # "active", "stale", "prohibited"

    # Relationships
    observations = relationship("RoadObservation", back_populates="segment", cascade="all, delete-orphan")


class RoadObservation(Base):
    __tablename__ = "road_observations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    road_segment_id = Column(String(64), ForeignKey("road_segments.id"), nullable=False, index=True)
    
    observation_type = Column(String(64), nullable=False)  # "vision_analysis", "traffic_sensor", "simulation_flow"
    observation_timestamp = Column(DateTime(timezone=True), default=utcnow)
    measured_or_estimated_value = Column(JSON, nullable=False)
    source = Column(String(128), default="street_view_gemini")
    confidence = Column(Float, default=0.8)

    segment = relationship("RoadSegment", back_populates="observations")


class RouteAnalysis(Base):
    __tablename__ = "route_analyses"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    origin_text = Column(String(512), nullable=False)
    destination_text = Column(String(512), nullable=False)
    origin_lat = Column(Float, nullable=False)
    origin_lng = Column(Float, nullable=False)
    destination_lat = Column(Float, nullable=False)
    destination_lng = Column(Float, nullable=False)

    candidate_summaries = Column(JSON, nullable=False)
    scoring_configuration = Column(JSON, nullable=True)
    selected_route_id = Column(String(128), nullable=False)
    selected_route_name = Column(String(256), nullable=False)
    decision_rationale = Column(Text, nullable=False)
    is_simulated = Column(String(16), default="false")

    analysis_timestamp = Column(DateTime(timezone=True), default=utcnow)


class RouteAllocationRecord(Base):
    __tablename__ = "route_allocations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(String(128), nullable=False, index=True)
    segment_ids = Column(JSON, nullable=False)
    allocated_timestamp = Column(DateTime(timezone=True), default=utcnow)
    weight = Column(Float, default=1.0)
