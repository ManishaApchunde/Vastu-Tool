"""Vision-LLM provider (Anthropic Messages API). Asks the model for normalized (0-1) coordinates,
validates the JSON against DetectionResult and scales it to pixels. Any parsing problem raises
AIDetectionError so the job is marked failed and can be retried; the user can always fall back to
manual verification."""
import base64
import io
import json
import re

import httpx
from PIL import Image

from app.ai.base import AIDetectionError, FloorPlanAnalyzer
from app.ai.schema import DetectedOpening, DetectedRoom, DetectedStair, DetectedText, DetectionResult
from app.core.config import settings
from app.vastu.room_types import ROOM_TYPES, normalise_room_type

PROMPT = f"""You are reading an architectural floor plan image. Return ONLY a JSON object, no prose.
All coordinates are normalized: x and y between 0 and 1, origin at the top-left of the image.
Schema:
{{"boundary": [[x,y],...],
  "rooms": [{{"name": str, "room_type": one of {sorted(ROOM_TYPES)}, "polygon": [[x,y],...], "confidence": 0-1}}],
  "doors": [{{"position": [x,y], "is_main_entrance": bool, "confidence": 0-1}}],
  "windows": [{{"position": [x,y], "confidence": 0-1}}],
  "stairs": [{{"polygon": [[x,y],...], "confidence": 0-1}}],
  "texts": [{{"text": str, "position": [x,y], "kind": "label" | "dimension"}}]}}
Rules: polygons follow the inside faces of walls; use the room label printed on the plan as the name;
use confidence below 0.6 when unsure; do not guess compass direction."""


class AnthropicFloorPlanAnalyzer(FloorPlanAnalyzer):
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        if not self.api_key:
            raise AIDetectionError("ANTHROPIC_API_KEY is not configured.", retryable=False)

    def _call(self, image_png: bytes) -> dict:
        img = Image.open(io.BytesIO(image_png))
        img.thumbnail((1568, 1568))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        body = {
            "model": self.model, "max_tokens": 4000,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(buf.getvalue()).decode()}},
                {"type": "text", "text": PROMPT}]}],
        }
        try:
            resp = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=settings.ai_timeout_seconds,
                              headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        except httpx.HTTPError as exc:
            raise AIDetectionError(f"AI provider unreachable: {exc}") from exc
        if resp.status_code >= 500 or resp.status_code == 429:
            raise AIDetectionError(f"AI provider busy (HTTP {resp.status_code}).")
        if resp.status_code >= 400:
            raise AIDetectionError(f"AI provider rejected the request (HTTP {resp.status_code}).", retryable=False)
        text = "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise AIDetectionError("AI response did not contain JSON.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise AIDetectionError("AI response JSON was malformed.") from exc

    def analyze_floor_plan(self, image_png: bytes, width: int, height: int) -> DetectionResult:
        raw = self._call(image_png)

        def s(p):
            x, y = (min(max(float(v), 0.0), 1.0) for v in p[:2])
            return [round(x * width, 1), round(y * height, 1)]

        try:
            rooms = [DetectedRoom(id=f"room_{i+1}", name=r.get("name") or "Room",
                                  room_type=normalise_room_type(r.get("room_type"), r.get("name", "")),
                                  polygon=[s(p) for p in r["polygon"]], confidence=float(r.get("confidence", 0.5)))
                     for i, r in enumerate(raw.get("rooms", [])) if len(r.get("polygon", [])) >= 3]
            doors = [DetectedOpening(id=f"door_{i+1}", kind="door", position=s(d["position"]),
                                     is_main_entrance=bool(d.get("is_main_entrance")),
                                     confidence=float(d.get("confidence", 0.5))) for i, d in enumerate(raw.get("doors", []))]
            windows = [DetectedOpening(id=f"window_{i+1}", kind="window", position=s(w["position"]),
                                       confidence=float(w.get("confidence", 0.5))) for i, w in enumerate(raw.get("windows", []))]
            stairs = [DetectedStair(id=f"stair_{i+1}", polygon=[s(p) for p in st["polygon"]],
                                    confidence=float(st.get("confidence", 0.5))) for i, st in enumerate(raw.get("stairs", []))]
            texts = [DetectedText(text=str(t["text"])[:80], position=s(t["position"]),
                                  kind="dimension" if t.get("kind") == "dimension" else "label")
                     for t in raw.get("texts", []) if t.get("position")]
            boundary = [s(p) for p in raw["boundary"]] if len(raw.get("boundary") or []) >= 3 else None
        except (KeyError, TypeError, ValueError) as exc:
            raise AIDetectionError("AI response did not match the expected structure.") from exc
        if not rooms:
            raise AIDetectionError("No rooms were detected. Try a clearer image or draw the rooms manually.",
                                   retryable=False)
        return DetectionResult(provider=self.name, image_width=width, image_height=height, boundary=boundary,
                               boundary_confidence=0.7 if boundary else 0.0, rooms=rooms, doors=doors,
                               windows=windows, entrances=[d.id for d in doors if d.is_main_entrance],
                               stairs=stairs, texts=texts)
