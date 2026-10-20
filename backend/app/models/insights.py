"""Tables for the customer-facing insight tools. Both only *record* what people did or said; neither
changes an analysis."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, new_id


class SiteVerification(Timestamps, Base):
    """Post-Move Verification: what the customer found in the real house, checked against the plan.

    items: [{"room_id", "actual_room_type", "present": bool, "note"}]
    remedy_progress: {finding_id: "done" | "partial" | "not_started" | "not_possible"}
    """

    __tablename__ = "site_verifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    compass_north_angle: Mapped[float | None] = mapped_column(Float)  # measured on site, same convention
    entrance_confirmed: Mapped[bool | None] = mapped_column()
    items: Mapped[list | None] = mapped_column(JSON)
    remedy_progress: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project = relationship("Project", back_populates="site_verifications")


class ExpertReview(Timestamps, Base):
    """Expert Review Handoff: a read-only review pack shared with a Vastu consultant or architect
    through an unguessable, expiring link. The expert's feedback is stored here, never applied
    automatically."""

    __tablename__ = "expert_reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expert_name: Mapped[str | None] = mapped_column(String(200))
    expert_role: Mapped[str | None] = mapped_column(String(50))  # vastu_consultant | architect | engineer
    message: Mapped[str | None] = mapped_column(Text)  # note from the customer to the expert
    include_contact: Mapped[bool | None] = mapped_column(default=False)  # share client name and address
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | submitted | revoked
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    feedback: Mapped[dict | None] = mapped_column(JSON)  # {"summary", "items": {finding_id: {...}}}
    reviewer_signature: Mapped[str | None] = mapped_column(String(200))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project = relationship("Project", back_populates="expert_reviews")
