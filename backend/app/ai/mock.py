"""Deterministic analyzer for development and demos. It returns the reference layout scaled to the
uploaded image, with realistic confidences and two deliberate mistakes (an unlabelled room and a
low-confidence entrance) so the verification step has something to correct."""
from app.ai.base import FloorPlanAnalyzer
from app.ai.demo_layout import BOUNDARY, CANVAS, DOORS, ROOMS, WINDOWS
from app.ai.schema import DetectedOpening, DetectedRoom, DetectedStair, DetectedText, DetectionResult

_CONF = {"r_living": 0.94, "r_kitchen": 0.91, "r_master": 0.9, "r_pooja": 0.83, "r_toilet1": 0.88,
         "r_toilet2": 0.79, "r_dining": 0.86, "r_stairs": 0.81, "r_bed2": 0.58}


class MockFloorPlanAnalyzer(FloorPlanAnalyzer):
    name = "mock"

    def analyze_floor_plan(self, image_png: bytes, width: int, height: int) -> DetectionResult:
        sx, sy = width / CANVAS[0], height / CANVAS[1]

        def s(p):
            return [round(p[0] * sx, 1), round(p[1] * sy, 1)]

        rooms, stairs, texts = [], [], []
        for rid, label, rtype, poly in ROOMS:
            pts = [s(p) for p in poly]
            if rtype == "staircase":
                stairs.append(DetectedStair(id=rid, polygon=pts, confidence=_CONF[rid]))
                continue
            # deliberate AI mistake: Bedroom 2 comes back unlabelled
            name, room_type = ("Room", "other") if rid == "r_bed2" else (label, rtype)
            rooms.append(DetectedRoom(id=rid, name=name, room_type=room_type, polygon=pts, confidence=_CONF[rid]))
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            texts.append(DetectedText(text=label, position=[sum(xs) / len(xs), sum(ys) / len(ys)]))

        doors = [DetectedOpening(id=i, kind="door", position=s(p), is_main_entrance=m,
                                 confidence=0.62 if m else 0.84) for i, p, m in DOORS]
        windows = [DetectedOpening(id=i, kind="window", position=s(p), confidence=0.8) for i, p in WINDOWS]
        return DetectionResult(
            provider=self.name, image_width=width, image_height=height,
            boundary=[s(p) for p in BOUNDARY], boundary_confidence=0.9,
            walls=[[*s(a), *s(b)] for a, b in zip(BOUNDARY, BOUNDARY[1:] + BOUNDARY[:1])],
            rooms=rooms, doors=doors, windows=windows, entrances=["d_main"], stairs=stairs, texts=texts,
            warnings=["Mock analyzer: detection is a fixed reference layout scaled to your image. "
                      "Check every room before continuing."],
        )
