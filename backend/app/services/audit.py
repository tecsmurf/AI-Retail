"""Audit log: who changed what.

``record`` only adds a row to the caller's session, so the entry is committed
(or rolled back) together with the change it describes. Never put secrets,
passwords or tokens in ``details``.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import AuditLog
from app.models.user import User


def record(
    db: AsyncSession,
    action: str,
    *,
    user: Optional[User] = None,
    actor: Optional[str] = None,
    org_id: Optional[uuid.UUID] = None,
    target_type: Optional[str] = None,
    target_id: Any = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    from app.security import client_ip

    entry = AuditLog(
        org_id=org_id or (user.org_id if user else None),
        user_id=user.id if user else None,
        actor=(actor or (user.email if user else "system"))[:320],
        action=action,
        target_type=target_type,
        target_id=str(target_id)[:80] if target_id is not None else None,
        details=details or None,
        ip=client_ip(request)[:64] if request is not None else None,
    )
    db.add(entry)
    return entry
