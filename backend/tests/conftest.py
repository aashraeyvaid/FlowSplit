"""Pytest root configuration and fixtures."""

import pytest
from backend.app.db.session import init_db


@pytest.fixture(autouse=True)
async def initialize_database():
    """Initializes database tables before each test."""
    await init_db()
