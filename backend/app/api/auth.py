"""Sign-in, sign-out and the caller's own account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import load_scope
from app.config import settings
from app.database import get_db, utcnow
from app.models.org import Organization, UserRegionAccess, UserStoreAccess
from app.models.user import ROLE_ADMIN, User
from app.schemas.auth import AuthOptions, LoginRequest, MeResponse, PasswordChange, ProfileUpdate, SignupRequest
from app.security import (
    SESSION_COOKIE,
    client_ip,
    current_user,
    hash_password,
    issue_token,
    rate_limiter,
    verify_password,
)
from app.services import audit
from app.services.orgs import unique_slug

router = APIRouter(prefix="/api/auth", tags=["Auth"])

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


async def user_grants(db: AsyncSession, user_ids) -> tuple[dict, dict]:
    """Explicit store and region grants per user id."""
    ids = list(user_ids)
    stores: dict = {i: [] for i in ids}
    regions: dict = {i: [] for i in ids}
    if ids:
        for uid, sid in (await db.execute(
            select(UserStoreAccess.user_id, UserStoreAccess.store_id).where(UserStoreAccess.user_id.in_(ids))
        )).all():
            stores[uid].append(sid)
        for uid, rid in (await db.execute(
            select(UserRegionAccess.user_id, UserRegionAccess.region_id).where(UserRegionAccess.user_id.in_(ids))
        )).all():
            regions[uid].append(rid)
    return stores, regions


async def me_response(db: AsyncSession, user: User) -> MeResponse:
    scope = await load_scope(db, user)
    org = await db.get(Organization, user.org_id)
    return MeResponse(
        id=user.id, email=user.email, full_name=user.full_name, role=user.role, is_active=user.is_active,
        created_at=user.created_at, last_login_at=user.last_login_at,
        store_ids=sorted(scope.store_ids, key=str), region_ids=sorted(scope.region_ids, key=str),
        org_id=user.org_id, org_name=org.name if org else "", all_stores=scope.all_stores,
        can_upload=scope.can_upload, is_admin=scope.is_admin,
    )


@router.post("/login", response_model=MeResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    rate_limiter.check(f"login:{client_ip(request)}", settings.login_rate_limit_per_minute, 60)
    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    ).scalar_one_or_none()
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        raise HTTPException(401, "Invalid email or password")
    user.last_login_at = utcnow()
    audit.record(db, "auth.login", user=user, request=request)
    _set_cookie(response, issue_token(user))
    return await me_response(db, user)


@router.get("/options", response_model=AuthOptions)
async def options():
    """What the sign-in page may offer (no secrets)."""
    return AuthOptions(signup_enabled=settings.signup_enabled)


@router.post("/signup", response_model=MeResponse, status_code=201)
async def signup(body: SignupRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Create a new company account and sign its first admin in.

    The company starts empty: it sees none of any other company's stores,
    users or data (every query is scoped to the user's organisation)."""
    if not settings.signup_enabled:
        raise HTTPException(403, "Sign-up is turned off. Ask your administrator for an account.")
    rate_limiter.check(f"signup:{client_ip(request)}", settings.signup_rate_limit_per_hour, 3600)
    email = body.email.strip().lower()
    if (await db.execute(select(User.id).where(func.lower(User.email) == email))).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    org = Organization(name=body.company_name.strip(), slug=unique_slug(body.company_name))
    db.add(org)
    await db.flush()
    user = User(email=email, full_name=(body.full_name or "").strip() or None, role=ROLE_ADMIN,
                password_hash=hash_password(body.password), org_id=org.id, last_login_at=utcnow())
    db.add(user)
    await db.flush()
    audit.record(db, "auth.signup", user=user, target_type="org", target_id=org.id,
                 details={"company": org.name}, request=request)
    _set_cookie(response, issue_token(user))
    return await me_response(db, user)


@router.patch("/me", response_model=MeResponse)
async def update_me(body: ProfileUpdate, request: Request, user: User = Depends(current_user),
                    db: AsyncSession = Depends(get_db)):
    user.full_name = (body.full_name or "").strip() or None
    audit.record(db, "auth.profile_update", user=user, target_type="user", target_id=user.id, request=request)
    return await me_response(db, user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await me_response(db, user)


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChange, request: Request, response: Response, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.session_version += 1  # sign out every other session
    audit.record(db, "auth.password_change", user=user, request=request)
    _set_cookie(response, issue_token(user))
    response.status_code = 204
    return response


@router.post("/logout-everywhere", status_code=204)
async def logout_everywhere(request: Request, response: Response, user: User = Depends(current_user),
                            db: AsyncSession = Depends(get_db)):
    user.session_version += 1
    audit.record(db, "auth.logout_everywhere", user=user, request=request)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response
