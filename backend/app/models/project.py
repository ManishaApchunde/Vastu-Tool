from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, new_id


class Project(Timestamps, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False)

    owner = relationship("User", back_populates="projects")
    property = relationship("Property", back_populates="project", uselist=False, cascade="all, delete-orphan")
    floor_plans = relationship(
        "FloorPlan", back_populates="project", cascade="all, delete-orphan", order_by="FloorPlan.created_at"
    )
    analyses = relationship(
        "Analysis", back_populates="project", cascade="all, delete-orphan", order_by="Analysis.created_at"
    )
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")
    site_verifications = relationship("SiteVerification", back_populates="project", cascade="all, delete-orphan",
                                      order_by="SiteVerification.created_at")
    expert_reviews = relationship("ExpertReview", back_populates="project", cascade="all, delete-orphan",
                                  order_by="ExpertReview.created_at")


class Property(Timestamps, Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    client_name: Mapped[str | None] = mapped_column(String(200))  # who the report is prepared for
    address: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str] = mapped_column(String(50), default="apartment")  # apartment|villa|plot|office|other
    built_up_area_sqft: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    # Customer context used by the insight tools (all optional, all nullable so the dev auto-upgrade
    # can add them). They never change the official analysis; they shape advice around it.
    fit_constraints: Mapped[dict | None] = mapped_column(JSON)  # Vastu FitCheck: budget, ownership, limits
    family_profile: Mapped[dict | None] = mapped_column(JSON)  # Family Priority Mode
    construction_stage: Mapped[str | None] = mapped_column(String(30))  # Construction Stage Assistant

    project = relationship("Project", back_populates="property")
