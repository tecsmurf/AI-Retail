"""POS data import and mapping status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security import current_user, require_admin
from app.services import metrics, pos_service

router = APIRouter(prefix="/api/pos", tags=["POS"])
MAX_CSV_BYTES = 20 * 1024 * 1024


@router.post("/import")
async def import_pos(file: UploadFile = File(...), _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
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
        return await pos_service.import_csv(db, text, source="api")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/unassigned")
async def unassigned(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """POS store codes that are not mapped to any store yet."""
    return {"items": await metrics.unassigned_pos(db)}
