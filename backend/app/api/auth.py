"""Authentication and user management."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, utcnow
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChange, UserCreate, UserResponse
from app.security import (
    SESSION_COOKIE,
    client_ip,
    current_user,
    hash_password,
    issue_token,
    rate_limiter,
    require_admin,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])
users_router = APIRouter(prefix="/api/users", tags=["Users"])

# Constant-time-ish response for unknown emails.
_DUMMY_HASH = hash_password("dummy-password-not-used")


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    rate_limiter.check(f"login:{client_ip(request)}", settings.login_rate_limit_per_minute, 60)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    ).scalar_one_or_none()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        raise HTTPException(401, "Invalid email or password")
    user.last_login_at = utcnow()
    _set_cookie(response, issue_token(user))
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChange, response: Response, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1  # sign out every other session
    _set_cookie(response, issue_token(user))
    response.status_code = 204
    return response


@router.post("/logout-everywhere", status_code=204)
async def logout_everywhere(response: Response, user: User = Depends(current_user)):
    user.session_version += 1
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@users_router.get("", response_model=List[UserResponse])
async def list_users(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return list((await db.execute(select(User).order_by(User.created_at))).scalars().all())


@users_router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    exists = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "A user with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), role=body.role, is_active=True,
                session_version=1)
    db.add(user)
    await db.flush()
    return user


@users_router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    user.is_active = False
    user.session_version += 1
    return user
