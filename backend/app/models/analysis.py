from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, new_id


class Analysis(Timestamps, Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    floor_plan_id: Mapped[str] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"), index=True)
    rule_set_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id"))
    scoring_config_id: Mapped[str] = mapped_column(ForeignKey("scoring_configs.id"))
    status: Mapped[str] = mapped_column(String(20), default="complete")
    north_angle: Mapped[float] = mapped_column(Float)
    zone_system: Mapped[str] = mapped_column(String(40))
    overall_score: Mapped[float | None] = mapped_column(Float)
    category_scores: Mapped[dict | None] = mapped_column(JSON)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    counts: Mapped[dict | None] = mapped_column(JSON)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON)  # verified geometry used, for audit
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project = relationship("Project", back_populates="analyses")
    rule_set = relationship("RuleSet")
    findings = relationship(
        "Finding", back_populates="analysis", cascade="all, delete-orphan", order_by="Finding.sort_order"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("vastu_rules.id", ondelete="SET NULL"))
    rule_code: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30))
    subject_type: Mapped[str] = mapped_column(String(30))
    subject_ref: Mapped[str | None] = mapped_column(String(32))  # room/opening id
    subject_label: Mapped[str] = mapped_column(String(200))
    room_type: Mapped[str | None] = mapped_column(String(50))
    zone: Mapped[str | None] = mapped_column(String(10))
    direction: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))  # preferred | acceptable | issue | not_evaluated
    severity: Mapped[str] = mapped_column(String(20))
    bucket: Mapped[str] = mapped_column(String(20))  # positive | warning | major | info
    weight: Mapped[float] = mapped_column(Float, default=0)
    earned: Mapped[float] = mapped_column(Float, default=0)
    finding: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    remedy_id: Mapped[str | None] = mapped_column(ForeignKey("remedies.id", ondelete="SET NULL"))
    remedy_snapshot: Mapped[dict | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    analysis = relationship("Analysis", back_populates="findings")


class Report(Timestamps, Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|ready|failed
    # en | mr. Nullable so the dev auto-upgrade can add it; a NULL (older row) reads as English.
    language: Mapped[str | None] = mapped_column(String(5), default="en", server_default="en")
    # {"action_plan": bool}. NULL (older rows) means the original report without the personal action plan.
    options: Mapped[dict | None] = mapped_column(JSON)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    job_id: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)

    project = relationship("Project", back_populates="reports")


class ProcessingJob(Timestamps, Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    floor_plan_id: Mapped[str | None] = mapped_column(ForeignKey("floor_plans.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))  # detection | report
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|succeeded|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportVideo(Timestamps, Base):
    """Narrated video walkthrough of the report (MP4 with soft subtitles), English or Marathi."""

    __tablename__ = "report_videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(5), default="en")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|ready|failed
    progress: Mapped[int | None] = mapped_column(Integer, default=0)  # 0-100 while rendering
    narration: Mapped[str | None] = mapped_column(String(20))  # edge | gtts | silent
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    scenes: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    subtitles_key: Mapped[str | None] = mapped_column(String(500))  # .srt
    captions_key: Mapped[str | None] = mapped_column(String(500))  # .vtt for the web player
    poster_key: Mapped[str | None] = mapped_column(String(500))
    transcript: Mapped[list | None] = mapped_column(JSON)  # [{"title", "start", "text"}]
    job_id: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)

    project = relationship("Project")
