"""Tests for the API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client):
    """Test root health endpoint."""
    async with client as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PurpleSol API"
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_detailed(client):
    """Test detailed health endpoint."""
    async with client as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
