"""Shared API dependencies."""


import uuid
from datetime import date
from typing import Optional, Sequence

from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Camera, Store
from app.services.timerange import TimeRange, parse_sources, resolve_range


async def get_store(store_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Store:
    store = await db.get(Store, store_id)
    if store is None:
        raise HTTPException(404, "Store not found")
    return store


async def get_camera(camera_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Camera:
    camera = await db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(404, "Camera not found")
    return camera


class RangeParams:
    def __init__(
        self,
        start: Optional[date] = Query(None, description="First local date (YYYY-MM-DD), inclusive"),
        end: Optional[date] = Query(None, description="Last local date (YYYY-MM-DD), inclusive"),
        data: str = Query("real", description="'real' (CV+API), 'all' (adds sample/demo/legacy), or a comma list"),
    ) -> None:
        self.start = start
        self.end = end
        self.data = data

    def resolve(self, store: Store) -> tuple[TimeRange, Sequence[str]]:
        return resolve_range(store.timezone, self.start, self.end), parse_sources(self.data)
