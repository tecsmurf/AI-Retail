"""Analytics API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.analytics_service import AnalyticsService
from app.services.journey_service import JourneyService
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/{store_id}")
async def get_store_analytics(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive analytics for a store."""
    analytics = AnalyticsService(db)

    footfall = await analytics.get_footfall(store_id)
    conversion = await analytics.get_conversion_analytics(store_id)
    queue = await analytics.get_queue_analytics(store_id)
    zones = await analytics.get_zone_analytics(store_id)
    demographics = await analytics.get_demographics(store_id)
    revenue = await analytics.get_revenue_analytics(store_id)

    return {
        "store_id": str(store_id),
        "footfall": footfall,
        "conversion": conversion,
        "queue": queue,
        "zone_rankings": zones,
        "demographics": demographics,
        "revenue": revenue,
    }


@router.get("/{store_id}/footfall")
async def get_footfall(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get footfall analytics."""
    analytics = AnalyticsService(db)
    return await analytics.get_footfall(store_id)


@router.get("/{store_id}/zones")
async def get_zone_analytics(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get zone-level analytics."""
    analytics = AnalyticsService(db)
    return await analytics.get_zone_analytics(store_id)


@router.get("/{store_id}/conversion")
async def get_conversion(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get conversion funnel analytics."""
    analytics = AnalyticsService(db)
    return await analytics.get_conversion_analytics(store_id)


@router.get("/{store_id}/queue")
async def get_queue(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get queue analytics."""
    analytics = AnalyticsService(db)
    return await analytics.get_queue_analytics(store_id)


@router.get("/{store_id}/journeys")
async def get_journeys(
    store_id: uuid.UUID,
    journey_type: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get customer journeys."""
    service = JourneyService(db)
    journeys = await service.get_journeys(store_id, journey_type, limit)
    return journeys


@router.get("/{store_id}/journeys/analytics")
async def get_journey_analytics(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get journey analytics summary."""
    service = JourneyService(db)
    return await service.get_journey_analytics(store_id)


@router.get("/{store_id}/journeys/top-paths")
async def get_top_paths(
    store_id: uuid.UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get most common customer paths."""
    service = JourneyService(db)
    return await service.get_top_paths(store_id, limit)


@router.get("/{store_id}/anomalies")
async def get_anomalies(
    store_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get anomalies for a store."""
    service = AnomalyService(db)
    return await service.get_anomalies(store_id, limit)


@router.get("/{store_id}/alerts")
async def get_alerts(
    store_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get alerts for a store."""
    service = AnomalyService(db)
    return await service.get_alerts(store_id, limit, unread_only)


@router.post("/{store_id}/detect-anomalies")
async def trigger_anomaly_detection(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger anomaly detection for a store."""
    service = AnomalyService(db)
    anomalies = await service.detect_anomalies(store_id)
    return {"detected": len(anomalies), "anomalies": anomalies}


@router.get("/{store_id}/demographics")
async def get_demographics(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get demographic breakdown."""
    analytics = AnalyticsService(db)
    return await analytics.get_demographics(store_id)


@router.get("/{store_id}/revenue")
async def get_revenue(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get revenue analytics from POS data."""
    analytics = AnalyticsService(db)
    return await analytics.get_revenue_analytics(store_id)
