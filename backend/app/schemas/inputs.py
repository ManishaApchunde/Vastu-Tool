from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Pt = list[float]


def _check_pt(p: list[float]) -> list[float]:
    if len(p) != 2:
        raise ValueError("points must be [x, y]")
    return [float(p[0]), float(p[1])]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PropertyIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    client_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=1000)
    property_type: Literal["apartment", "villa", "independent_house", "plot", "office", "other"] = "apartment"
    built_up_area_sqft: float | None = Field(default=None, gt=0, lt=1_000_000)
    notes: str | None = Field(default=None, max_length=2000)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    property: PropertyIn = PropertyIn()


class RoomIn(BaseModel):
    id: str | None = None
    label: str = Field(min_length=1, max_length=120)
    room_type: str = Field(min_length=1, max_length=50)
    polygon: list[Pt] = Field(min_length=3, max_length=200)
    source: Literal["ai", "ai_edited", "user"] = "user"
    confidence: float | None = Field(default=None, ge=0, le=1)

    _pts = field_validator("polygon")(lambda cls, v: [_check_pt(p) for p in v])


class OpeningIn(BaseModel):
    id: str | None = None
    kind: Literal["door", "window"]
    position: Pt
    is_main_entrance: bool = False
    source: Literal["ai", "ai_edited", "user"] = "user"
    confidence: float | None = Field(default=None, ge=0, le=1)

    _pt = field_validator("position")(lambda cls, v: _check_pt(v))


class VerificationIn(BaseModel):
    boundary: list[Pt] | None = Field(default=None, max_length=500)
    rooms: list[RoomIn] = Field(default_factory=list, max_length=200)
    openings: list[OpeningIn] = Field(default_factory=list, max_length=500)

    @field_validator("boundary")
    @classmethod
    def _b(cls, v):
        if v is None:
            return v
        if len(v) < 3:
            raise ValueError("boundary needs at least 3 points")
        return [_check_pt(p) for p in v]


class NorthIn(BaseModel):
    north_angle: float = Field(ge=-360, le=360, description="Degrees clockwise from image top to true North")


class ReportIn(BaseModel):
    """Optional body for POST /projects/{id}/report. Omitting it keeps the original English report."""
    language: Literal["en", "mr"] = "en"
    include_action_plan: bool = True  # personal action plan section (insight tools)


# --- customer insight tools ----------------------------------------------------------------------
Level = Literal["none", "low", "medium", "high"]


class FitConstraintsIn(BaseModel):
    """Vastu FitCheck: what the household can and can't change."""
    ownership: Literal["owner", "tenant", "buying"] = "owner"
    budget: Level = "low"
    allow_structural: bool = False
    allow_services: bool = False  # plumbing / electrical
    max_disruption: Literal["none", "low", "high"] = "low"
    renovation_planned: bool = False
    society_restrictions: bool = False


class FamilyProfileIn(BaseModel):
    members: list[Literal["elderly", "children", "students", "work_from_home", "couple", "home_cook",
                          "devotional"]] = Field(default_factory=list, max_length=7)
    focus: list[Literal["sleep", "study", "work", "kitchen", "worship", "entrance", "open_centre"]] = Field(
        default_factory=list, max_length=7)
    room_priority: dict[str, Literal["high", "normal", "low"]] = Field(default_factory=dict, max_length=200)


Stage = Literal["planning", "foundation", "structure", "services", "finishing", "occupied"]


class InsightContextIn(BaseModel):
    """Any field left out is unchanged; send null to clear it."""
    fit_constraints: FitConstraintsIn | None = None
    family_profile: FamilyProfileIn | None = None
    construction_stage: Stage | None = None


class SiteRoomIn(BaseModel):
    room_id: str = Field(max_length=32)
    actual_room_type: str | None = Field(default=None, max_length=50)
    present: bool = True
    note: str | None = Field(default=None, max_length=500)


class SiteVerificationIn(BaseModel):
    compass_north_angle: float | None = Field(default=None, ge=0, lt=360)
    entrance_confirmed: bool | None = None
    items: list[SiteRoomIn] = Field(default_factory=list, max_length=200)
    remedy_progress: dict[str, Literal["done", "partial", "not_started", "not_possible"]] = Field(
        default_factory=dict, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)


class ApplySiteIn(BaseModel):
    use_site_north: bool = False


class ExpertReviewIn(BaseModel):
    expert_name: str | None = Field(default=None, max_length=200)
    expert_role: Literal["vastu_consultant", "architect", "engineer", "other"] = "vastu_consultant"
    message: str | None = Field(default=None, max_length=2000)
    valid_days: int = Field(default=14, ge=1, le=60)
    include_contact: bool = False


class ExpertItemIn(BaseModel):
    agree: bool | None = None
    comment: str | None = Field(default=None, max_length=2000)


class ExpertFeedbackIn(BaseModel):
    verdict: Literal["agree", "agree_with_changes", "disagree"]
    summary: str = Field(min_length=1, max_length=6000)
    north_confirmed: bool | None = None
    items: dict[str, ExpertItemIn] = Field(default_factory=dict, max_length=500)
    signature: str = Field(min_length=1, max_length=200)
