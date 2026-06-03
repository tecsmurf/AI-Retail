"""Event API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.event_service import EventService
from app.schemas.event import EventCreate, EventResponse, EventFilter

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    event: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single business event."""
    service = EventService(db)
    try:
        result = await service.ingest_event(event)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", status_code=201)
async def create_batch_events(
    events: List[EventCreate],
    db: AsyncSession = Depends(get_db),
):
    """Ingest a batch of events."""
    service = EventService(db)
    count = await service.ingest_batch(events)
    return {"ingested": count, "total": len(events)}


@router.get("", response_model=List[EventResponse])
async def list_events(
    store_id: Optional[uuid.UUID] = Query(None),
    event_type: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    zone_name: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Query events with filters."""
    service = EventService(db)
    filters = EventFilter(
        store_id=store_id,
        event_type=event_type,
        customer_id=customer_id,
        zone_name=zone_name,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return await service.get_events(filters)


@router.get("/customer/{customer_id}", response_model=List[EventResponse])
async def get_customer_events(
    customer_id: str,
    store_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get all events for a specific customer."""
    service = EventService(db)
    return await service.get_events_for_customer(store_id, customer_id)
