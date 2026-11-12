"""The caller's organisation: name, regions, the HQ comparison and the audit log."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, get_scope, require_org_admin
from app.database import get_db
from app.models.org import AuditLog, Organization, Region
from app.models.store import Store
from app.models.user import User
from app.schemas.auth import OrgUpdate, RegionIn
from app.services import audit, org_metrics
from app.services.timerange import parse_sources

router = APIRouter(prefix="/api/org", tags=["Organisation"])


@router.get("")
async def get_org(scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)):
    org = await db.get(Organization, scope.org_id)
    stores = (await db.execute(scope.filter_stores(select(func.count()).select_from(Store)))).scalar() or 0
    users = (await db.execute(
        select(func.count()).select_from(User).where(User.org_id == scope.org_id, User.is_active.is_(True))
    )).scalar() or 0
    return {"id": str(org.id), "name": org.name, "slug": org.slug, "store_count": stores,
            "user_count": users if scope.is_admin else None}


@router.patch("")
async def update_org(body: OrgUpdate, request: Request, scope: Scope = Depends(require_org_admin),
                     db: AsyncSession = Depends(get_db)):
    org = await db.get(Organization, scope.org_id)
    old = org.name
    org.name = body.name.strip()
    audit.record(db, "org.update", user=scope.user, target_type="org", target_id=org.id,
                 details={"from": old, "to": org.name}, request=request)
    return {"id": str(org.id), "name": org.name, "slug": org.slug}


# ── Regions ──────────────────────────────────────────────────────


def _region(r: Region, store_count: int = 0) -> dict:
    return {"id": str(r.id), "name": r.name, "store_count": store_count}


async def _region_or_404(db: AsyncSession, scope: Scope, region_id: uuid.UUID) -> Region:
    region = await db.get(Region, region_id)
    if not region or region.org_id != scope.org_id:
        raise HTTPException(404, "Region not found")
    return region


async def _name_taken(db: AsyncSession, scope: Scope, name: str, ignore: Optional[uuid.UUID] = None) -> bool:
    q = select(Region.id).where(Region.org_id == scope.org_id, func.lower(Region.name) == name.lower())
    if ignore:
        q = q.where(Region.id != ignore)
    return (await db.execute(q)).first() is not None


@router.get("/regions")
async def list_regions(scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)):
    """Regions of the organisation. Non-HQ users get only regions that contain a store they can see."""
    counts = dict((await db.execute(
        scope.filter_stores(select(Store.region_id, func.count()).where(Store.region_id.is_not(None)))
        .group_by(Store.region_id)
    )).all())
    regions = (await db.execute(
        select(Region).where(Region.org_id == scope.org_id).order_by(Region.name)
    )).scalars().all()
    return {"items": [_region(r, counts.get(r.id, 0)) for r in regions if scope.all_stores or r.id in counts
                      or r.id in scope.region_ids]}


@router.post("/regions", status_code=201)
async def create_region(body: RegionIn, request: Request, scope: Scope = Depends(require_org_admin),
                        db: AsyncSession = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Region name is required")
    if await _name_taken(db, scope, name):
        raise HTTPException(409, "A region with this name already exists")
    region = Region(org_id=scope.org_id, name=name)
    db.add(region)
    await db.flush()
    audit.record(db, "region.create", user=scope.user, target_type="region", target_id=region.id,
                 details={"name": name}, request=request)
    return _region(region)


@router.patch("/regions/{region_id}")
async def rename_region(region_id: uuid.UUID, body: RegionIn, request: Request,
                        scope: Scope = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    region = await _region_or_404(db, scope, region_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Region name is required")
    if await _name_taken(db, scope, name, ignore=region.id):
        raise HTTPException(409, "A region with this name already exists")
    old = region.name
    region.name = name
    audit.record(db, "region.update", user=scope.user, target_type="region", target_id=region.id,
                 details={"from": old, "to": name}, request=request)
    count = (await db.execute(select(func.count()).select_from(Store).where(Store.region_id == region.id))).scalar() or 0
    return _region(region, count)


@router.delete("/regions/{region_id}", status_code=204)
async def delete_region(region_id: uuid.UUID, request: Request, scope: Scope = Depends(require_org_admin),
                        db: AsyncSession = Depends(get_db)):
    """Delete a region. Its stores are kept and become unassigned."""
    region = await _region_or_404(db, scope, region_id)
    stores = (await db.execute(select(Store).where(Store.region_id == region.id))).scalars().all()
    for s in stores:  # explicit: SQLite does not enforce ON DELETE SET NULL by default
        s.region_id = None
    audit.record(db, "region.delete", user=scope.user, target_type="region", target_id=region.id,
                 details={"name": region.name, "stores_unassigned": len(stores)}, request=request)
    await db.flush()
    await db.delete(region)


# ── HQ comparison ────────────────────────────────────────────────


@router.get("/overview")
async def overview(
    start: Optional[date] = Query(None, description="First local date, inclusive"),
    end: Optional[date] = Query(None, description="Last local date, inclusive"),
    data: str = Query("real"),
    region_id: Optional[uuid.UUID] = None,
    scope: Scope = Depends(get_scope),
    db: AsyncSession = Depends(get_db),
):
    """Every store the caller may see, side by side, with region and chain totals."""
    return await org_metrics.org_overview(db, scope, start, end, parse_sources(data), region_id)


# ── Audit log ────────────────────────────────────────────────────


@router.get("/audit")
async def audit_log(
    action: Optional[str] = Query(None, max_length=80, description="Exact action or a prefix such as 'user.'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    scope: Scope = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).where(AuditLog.org_id == scope.org_id)
    if action:
        q = q.where(AuditLog.action.startswith(action, autoescape=True))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit).offset(offset))).scalars().all()
    return {
        "total": total, "limit": limit, "offset": offset,
        "items": [
            {"id": str(a.id), "created_at": a.created_at.isoformat() + "Z", "actor": a.actor, "action": a.action,
             "target_type": a.target_type, "target_id": a.target_id, "details": a.details, "ip": a.ip}
            for a in rows
        ],
    }
