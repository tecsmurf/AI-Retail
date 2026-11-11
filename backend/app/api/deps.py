"""Shared API dependencies."""


import uuid
from datetime import date
from typing import Optional, Sequence

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, camera_in_scope, get_scope, store_in_scope
from app.database import get_db
from app.models.store import Camera, Store
from app.services.timerange import TimeRange, parse_sources, resolve_range


async def get_store(store_id: uuid.UUID, scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)) -> Store:
    """The store, if the caller may see it (404 otherwise)."""
    return await store_in_scope(db, scope, store_id)


async def get_camera(camera_id: uuid.UUID, scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)) -> Camera:
    return await camera_in_scope(db, scope, camera_id)


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
