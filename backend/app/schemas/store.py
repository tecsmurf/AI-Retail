"""Store, camera and zone schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.cv.geometry import validate_line, validate_polygon

ZoneType = Literal["ENTRANCE", "SHELF", "DISPLAY", "QUEUE", "BILLING", "EXIT", "OTHER"]
CameraType = Literal["entrance", "zone", "billing", "other"]


def _check_tz(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in available_timezones():
        raise ValueError(f"unknown IANA time zone '{v}'")
    return v


class StoreCreate(BaseModel):
    store_code: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = Field(None, max_length=100)
    timezone: str = "Asia/Kolkata"
    pos_store_code: Optional[str] = Field(None, max_length=50)

    _tz = field_validator("timezone")(_check_tz)


class StoreUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = None
    pos_store_code: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

    _tz = field_validator("timezone")(_check_tz)


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_code: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    timezone: str
    pos_store_code: Optional[str] = None
    is_active: bool
    camera_count: int = 0
    zone_count: int = 0
    created_at: datetime


class EntryLine(BaseModel):
    p1: List[float] = Field(..., min_length=2, max_length=2)
    p2: List[float] = Field(..., min_length=2, max_length=2)
    inside: Literal["left", "right"]

    def problems(self) -> List[str]:
        return validate_line(self.model_dump())


class CameraCreate(BaseModel):
    camera_code: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    camera_type: CameraType = "zone"


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    camera_type: Optional[CameraType] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    camera_code: str
    name: str
    camera_type: str
    is_active: bool
    resolution_width: Optional[int] = None
    resolution_height: Optional[int] = None
    fps: Optional[float] = None
    entry_line: Optional[dict] = None
    has_reference_frame: bool = False
    reference_frame_width: Optional[int] = None
    reference_frame_height: Optional[int] = None
    config_version: int = 1


class ZoneIn(BaseModel):
    zone_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    zone_type: ZoneType
    polygon: List[List[float]] = Field(..., min_length=3, max_length=64)
    priority: int = Field(0, ge=-100, le=100)
    is_revenue_zone: bool = False
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("polygon")
    @classmethod
    def _valid_polygon(cls, v):
        problems = validate_polygon(v)
        if problems:
            raise ValueError("; ".join(problems))
        return [[round(float(x), 5), round(float(y), 5)] for x, y in v]


class CameraConfigIn(BaseModel):
    """Replace a camera's zones and entry line in one versioned update."""

    zones: List[ZoneIn] = Field(default_factory=list, max_length=50)
    entry_line: Optional[EntryLine] = None

    @field_validator("entry_line")
    @classmethod
    def _valid_line(cls, v):
        if v is not None:
            problems = v.problems()
            if problems:
                raise ValueError("; ".join(problems))
        return v

    @field_validator("zones")
    @classmethod
    def _unique(cls, v):
        names = [z.name for z in v]
        codes = [z.zone_code for z in v]
        if len(set(names)) != len(names) or len(set(codes)) != len(codes):
            raise ValueError("zone names and codes must be unique per camera")
        return v


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_code: str
    name: str
    zone_type: str
    is_revenue_zone: bool
    polygon: Optional[List[List[float]]] = None
    camera_id: Optional[uuid.UUID] = None
    priority: int = 0
    color: Optional[str] = None
    display_order: int = 0


class CameraConfigResponse(BaseModel):
    camera: CameraResponse
    zones: List[ZoneResponse]
    coordinate_space: str = "normalized: x,y in [0,1] of the camera frame, origin top-left"
