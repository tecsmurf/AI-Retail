"""Who may see which stores.

Every signed-in user belongs to one organisation. HQ roles (admin, viewer) see
all of its stores. Regional managers see the stores of their regions, store
managers the stores they were given (either role may hold both kinds of
grant). A store outside the caller's scope answers 404, exactly like a store
that does not exist, so ids cannot be probed across organisations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.org import UserRegionAccess, UserStoreAccess
from app.models.store import Camera, Store
from app.models.user import ORG_WIDE_ROLES, ROLE_ADMIN, UPLOAD_ROLES, User
from app.security import current_user


@dataclass(frozen=True)
class Scope:
    user: User
    org_id: uuid.UUID
    all_stores: bool
    is_admin: bool
    can_upload: bool
    # Filled only when all_stores is False.
    store_ids: FrozenSet[uuid.UUID] = field(default_factory=frozenset)
    region_ids: FrozenSet[uuid.UUID] = field(default_factory=frozenset)
    direct_store_ids: FrozenSet[uuid.UUID] = field(default_factory=frozenset)

    def allows(self, store: Store) -> bool:
        if store.org_id != self.org_id:
            return False
        return self.all_stores or store.id in self.store_ids

    def filter_stores(self, query):
        """Restrict a query that selects from ``stores`` to this scope."""
        query = query.where(Store.org_id == self.org_id)
        if not self.all_stores:
            query = query.where(Store.id.in_(self.store_ids))
        return query


async def load_scope(db: AsyncSession, user: User) -> Scope:
    is_admin = user.role == ROLE_ADMIN
    can_upload = user.role in UPLOAD_ROLES
    if user.role in ORG_WIDE_ROLES:
        return Scope(user=user, org_id=user.org_id, all_stores=True, is_admin=is_admin, can_upload=can_upload)
    region_ids = frozenset(
        r for (r,) in (await db.execute(
            select(UserRegionAccess.region_id).where(UserRegionAccess.user_id == user.id)
        )).all()
    )
    direct = frozenset(
        s for (s,) in (await db.execute(
            select(UserStoreAccess.store_id)
            .join(Store, Store.id == UserStoreAccess.store_id)
            .where(UserStoreAccess.user_id == user.id, Store.org_id == user.org_id)
        )).all()
    )
    via_region: set = set()
    if region_ids:
        via_region = {
            s for (s,) in (await db.execute(
                select(Store.id).where(Store.org_id == user.org_id, Store.region_id.in_(region_ids))
            )).all()
        }
    return Scope(
        user=user, org_id=user.org_id, all_stores=False, is_admin=False, can_upload=can_upload,
        store_ids=frozenset(direct | via_region), region_ids=region_ids, direct_store_ids=direct,
    )


async def get_scope(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Scope:
    return await load_scope(db, user)


async def require_org_admin(scope: Scope = Depends(get_scope)) -> Scope:
    if not scope.is_admin:
        raise HTTPException(403, "Administrator role required")
    return scope


async def require_uploader(scope: Scope = Depends(get_scope)) -> Scope:
    if not scope.can_upload:
        raise HTTPException(403, "Your role cannot upload or process recordings")
    return scope


async def store_in_scope(db: AsyncSession, scope: Scope, store_id: Optional[uuid.UUID]) -> Store:
    store = await db.get(Store, store_id) if store_id else None
    if store is None or not scope.allows(store):
        raise HTTPException(404, "Store not found")
    return store


async def camera_in_scope(db: AsyncSession, scope: Scope, camera_id: Optional[uuid.UUID]) -> Camera:
    camera = await db.get(Camera, camera_id) if camera_id else None
    if camera is None:
        raise HTTPException(404, "Camera not found")
    store = await db.get(Store, camera.store_id)
    if store is None or not scope.allows(store):
        raise HTTPException(404, "Camera not found")
    return camera


async def scoped_store_ids(db: AsyncSession, scope: Scope) -> List[uuid.UUID]:
    """Ids of every store the caller may see (all of the organisation's for HQ roles)."""
    if not scope.all_stores:
        return list(scope.store_ids)
    return [s for (s,) in (await db.execute(select(Store.id).where(Store.org_id == scope.org_id))).all()]
