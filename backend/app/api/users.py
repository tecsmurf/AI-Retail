"""Team management: an organisation's admins manage its users.

Every route here is limited to the caller's own organisation; a user id from
another organisation answers 404.
"""

from __future__ import annotations

import uuid
from typing import Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, require_org_admin
from app.api.auth import user_grants
from app.database import get_db
from app.models.org import Region, UserRegionAccess, UserStoreAccess
from app.models.store import Store
from app.models.user import ORG_WIDE_ROLES, ROLE_ADMIN, User
from app.schemas.auth import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.security import hash_password
from app.services import audit

router = APIRouter(prefix="/api/users", tags=["Users"])


def _response(user: User, stores: dict, regions: dict) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, is_active=user.is_active,
        created_at=user.created_at, last_login_at=user.last_login_at,
        store_ids=sorted(stores.get(user.id, []), key=str), region_ids=sorted(regions.get(user.id, []), key=str),
    )


async def _one(db: AsyncSession, user: User) -> UserResponse:
    stores, regions = await user_grants(db, [user.id])
    return _response(user, stores, regions)


async def _target(db: AsyncSession, scope: Scope, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if not user or user.org_id != scope.org_id:
        raise HTTPException(404, "User not found")
    return user


async def _set_grants(db: AsyncSession, scope: Scope, user: User, store_ids: Optional[Iterable[uuid.UUID]],
                      region_ids: Optional[Iterable[uuid.UUID]]) -> None:
    """Replace the user's grants. HQ roles hold none (they see everything)."""
    if user.role in ORG_WIDE_ROLES:
        store_ids, region_ids = [], []
    if store_ids is not None:
        wanted = set(store_ids)
        if wanted:
            found = {s for (s,) in (await db.execute(
                select(Store.id).where(Store.org_id == scope.org_id, Store.id.in_(wanted))
            )).all()}
            if found != wanted:
                raise HTTPException(422, "One or more stores were not found")
        await db.execute(delete(UserStoreAccess).where(UserStoreAccess.user_id == user.id))
        db.add_all([UserStoreAccess(user_id=user.id, store_id=s) for s in wanted])
    if region_ids is not None:
        wanted = set(region_ids)
        if wanted:
            found = {r for (r,) in (await db.execute(
                select(Region.id).where(Region.org_id == scope.org_id, Region.id.in_(wanted))
            )).all()}
            if found != wanted:
                raise HTTPException(422, "One or more regions were not found")
        await db.execute(delete(UserRegionAccess).where(UserRegionAccess.user_id == user.id))
        db.add_all([UserRegionAccess(user_id=user.id, region_id=r) for r in wanted])
    await db.flush()


async def _other_active_admins(db: AsyncSession, scope: Scope, user: User) -> int:
    return (await db.execute(
        select(func.count()).select_from(User).where(
            User.org_id == scope.org_id, User.role == ROLE_ADMIN, User.is_active.is_(True), User.id != user.id)
    )).scalar() or 0


@router.get("", response_model=List[UserResponse])
async def list_users(scope: Scope = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    users = list((await db.execute(
        select(User).where(User.org_id == scope.org_id).order_by(User.created_at)
    )).scalars().all())
    stores, regions = await user_grants(db, [u.id for u in users])
    return [_response(u, stores, regions) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, request: Request, scope: Scope = Depends(require_org_admin),
                      db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    # Emails are unique across all organisations (one login, one company).
    if (await db.execute(select(User.id).where(func.lower(User.email) == email))).first():
        raise HTTPException(409, "A user with this email already exists")
    user = User(email=email, full_name=(body.full_name or "").strip() or None,
                password_hash=hash_password(body.password), role=body.role, is_active=True, session_version=1,
                org_id=scope.org_id)
    db.add(user)
    await db.flush()
    await _set_grants(db, scope, user, body.store_ids, body.region_ids)
    audit.record(db, "user.create", user=scope.user, target_type="user", target_id=user.id,
                 details={"email": email, "role": user.role}, request=request)
    return await _one(db, user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, body: UserUpdate, request: Request,
                      scope: Scope = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    user = await _target(db, scope, user_id)
    changes = body.model_dump(exclude_unset=True)
    losing_admin = user.role == ROLE_ADMIN and (
        ("role" in changes and changes["role"] != ROLE_ADMIN) or changes.get("is_active") is False
    )
    if losing_admin:
        if user.id == scope.user.id:
            raise HTTPException(400, "You cannot remove your own administrator access")
        if not await _other_active_admins(db, scope, user):
            raise HTTPException(400, "An organisation needs at least one active administrator")
    if "full_name" in changes:
        user.full_name = (changes["full_name"] or "").strip() or None
    if changes.get("role"):
        user.role = changes["role"]
    if changes.get("is_active") is not None and changes["is_active"] != user.is_active:
        user.is_active = changes["is_active"]
        user.session_version += 1
    await _set_grants(db, scope, user, changes.get("store_ids"), changes.get("region_ids"))
    logged = {k: ([str(x) for x in v] if isinstance(v, list) else v) for k, v in changes.items()}
    audit.record(db, "user.update", user=scope.user, target_type="user", target_id=user.id,
                 details={"email": user.email, "changes": logged}, request=request)
    return await _one(db, user)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: uuid.UUID, request: Request, scope: Scope = Depends(require_org_admin),
                          db: AsyncSession = Depends(get_db)):
    user = await _target(db, scope, user_id)
    if user.id == scope.user.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    user.is_active = False
    user.session_version += 1
    audit.record(db, "user.deactivate", user=scope.user, target_type="user", target_id=user.id,
                 details={"email": user.email}, request=request)
    return await _one(db, user)


@router.post("/{user_id}/password", status_code=204)
async def reset_password(user_id: uuid.UUID, body: PasswordReset, request: Request,
                         scope: Scope = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    """Set a new password for a team member and sign them out everywhere."""
    user = await _target(db, scope, user_id)
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1
    audit.record(db, "user.password_reset", user=scope.user, target_type="user", target_id=user.id,
                 details={"email": user.email}, request=request)
