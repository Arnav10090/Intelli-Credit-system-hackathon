"""
tests/conftest.py
──────────────────────────────────────────────────────────────────────────────
Shared pytest fixtures and configuration for Intelli-Credit test suite.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Ensure backend is importable from all test files
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (skip with -m 'not slow')")
    config.addinivalue_line("markers", "integration: marks tests requiring the full app stack")
    config.addinivalue_line("markers", "unit: marks pure unit tests (no DB, no HTTP)")


# ── Database Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
async def db_session():
    """Provide a test database session."""
    from backend.database import Base, get_session
    from backend.config import settings
    
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


# ── HTTP Client Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
async def client(db_session):
    """Provide an async HTTP client for API testing."""
    from backend.main import app
    from backend.database import get_session
    
    # Override the database session dependency
    async def override_get_session():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise
    
    app.dependency_overrides[get_session] = override_get_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


# ── Demo Data Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
async def demo_case_id(db_session):
    """Create a demo case and return its ID."""
    from backend.database import Case
    from uuid import uuid4
    
    case_id = str(uuid4())
    case = Case(
        id=case_id,
        company_name="Test Company Ltd",
        company_cin="U12345MH2020PLC123456",
        status="created",
    )
    db_session.add(case)
    await db_session.commit()
    
    return case_id
