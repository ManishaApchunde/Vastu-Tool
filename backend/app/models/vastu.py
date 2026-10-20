from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, new_id


class RuleSet(Timestamps, Base):
    """A Vastu methodology/version. Rules, remedies and scoring are scoped to a rule set so that
    several methodologies can coexist later."""

    __tablename__ = "rule_sets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    methodology: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    description: Mapped[str | None] = mapped_column(Text)
    disclaimer: Mapped[str] = mapped_column(Text)
    zone_system: Mapped[str] = mapped_column(String(40), default="grid_3x3")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules = relationship("VastuRule", back_populates="rule_set", cascade="all, delete-orphan")
    remedies = relationship("Remedy", back_populates="rule_set", cascade="all, delete-orphan")


class VastuRule(Timestamps, Base):
    __tablename__ = "vastu_rules"
    __table_args__ = (UniqueConstraint("rule_set_id", "code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rule_set_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30))  # rooms | entrance | zones | layout | directions
    subject_type: Mapped[str] = mapped_column(String(30))  # room | entrance | zone | openings | plan
    subject: Mapped[str] = mapped_column(String(50))  # room type, zone code, etc.
    condition: Mapped[dict] = mapped_column(JSON)  # {"type": "...", ...params}
    outcome: Mapped[str] = mapped_column(String(20))  # preferred | acceptable | issue
    severity: Mapped[str] = mapped_column(String(20))  # positive | low | medium | high
    weight: Mapped[float] = mapped_column(Float, default=2.0)
    finding_template: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    remedy_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved | retired
    approved_by: Mapped[str | None] = mapped_column(String(200))

    rule_set = relationship("RuleSet", back_populates="rules")


class Remedy(Timestamps, Base):
    __tablename__ = "remedies"
    __table_args__ = (UniqueConstraint("rule_set_id", "code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rule_set_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    problem: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))  # high | medium | low
    visual_instruction: Mapped[str | None] = mapped_column(Text)
    # non_structural | structural | optional. Drives how the report phases and labels the remedy.
    kind: Mapped[str | None] = mapped_column(String(20), default="non_structural")
    # Optional explicit phase (immediate | short_term | medium_term | long_term); otherwise derived.
    phase: Mapped[str | None] = mapped_column(String(20))
    # Structural follow-up kept apart from the everyday recommendation (always professional-led).
    structural_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(200))

    rule_set = relationship("RuleSet", back_populates="remedies")


class ScoringConfig(Timestamps, Base):
    __tablename__ = "scoring_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rule_set_id: Mapped[str] = mapped_column(ForeignKey("rule_sets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
