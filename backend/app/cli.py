"""Administrative commands.

    python -m app.cli create-org "Acme Retail" --slug acme   # a new customer (chain)
    python -m app.cli list-orgs
    python -m app.cli create-user EMAIL --role admin --org acme   # prompts for the password
    python -m app.cli reset-password EMAIL                   # also signs the user out everywhere

Without ``--org`` a user is created in the default organisation.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import func, select

from app.database import async_session
from app.models.org import DEFAULT_ORG_SLUG, Organization
from app.models.store import Store
from app.models.user import ROLES, User
from app.security import hash_password
from app.services.orgs import ensure_default_org, org_by_slug, slugify


def _password() -> str:
    pw = os.environ.get("PURPLESOL_NEW_PASSWORD") or getpass.getpass("Password (min 10 chars): ")
    if len(pw) < 10:
        sys.exit("Password must be at least 10 characters")
    return pw


async def create_org(name: str, slug: str | None) -> None:
    slug = slugify(slug or name)
    async with async_session() as db:
        if await org_by_slug(db, slug):
            sys.exit(f"Organisation '{slug}' already exists")
        db.add(Organization(name=name.strip(), slug=slug))
        await db.commit()
    print(f"Created organisation '{name}' (slug: {slug})")
    print(f"Next: python -m app.cli create-user EMAIL --role admin --org {slug}")


async def list_orgs() -> None:
    async with async_session() as db:
        await ensure_default_org(db)
        await db.commit()
        orgs = (await db.execute(select(Organization).order_by(Organization.created_at))).scalars().all()
        for org in orgs:
            stores = (await db.execute(select(func.count()).select_from(Store).where(Store.org_id == org.id))).scalar()
            users = (await db.execute(select(func.count()).select_from(User).where(User.org_id == org.id))).scalar()
            print(f"{org.slug:30} {org.name:40} stores={stores} users={users}")


async def create_user(email: str, role: str, org_slug: str) -> None:
    async with async_session() as db:
        if org_slug == DEFAULT_ORG_SLUG:
            org = await ensure_default_org(db)
        else:
            org = await org_by_slug(db, org_slug)
        if org is None:
            sys.exit(f"No organisation '{org_slug}'. Create it first: python -m app.cli create-org NAME --slug {org_slug}")
        if (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none():
            sys.exit(f"User {email} already exists")
        db.add(User(email=email.lower(), password_hash=hash_password(_password()), role=role, is_active=True,
                    org_id=org.id))
        await db.commit()
    print(f"Created {role} {email} in organisation '{org_slug}'")


async def reset_password(email: str) -> None:
    async with async_session() as db:
        user = (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none()
        if user is None:
            sys.exit(f"No user {email}")
        user.password_hash = hash_password(_password())
        user.session_version = (user.session_version or 1) + 1
        user.is_active = True
        await db.commit()
    print(f"Password reset for {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Footrail admin commands")
    sub = parser.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("create-org", help="add a customer organisation (chain)")
    o.add_argument("name")
    o.add_argument("--slug", help="short id used on the command line and for API ingestion (default: from the name)")
    sub.add_parser("list-orgs")
    c = sub.add_parser("create-user")
    c.add_argument("email")
    c.add_argument("--role", choices=ROLES, default="viewer")
    c.add_argument("--org", default=DEFAULT_ORG_SLUG, help="organisation slug (default: the default organisation)")
    r = sub.add_parser("reset-password")
    r.add_argument("email")
    args = parser.parse_args()
    if args.cmd == "create-org":
        asyncio.run(create_org(args.name, args.slug))
    elif args.cmd == "list-orgs":
        asyncio.run(list_orgs())
    elif args.cmd == "create-user":
        asyncio.run(create_user(args.email, args.role, args.org.strip().lower()))
    else:
        asyncio.run(reset_password(args.email))


if __name__ == "__main__":
    main()
