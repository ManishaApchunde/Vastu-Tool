"""Server-side rendering of the annotated floor plan for the PDF report (rooms shaded by result,
numbered markers, 3 x 3 grid, Brahmasthan, main entrance, true-North directions)."""
import io
import math

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


# --- Report renderer -----------------------------------------------------------------------------
# Used by the redesigned PDF: rooms shaded by result, numbered markers that match the room tables,
# the 3 x 3 grid, the Brahmasthan, the main entrance, and the eight directions written around the
# plan at their true bearings (derived from north_angle), so the reader never assumes top = North.
TONE_RGB = {"positive": (47, 115, 85), "warning": (176, 115, 26), "major": (168, 50, 47), "neutral": (90, 107, 123)}
TONE_FILL_ALPHA = {"positive": 70, "warning": 85, "major": 95, "neutral": 30}
DIRECTIONS = [("N", 0), ("NE", 45), ("E", 90), ("SE", 135), ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)]
_FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
                    "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf", "arialbd.ttf"]


def _bold_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return _font(size)


def _label_point(polygon):
    try:
        from shapely.geometry import Polygon

        p = Polygon(polygon)
        if not p.is_valid:
            p = p.buffer(0)
        rp = p.representative_point()
        return rp.x, rp.y
    except Exception:  # noqa: BLE001 - fall back to the vertex average
        return sum(q[0] for q in polygon) / len(polygon), sum(q[1] for q in polygon) / len(polygon)


def _clipped_zones(geo) -> list[dict]:
    from shapely.geometry import Polygon, box

    frame = box(0, 0, geo["width"], geo["height"])
    if geo.get("boundary") and len(geo["boundary"]) >= 3:
        outline = Polygon(geo["boundary"])
        frame = (outline if outline.is_valid else outline.buffer(0)).intersection(frame)
    out = []
    for z in geo["zones"]:
        shape = Polygon(z["polygon"])
        if not shape.is_valid:
            shape = shape.buffer(0)
        clipped = shape.intersection(frame)
        if clipped.is_empty or clipped.area < 1 or clipped.geom_type != "Polygon":
            continue
        out.append({"code": z["code"], "shape": clipped, "points": list(clipped.exterior.coords)[:-1]})
    return out


def _tag_point(shape, inset):
    """Lower-right-most point of the zone cell after insetting it, so the tag sits inside the cell."""
    inner = shape.buffer(-inset * 1.6)
    if inner.is_empty or inner.geom_type != "Polygon":
        return None
    return max(inner.exterior.coords, key=lambda q: q[0] + q[1])


def _marker_point(polygon, r):
    """A point near the room's top-left corner, inside the room; falls back to the label point."""
    try:
        from shapely.geometry import Point, Polygon

        p = Polygon(polygon)
        if not p.is_valid:
            p = p.buffer(0)
        x0, y0, x1, y1 = p.bounds
        pad = r * 1.6
        if x1 - x0 > pad * 3 and y1 - y0 > pad * 3:
            for fx, fy in ((x0 + pad, y0 + pad), (x1 - pad, y0 + pad), (x0 + pad, y1 - pad)):
                if p.buffer(-r * 1.1).contains(Point(fx, fy)):
                    return fx, fy
    except Exception:  # noqa: BLE001
        pass
    return _label_point(polygon)


def _ray_to_rect(cx, cy, dx, dy, x0, y0, x1, y1):
    ts = []
    if dx > 1e-9:
        ts.append((x1 - cx) / dx)
    if dx < -1e-9:
        ts.append((x0 - cx) / dx)
    if dy > 1e-9:
        ts.append((y1 - cy) / dy)
    if dy < -1e-9:
        ts.append((y0 - cy) / dy)
    t = min(t for t in ts if t > 0)
    return cx + dx * t, cy + dy * t


def render_report_plan(image_png: bytes, report: dict, *, highlight: str | None = None,
                       max_side: int = 1600) -> bytes:
    """Annotated plan for the report. With `highlight` (a room id) it draws a thumbnail that
    emphasises one room and fades the rest."""
    geo = report["geometry"]
    base = Image.open(io.BytesIO(image_png)).convert("RGBA")
    scale = min(1.0, max_side / max(base.size))
    if scale < 1.0:
        base = base.resize((int(base.width * scale), int(base.height * scale)), Image.LANCZOS)
    fs = max(14, int(max(base.size) / (60 if highlight else 46)))
    margin = int(fs * 3.4)
    W, H = base.width + 2 * margin, base.height + 2 * margin
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    canvas.paste(base, (margin, margin))

    def S(p):
        return (p[0] * scale + margin, p[1] * scale + margin)

    font, small = _bold_font(fs), _bold_font(int(fs * 0.72))
    rooms = report["rooms"]

    # Layer 1: room shading. (Each layer is composited separately: drawing on one RGBA layer
    # replaces pixels instead of blending, which would wipe out lines drawn underneath.)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in rooms:
        pts = [S(p) for p in r["polygon"]]
        rgb = TONE_RGB[r["tone"]]
        if highlight and r["id"] != highlight:
            d.polygon(pts, fill=(255, 255, 255, 110), outline=(90, 107, 123, 120), width=2)
        elif highlight:
            d.polygon(pts, fill=rgb + (115,), outline=rgb + (255,), width=max(4, fs // 3))
        else:
            d.polygon(pts, fill=rgb + (TONE_FILL_ALPHA[r["tone"]],), outline=(22, 40, 58, 170), width=2)
    canvas = Image.alpha_composite(canvas, layer)

    # Layer 2: 3 x 3 grid, centre and entrance.
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # The grid is clipped to the plan outline: with a rotated North the zone cells extend past the image,
    # and unclipped lines would run through the margin and the direction labels.
    for poly in _clipped_zones(geo):
        pts = [S(p) for p in poly["points"]]
        d.line(pts + [pts[0]], fill=(156, 107, 28, 150 if highlight else 210), width=max(2, fs // 7))
    if not highlight:
        for poly in _clipped_zones(geo):
            spot = _tag_point(poly["shape"], fs / scale)
            if spot is None:
                continue
            tw = d.textlength(poly["code"], font=small)
            x, y = S(spot)
            lx, ly = x - tw - 4, y - fs * 0.85
            d.rounded_rectangle([lx - 5, ly - 3, lx + tw + 5, ly + fs * 0.85], radius=3, fill=(156, 107, 28, 225))
            d.text((lx, ly - 1), poly["code"], fill=(255, 255, 255, 255), font=small)
    if geo.get("centre"):
        cx, cy = S(geo["centre"])
        rr = fs * 0.75
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(156, 107, 28, 255), width=max(3, fs // 6))
        d.line([cx - 2 * rr, cy, cx + 2 * rr, cy], fill=(156, 107, 28, 255), width=max(2, fs // 8))
        d.line([cx, cy - 2 * rr, cx, cy + 2 * rr], fill=(156, 107, 28, 255), width=max(2, fs // 8))
    for o in geo.get("openings", []):
        if o["is_main_entrance"]:
            x, y = S(o["position"])
            rr = fs * 0.7
            d.rounded_rectangle([x - rr, y - rr, x + rr, y + rr], radius=4, fill=(22, 40, 58, 240),
                                outline=(255, 255, 255, 255), width=2)
            tw = d.textlength("E", font=small)
            d.text((x - tw / 2, y - fs * 0.45), "E", fill=(255, 255, 255, 255), font=small)
    canvas = Image.alpha_composite(canvas, layer)

    # Layer 3: numbered markers that match the room tables, tucked into each room's top-left
    # corner so they don't cover the plan's own room names.
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for r in rooms:
        if highlight and r["id"] != highlight:
            continue
        rr = fs * (1.05 if highlight else 0.9)
        x, y = _marker_point(r["polygon"], rr / scale)
        x, y = S((x, y))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=TONE_RGB[r["tone"]] + (255,),
                  outline=(255, 255, 255, 255), width=max(2, fs // 7))
        num = str(r["number"])
        tw = d.textlength(num, font=font)
        d.text((x - tw / 2, y - fs * 0.6), num, fill=(255, 255, 255, 255), font=font)

    out = Image.alpha_composite(canvas, overlay)
    d = ImageDraw.Draw(out)
    d.rectangle([margin - 1, margin - 1, margin + base.width, margin + base.height], outline=(211, 218, 223, 255))

    # Directions at their true bearings around the plan.
    cx, cy = margin + base.width / 2, margin + base.height / 2
    inset = margin * 0.5
    north = geo.get("north_angle") or 0.0
    for code, bearing in DIRECTIONS:
        if highlight and code != "N":
            continue
        t = math.radians(north + bearing)
        dx, dy = math.sin(t), -math.cos(t)
        x, y = _ray_to_rect(cx, cy, dx, dy, inset, inset, W - inset, H - inset)
        f = font if code in ("N", "S", "E", "W") else small
        if code == "N":
            rr = fs * 1.05
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(156, 107, 28, 255))
            # small arrow head pointing outward along the bearing
            tip = (x + dx * rr * 1.9, y + dy * rr * 1.9)
            px, py = -dy, dx
            d.polygon([tip, (x + dx * rr * 1.05 + px * rr * 0.5, y + dy * rr * 1.05 + py * rr * 0.5),
                       (x + dx * rr * 1.05 - px * rr * 0.5, y + dy * rr * 1.05 - py * rr * 0.5)],
                      fill=(156, 107, 28, 255))
            tw = d.textlength("N", font=font)
            d.text((x - tw / 2, y - fs * 0.62), "N", fill=(255, 255, 255, 255), font=font)
        else:
            tw = d.textlength(code, font=f)
            d.text((x - tw / 2, y - fs * 0.55), code, fill=(22, 40, 58, 255), font=f)

    buf = io.BytesIO()
    out.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
