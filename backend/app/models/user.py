"""Dashboard users."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow
from app.models.org import DEFAULT_ORG_ID

# HQ roles see every store of their organisation; the other two see only the
# regions / stores they were given.
ROLE_ADMIN = "admin"                # HQ admin: everything, including setup and team
ROLE_VIEWER = "viewer"              # HQ viewer: read-only, all stores
ROLE_REGIONAL = "regional_manager"  # their regions; can upload recordings
ROLE_STORE = "store_manager"        # their stores; can upload recordings
ROLES = (ROLE_ADMIN, ROLE_VIEWER, ROLE_REGIONAL, ROLE_STORE)

ORG_WIDE_ROLES = (ROLE_ADMIN, ROLE_VIEWER)
UPLOAD_ROLES = (ROLE_ADMIN, ROLE_REGIONAL, ROLE_STORE)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, default=DEFAULT_ORG_ID
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(32), default=ROLE_VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bumping this invalidates every session issued to the user.
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
