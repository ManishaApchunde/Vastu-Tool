from abc import ABC, abstractmethod

from app.ai.schema import DetectedOpening, DetectedRoom, DetectionResult


class AIDetectionError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class FloorPlanAnalyzer(ABC):
    """Provider interface. Implementations turn a normalized PNG into a DetectionResult.

    `analyze_floor_plan` is the only method the pipeline calls; the finer-grained methods exist so
    providers that detect elements with different models (e.g. CV for walls, LLM for labels) can
    compose them."""

    name: str = "base"

    @abstractmethod
    def analyze_floor_plan(self, image_png: bytes, width: int, height: int) -> DetectionResult: ...

    def detect_rooms(self, image_png: bytes, width: int, height: int) -> list[DetectedRoom]:
        return self.analyze_floor_plan(image_png, width, height).rooms

    def detect_doors(self, image_png: bytes, width: int, height: int) -> list[DetectedOpening]:
        return self.analyze_floor_plan(image_png, width, height).doors

    def detect_windows(self, image_png: bytes, width: int, height: int) -> list[DetectedOpening]:
        return self.analyze_floor_plan(image_png, width, height).windows

    def detect_entrance(self, image_png: bytes, width: int, height: int) -> list[str]:
        return self.analyze_floor_plan(image_png, width, height).entrances
