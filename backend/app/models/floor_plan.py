from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, new_id


class FloorPlanStatus:
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    DETECTED = "detected"
    DETECTION_FAILED = "detection_failed"
    VERIFIED = "verified"
    NORTH_SET = "north_set"
    ZONED = "zoned"
    ANALYZED = "analyzed"


class FloorPlan(Timestamps, Base):
    """One uploaded plan. Geometry is stored in image pixel coordinates of the preview image
    (x to the right, y downward)."""

    __tablename__ = "floor_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(500))  # original file, private
    preview_key: Mapped[str] = mapped_column(String(500))  # normalized PNG used for AI + display
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default=FloorPlanStatus.UPLOADED)
    quality: Mapped[dict | None] = mapped_column(JSON)  # {"blur_score": .., "warnings": [..]}

    # AI output kept verbatim and never used for analysis directly.
    detection: Mapped[dict | None] = mapped_column(JSON)
    detection_provider: Mapped[str | None] = mapped_column(String(50))

    # Verified data (set only by the verification endpoint).
    boundary: Mapped[list | None] = mapped_column(JSON)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Derived by the geometry engine.
    zone_system: Mapped[str] = mapped_column(String(40), default="grid_3x3")
    centre: Mapped[list | None] = mapped_column(JSON)  # [x, y]

    project = relationship("Project", back_populates="floor_plans")
    rooms = relationship("Room", back_populates="floor_plan", cascade="all, delete-orphan", order_by="Room.sort_order")
    openings = relationship("Opening", back_populates="floor_plan", cascade="all, delete-orphan")
    north = relationship("NorthOrientation", back_populates="floor_plan", uselist=False, cascade="all, delete-orphan")
    zones = relationship("VastuZone", back_populates="floor_plan", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    floor_plan_id: Mapped[str] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    room_type: Mapped[str] = mapped_column(String(50))
    polygon: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="user")  # ai | ai_edited | user
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # geometry engine output
    primary_zone: Mapped[str | None] = mapped_column(String(10))
    direction: Mapped[str | None] = mapped_column(String(10))
    bearing_deg: Mapped[float | None] = mapped_column(Float)
    zone_overlaps: Mapped[dict | None] = mapped_column(JSON)

    floor_plan = relationship("FloorPlan", back_populates="rooms")


class Opening(Base):
    __tablename__ = "openings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    floor_plan_id: Mapped[str] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # door | window
    is_main_entrance: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[list] = mapped_column(JSON)  # [x, y]
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="user")
    zone: Mapped[str | None] = mapped_column(String(10))
    direction: Mapped[str | None] = mapped_column(String(10))

    floor_plan = relationship("FloorPlan", back_populates="openings")


class NorthOrientation(Base):
    """north_angle: degrees clockwise from the top of the image to true North."""

    __tablename__ = "north_orientations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    floor_plan_id: Mapped[str] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), unique=True)
    north_angle: Mapped[float] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    floor_plan = relationship("FloorPlan", back_populates="north")


class VastuZone(Base):
    __tablename__ = "vastu_zones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    floor_plan_id: Mapped[str] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), index=True)
    system: Mapped[str] = mapped_column(String(40))
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(50))
    polygon: Mapped[list] = mapped_column(JSON)  # image coordinates
    coverage: Mapped[float] = mapped_column(Float)  # fraction of the cell covered by the plan boundary

    floor_plan = relationship("FloorPlan", back_populates="zones")
