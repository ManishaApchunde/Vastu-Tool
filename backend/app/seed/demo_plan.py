"""Draws the demo floor plan PNG from the reference layout, so the whole workflow can be shown
without real plans or AI credentials."""
import io
import math

from PIL import Image, ImageDraw, ImageFont

from app.ai.demo_layout import BOUNDARY, CANVAS, DOORS, ROOMS, WINDOWS


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_demo_plan(scale: float = 1.4) -> bytes:
    W, H = int(CANVAS[0] * scale), int(CANVAS[1] * scale)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    S = lambda p: (p[0] * scale, p[1] * scale)  # noqa: E731
    wall = int(4 * scale)
    for _, _, _, poly in ROOMS:
        d.polygon([S(p) for p in poly], outline=(40, 40, 40), width=int(2 * scale))
    d.polygon([S(p) for p in BOUNDARY], outline=(20, 20, 20), width=wall * 2)
    f, fs = _font(int(17 * scale)), _font(int(12 * scale))
    for _, label, _, poly in ROOMS:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        cx, cy = S((sum(xs) / len(xs), sum(ys) / len(ys)))
        w = (max(xs) - min(xs)) / 100 * 3.28 * 3
        h = (max(ys) - min(ys)) / 100 * 3.28 * 3
        tw = d.textlength(label, font=f)
        d.text((cx - tw / 2, cy - 14 * scale), label, fill=(20, 20, 20), font=f)
        dim = f"{w:.0f}' x {h:.0f}'"
        d.text((cx - d.textlength(dim, font=fs) / 2, cy + 6 * scale), dim, fill=(90, 90, 90), font=fs)
        if label == "Stairs":
            for i in range(1, 8):
                y = S((0, 220 + i * 30))[1]
                d.line([S((720, 0))[0], y, S((880, 0))[0], y], fill=(120, 120, 120), width=1)
    for _, pos, main in DOORS:
        x, y = S(pos)
        r = (26 if main else 18) * scale
        d.rectangle([x - r / 2, y - 4 * scale, x + r / 2, y + 4 * scale], fill="white")
        d.arc([x - r / 2, y - r / 2, x + r / 2, y + r / 2], 0, 180, fill=(60, 60, 60), width=2)
        if main:
            d.text((x - 22 * scale, y - 34 * scale), "ENTRY", fill=(20, 20, 20), font=fs)
    for _, pos in WINDOWS:
        x, y = S(pos)
        vertical = pos[0] in (100, 900)
        L = 30 * scale
        if vertical:
            d.rectangle([x - 5 * scale, y - L, x + 5 * scale, y + L], fill="white", outline=(40, 40, 40))
            d.line([x, y - L, x, y + L], fill=(40, 40, 40))
        else:
            d.rectangle([x - L, y - 5 * scale, x + L, y + 5 * scale], fill="white", outline=(40, 40, 40))
            d.line([x - L, y, x + L, y], fill=(40, 40, 40))
    # title block
    d.text((S((100, 730))), "DEMO RESIDENCE  -  GROUND FLOOR  -  NOT TO SCALE", fill=(60, 60, 60), font=fs)
    cx, cy = S((955, 60))
    d.line([cx, cy + 25 * scale, cx, cy - 25 * scale], fill=(20, 20, 20), width=3)
    d.polygon([(cx, cy - 32 * scale), (cx - 8 * scale, cy - 16 * scale), (cx + 8 * scale, cy - 16 * scale)],
              fill=(20, 20, 20))
    d.text((cx - 5 * scale, cy + 27 * scale), "N", fill=(20, 20, 20), font=fs)
    _ = math  # keep import for future curved walls
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
