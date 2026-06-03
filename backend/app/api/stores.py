"""Store API endpoints."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.store_service import StoreService
from app.services.analytics_service import AnalyticsService
from app.services.anomaly_service import AnomalyService
from app.schemas.store import StoreResponse, StoreOverview, CameraResponse, ZoneResponse

router = APIRouter(prefix="/api/stores", tags=["Stores"])


@router.get("", response_model=List[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db)):
    """List all active stores."""
    service = StoreService(db)
    stores = await service.list_stores()

    result = []
    for store in stores:
        cameras = await service.get_cameras(store.id)
        zones = await service.get_zones(store.id)
        store_dict = StoreResponse(
            id=store.id,
            store_code=store.store_code,
            name=store.name,
            address=store.address,
            city=store.city,
            layout_image_url=store.layout_image_url,
            layout_width=store.layout_width,
            layout_height=store.layout_height,
            is_active=store.is_active,
            camera_count=len(cameras),
            zone_count=len(zones),
            created_at=store.created_at,
        )
        result.append(store_dict)

    return result


@router.get("/{store_id}", response_model=StoreOverview)
async def get_store_overview(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get store overview with key metrics."""
    store_svc = StoreService(db)
    store = await store_svc.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    analytics_svc = AnalyticsService(db)
    anomaly_svc = AnomalyService(db)

    footfall = await analytics_svc.get_footfall(store_id)
    conversion = await analytics_svc.get_conversion_analytics(store_id)
    revenue = await analytics_svc.get_revenue_analytics(store_id)
    alerts = await anomaly_svc.get_alerts(store_id, unread_only=True)

    store_resp = StoreResponse(
        id=store.id,
        store_code=store.store_code,
        name=store.name,
        address=store.address,
        city=store.city,
        layout_image_url=store.layout_image_url,
        layout_width=store.layout_width,
        layout_height=store.layout_height,
        is_active=store.is_active,
        camera_count=len(store.cameras),
        zone_count=len(store.zones),
        created_at=store.created_at,
    )

    return StoreOverview(
        store=store_resp,
        total_visitors_today=footfall["visitors_today"],
        conversion_rate=conversion["overall_conversion_rate"],
        revenue_today=revenue["total_revenue"],
        peak_hour=footfall["peak_hour"],
        active_alerts=len(alerts),
    )


@router.get("/{store_id}/cameras", response_model=List[CameraResponse])
async def get_cameras(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List cameras for a store."""
    service = StoreService(db)
    cameras = await service.get_cameras(store_id)
    return cameras


@router.get("/{store_id}/zones", response_model=List[ZoneResponse])
async def get_zones(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List zones for a store."""
    service = StoreService(db)
    zones = await service.get_zones(store_id)
    return zones
