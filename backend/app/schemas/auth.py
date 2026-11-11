"""Authentication, user and organisation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["admin", "viewer", "regional_manager", "store_manager"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    # Explicit grants (empty for the two HQ roles, which see every store).
    store_ids: List[uuid.UUID] = Field(default_factory=list)
    region_ids: List[uuid.UUID] = Field(default_factory=list)


class MeResponse(UserResponse):
    """The signed-in user plus what they are allowed to see and do."""

    org_id: uuid.UUID
    org_name: str
    all_stores: bool
    can_upload: bool
    is_admin: bool


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=320, pattern=EMAIL_PATTERN)
    password: str = Field(..., min_length=10, max_length=256)
    full_name: Optional[str] = Field(None, max_length=200)
    role: Role = "viewer"
    store_ids: List[uuid.UUID] = Field(default_factory=list, max_length=2000)
    region_ids: List[uuid.UUID] = Field(default_factory=list, max_length=500)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    store_ids: Optional[List[uuid.UUID]] = Field(None, max_length=2000)
    region_ids: Optional[List[uuid.UUID]] = Field(None, max_length=500)


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=10, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=10, max_length=256)


class OrgUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RegionIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
