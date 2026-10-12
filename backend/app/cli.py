"""Administrative commands.

    python -m app.cli create-user EMAIL --role admin     # prompts for the password
    python -m app.cli reset-password EMAIL               # also signs the user out everywhere
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import func, select

from app.database import async_session
from app.models.user import ROLES, User
from app.security import hash_password


def _password() -> str:
    pw = os.environ.get("PURPLESOL_NEW_PASSWORD") or getpass.getpass("Password (min 10 chars): ")
    if len(pw) < 10:
        sys.exit("Password must be at least 10 characters")
    return pw


async def create_user(email: str, role: str) -> None:
    async with async_session() as db:
        if (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none():
            sys.exit(f"User {email} already exists")
        db.add(User(email=email.lower(), password_hash=hash_password(_password()), role=role, is_active=True))
        await db.commit()
    print(f"Created {role} {email}")


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
    parser = argparse.ArgumentParser(description="PurpleSol admin commands")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("email")
    c.add_argument("--role", choices=ROLES, default="viewer")
    r = sub.add_parser("reset-password")
    r.add_argument("email")
    args = parser.parse_args()
    if args.cmd == "create-user":
        asyncio.run(create_user(args.email, args.role))
    else:
        asyncio.run(reset_password(args.email))


if __name__ == "__main__":
    main()
