"""Structured detection output. This is AI output only - it is never passed to the Vastu engine."""
from typing import Literal

from pydantic import BaseModel, Field

Pt = list[float]


class DetectedRoom(BaseModel):
    id: str
    name: str
    room_type: str = "other"
    polygon: list[Pt]
    confidence: float = Field(ge=0, le=1)


class DetectedOpening(BaseModel):
    id: str
    kind: Literal["door", "window"]
    position: Pt
    is_main_entrance: bool = False
    confidence: float = Field(ge=0, le=1)


class DetectedStair(BaseModel):
    id: str
    polygon: list[Pt]
    confidence: float = Field(ge=0, le=1)


class DetectedText(BaseModel):
    text: str
    position: Pt
    kind: Literal["label", "dimension"] = "label"


class DetectionResult(BaseModel):
    provider: str
    image_width: int
    image_height: int
    boundary: list[Pt] | None = None
    boundary_confidence: float = 0.0
    walls: list[list[float]] = []  # [x1, y1, x2, y2] segments
    rooms: list[DetectedRoom] = []
    doors: list[DetectedOpening] = []
    windows: list[DetectedOpening] = []
    entrances: list[str] = []  # ids of doors believed to be the main entrance
    stairs: list[DetectedStair] = []
    texts: list[DetectedText] = []
    warnings: list[str] = []
