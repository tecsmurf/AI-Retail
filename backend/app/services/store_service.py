"""Store service — CRUD and business logic for stores, cameras, zones."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.store import Store, Camera, Zone
from app.schemas.store import StoreCreate


class StoreService:
    """Service for store-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Stores ───────────────────────────────────────────────────

    async def list_stores(self) -> List[Store]:
        """List all active stores."""
        result = await self.db.execute(
            select(Store)
            .where(Store.is_active.is_(True))
            .order_by(Store.store_code)
        )
        return list(result.scalars().all())

    async def get_store(self, store_id: uuid.UUID) -> Optional[Store]:
        """Get a store by ID with related cameras and zones."""
        result = await self.db.execute(
            select(Store)
            .where(Store.id == store_id)
            .options(
                selectinload(Store.cameras),
                selectinload(Store.zones),
            )
        )
        return result.scalar_one_or_none()

    async def get_store_by_code(self, store_code: str) -> Optional[Store]:
        """Get a store by its code."""
        result = await self.db.execute(
            select(Store).where(Store.store_code == store_code)
        )
        return result.scalar_one_or_none()

    async def create_store(self, data: StoreCreate) -> Store:
        """Create a new store."""
        store = Store(**data.model_dump())
        self.db.add(store)
        await self.db.flush()
        return store

    # ── Cameras ──────────────────────────────────────────────────

    async def get_cameras(self, store_id: uuid.UUID) -> List[Camera]:
        """Get all cameras for a store."""
        result = await self.db.execute(
            select(Camera)
            .where(Camera.store_id == store_id)
            .order_by(Camera.camera_code)
        )
        return list(result.scalars().all())

    # ── Zones ────────────────────────────────────────────────────

    async def get_zones(self, store_id: uuid.UUID) -> List[Zone]:
        """Get all zones for a store."""
        result = await self.db.execute(
            select(Zone)
            .where(Zone.store_id == store_id)
            .order_by(Zone.display_order)
        )
        return list(result.scalars().all())

    async def get_zone_by_code(
        self, store_id: uuid.UUID, zone_code: str
    ) -> Optional[Zone]:
        """Get a specific zone by code."""
        result = await self.db.execute(
            select(Zone)
            .where(Zone.store_id == store_id, Zone.zone_code == zone_code)
        )
        return result.scalar_one_or_none()
