"""Plain data types shared by the rule, scoring and remedy engines (no DB dependency)."""
from dataclasses import dataclass, field


@dataclass
class RuleSpec:
    id: str | None
    code: str
    category: str
    subject_type: str
    subject: str
    condition: dict
    outcome: str  # preferred | acceptable | issue
    severity: str  # positive | low | medium | high
    weight: float
    finding_template: str
    explanation: str
    remedy_code: str | None = None


@dataclass
class RemedySpec:
    id: str | None
    code: str
    problem: str
    explanation: str
    recommendation: str
    priority: str
    visual_instruction: str | None = None
    kind: str | None = "non_structural"
    phase: str | None = None
    structural_note: str | None = None


@dataclass
class FindingResult:
    rule_id: str | None
    rule_code: str | None
    category: str
    subject_type: str
    subject_ref: str | None
    subject_label: str
    room_type: str | None
    zone: str | None
    direction: str | None
    status: str  # preferred | acceptable | issue | not_evaluated
    severity: str  # positive | low | medium | high | info
    weight: float
    finding: str
    explanation: str | None
    remedy_code: str | None = None
    earned: float = 0.0
    remedy: dict | None = None
    extra: dict = field(default_factory=dict)

    @property
    def bucket(self) -> str:
        if self.status in ("preferred", "acceptable"):
            return "positive"
        if self.status == "issue":
            return "major" if self.severity == "high" else "warning"
        return "info"
