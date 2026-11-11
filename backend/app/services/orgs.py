"""Organisation helpers."""

from __future__ import annotations

import re
import secrets
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import DEFAULT_ORG_ID, DEFAULT_ORG_NAME, DEFAULT_ORG_SLUG, Organization


async def ensure_default_org(db: AsyncSession) -> Organization:
    """The migration creates the default organisation; databases built with
    ``create_all`` (tests, DB_AUTO_CREATE) need it created here."""
    org = await db.get(Organization, DEFAULT_ORG_ID)
    if org is None:
        org = Organization(id=DEFAULT_ORG_ID, name=DEFAULT_ORG_NAME, slug=DEFAULT_ORG_SLUG)
        db.add(org)
        await db.flush()
    return org


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "org"


def unique_slug(name: str) -> str:
    """Slug with a short random suffix, for organisations created by sign-up."""
    return f"{slugify(name)[:50]}-{secrets.token_hex(3)}"


async def org_by_slug(db: AsyncSession, slug: str) -> Optional[Organization]:
    return (await db.execute(select(Organization).where(Organization.slug == slug.strip().lower()))).scalar_one_or_none()


async def get_org(db: AsyncSession, org_id: uuid.UUID) -> Optional[Organization]:
    return await db.get(Organization, org_id)
