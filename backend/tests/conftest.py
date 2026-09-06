"""
Shared pytest fixtures for the backend test suite.

The app defaults to an in-memory SQLite database
(``sqlite+aiosqlite:///:memory:``) backed by SQLAlchemy's ``StaticPool``,
which keeps a single physical connection alive for the whole process -- so
tables created once here are visible to every test/session afterwards.
"""

import pytest

from app.db.base import Base
from app.db.database import engine


@pytest.fixture(autouse=True, scope="session")
async def _create_test_schema():
    """Create all tables once before the test session runs."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
