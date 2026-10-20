from app.ai.base import FloorPlanAnalyzer
from app.ai.mock import MockFloorPlanAnalyzer
from app.core.config import settings


def get_analyzer(provider: str | None = None) -> FloorPlanAnalyzer:
    provider = (provider or settings.ai_provider).lower()
    if provider == "anthropic":
        from app.ai.vision_llm import AnthropicFloorPlanAnalyzer

        return AnthropicFloorPlanAnalyzer()
    return MockFloorPlanAnalyzer()
