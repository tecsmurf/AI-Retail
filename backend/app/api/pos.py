"""POS data import and mapping status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, get_scope, require_org_admin
from app.database import get_db
from app.services import audit, metrics, pos_service

router = APIRouter(prefix="/api/pos", tags=["POS"])
MAX_CSV_BYTES = 20 * 1024 * 1024


@router.post("/import")
async def import_pos(request: Request, file: UploadFile = File(...), scope: Scope = Depends(require_org_admin),
                     db: AsyncSession = Depends(get_db)):
    """Import a POS CSV. Re-importing the same file inserts nothing (unique on
    store code, order id, product id). Map the CSV's store code to a store by
    setting the store's ``pos_store_code``."""
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV too large (max 20 MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(415, "CSV must be UTF-8")
    try:
        result = await pos_service.import_csv(db, text, source="api", org_id=scope.org_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    audit.record(db, "pos.import", user=scope.user, target_type="pos",
                 details={"filename": (file.filename or "")[:200], "inserted": result["inserted"],
                          "duplicates_skipped": result["duplicates_skipped"], "error_count": result["error_count"]},
                 request=request)
    return result


@router.get("/unassigned")
async def unassigned(scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)):
    """POS store codes that are not mapped to any store yet (HQ roles only see them)."""
    if not scope.all_stores:
        return {"items": []}
    return {"items": await metrics.unassigned_pos(db, scope.org_id)}
