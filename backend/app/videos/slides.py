"""Slide renderer: one 16:9 slide per scene, drawn with ReportLab (the same fonts and HarfBuzz
shaping as the Marathi PDF, so Devanagari renders correctly) and rasterised with pdfium."""
import io
import math

import pypdfium2 as pdfium
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from app.reports.pdf import (
    BRASS, BRASS_LIGHT, HAIRLINE, INK, INK_SOFT, MUTED, PAPER, TONE, TONE_LIGHT, _fonts, draw_text, esc,
)
from app.videos.script import Scene

W, H = 1280, 720
PAD = 64
FOOT = 46
GOLD = colors.HexColor("#C99A4B")
TONE_ALL = {**TONE, "action": BRASS}
TONE_ALL_LIGHT = {**TONE_LIGHT, "action": BRASS_LIGHT}


class Slide:
    def __init__(self, c: canvas.Canvas, fonts: dict):
        self.c, self.f = c, fonts

    def style(self, size: float, bold=False, color=INK_SOFT, leading=1.32, align=0) -> ParagraphStyle:
        return ParagraphStyle("s", fontName=self.f["bold" if bold else "regular"], fontSize=size,
                              leading=size * leading * self.f["leading"], textColor=color, alignment=align,
                              shaping=1 if self.f["shaping"] else 0)

    def para(self, text: str, x: float, top: float, w: float, size: float, bold=False, color=INK_SOFT,
             max_h: float | None = None, align=0) -> float:
        """Draws wrapped text with its top at `top` (y up). Shrinks the font until it fits max_h."""
        while True:
            p = Paragraph(text, self.style(size, bold, color, align=align))
            _, h = p.wrap(w, 10_000)
            if max_h is None or h <= max_h or size <= 11:
                break
            size -= 1
        p.drawOn(self.c, x, top - h)
        return h

    def _width(self, text: str, size: float) -> float:
        if not self.f["shaping"]:
            return self.c.stringWidth(text, self.f["bold"], size)
        p = Paragraph(esc(text), self.style(size, bold=True))
        p.wrap(100_000, size * 3)
        return p.getActualLineWidths0()[0]

    def text(self, s: str, x: float, y: float, size: float, bold=False, color=INK, centre=False):
        self.c.setFillColor(color)
        return draw_text(self.c, x, y, s, self.f["bold" if bold else "regular"], size, self.f["shaping"], centre=centre)

    def mark(self, kind: str, x: float, y: float, s: float = 18):
        c, r = self.c, s / 2
        if kind == "action":
            c.setFillColor(BRASS)
            p = c.beginPath()
            p.moveTo(x + r, y)
            p.lineTo(x + s, y + r)
            p.lineTo(x + r, y + s)
            p.lineTo(x, y + r)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            return
        c.setFillColor(TONE_ALL.get(kind, TONE["neutral"]))
        c.circle(x + r, y + r, r, fill=1, stroke=0)
        c.setStrokeColor(colors.white)
        c.setLineWidth(s * 0.13)
        c.setLineCap(1)
        if kind == "positive":
            c.line(x + s * .27, y + s * .52, x + s * .44, y + s * .33)
            c.line(x + s * .44, y + s * .33, x + s * .74, y + s * .68)
        elif kind == "major":
            c.line(x + s * .32, y + s * .32, x + s * .68, y + s * .68)
            c.line(x + s * .32, y + s * .68, x + s * .68, y + s * .32)
        elif kind == "warning":
            c.line(x + r, y + s * .42, x + r, y + s * .74)
            c.setFillColor(colors.white)
            c.circle(x + r, y + s * .26, s * .07, fill=1, stroke=0)
        else:
            c.setFillColor(colors.white)
            c.circle(x + r, y + r, s * .16, fill=1, stroke=0)

    def chip(self, label: str, tone: str, x: float, y: float, size: float = 17, right=False) -> float:
        w = self._width(label, size) + 28
        x0 = x - w if right else x
        self.c.setFillColor(TONE_ALL_LIGHT.get(tone, TONE_LIGHT["neutral"]))
        self.c.roundRect(x0, y, w, size + 16, 6, fill=1, stroke=0)
        self.text(label, x0 + 14, y + 9, size, bold=True, color=TONE_ALL.get(tone, MUTED))
        return w

    def image(self, png: bytes, x: float, y: float, w: float, h: float):
        img = ImageReader(io.BytesIO(png))
        iw, ih = img.getSize()
        k = min(w / iw, h / ih)
        dw, dh = iw * k, ih * k
        self.c.setFillColor(colors.white)
        self.c.setStrokeColor(HAIRLINE)
        self.c.roundRect(x, y, w, h, 10, fill=1, stroke=1)
        self.c.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask="auto")


def _grid_motif(c, x, y, size, color, width=1.0):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.rect(x, y, size, size, stroke=1, fill=0)
    for k in (1, 2):
        c.line(x + size * k / 3, y, x + size * k / 3, y + size)
        c.line(x, y + size * k / 3, x + size, y + size * k / 3)
    c.setFillColor(color)
    c.circle(x + size / 2, y + size / 2, size * 0.07, fill=1, stroke=0)


def _mandala(c, cx, cy, R):
    c.setStrokeColor(INK_SOFT)
    c.setLineWidth(1.2)
    for k in (1.0, 0.86, 1.22):
        c.circle(cx, cy, R * k, fill=0, stroke=1)
    c.setStrokeColor(GOLD)
    for i in range(72):
        a = math.radians(i * 5)
        inner = R * (0.9 if i % 9 == 0 else 0.95)
        c.setLineWidth(1.6 if i % 9 == 0 else 0.7)
        c.line(cx + math.sin(a) * inner, cy + math.cos(a) * inner, cx + math.sin(a) * R, cy + math.cos(a) * R)
    sq = R * 1.08
    _grid_motif(c, cx - sq / 2, cy - sq / 2, sq, GOLD, 1.4)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    for label, ang in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        a = math.radians(ang)
        c.drawCentredString(cx + math.sin(a) * R * 1.12, cy + math.cos(a) * R * 1.12 - 5, label)


def _frame(s: Slide, scene: Scene, idx: int, total: int, brand: str, name: str):
    c = s.c
    c.setFillColor(colors.HexColor("#F4F6F6"))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    if scene.kind != "title":
        c.setFillColor(INK)
        c.rect(0, H - 92, W, 92, fill=1, stroke=0)
        c.setFillColor(BRASS)
        c.rect(0, H - 94, W, 2, fill=1, stroke=0)
        s.text(scene.title, PAD, H - 60, 32, bold=True, color=colors.white)
        _grid_motif(c, W - PAD - 40, H - 66, 40, GOLD, 1.2)
    # footer: brand, property, progress
    c.setFillColor(INK)
    c.rect(0, 0, W, FOOT, fill=1, stroke=0)
    _grid_motif(c, PAD, 13, 20, colors.white, 0.8)
    s.text(brand, PAD + 30, 17, 14, bold=True, color=colors.white)
    s.text(name, PAD + 40 + c.stringWidth(brand, s.f["bold"], 14), 17, 13, color=colors.HexColor("#B9C3CC"))
    seg_w, gap = 16, 5
    x = W - PAD - total * (seg_w + gap)
    for i in range(total):
        c.setFillColor(BRASS if i <= idx else colors.HexColor("#3A4F63"))
        c.roundRect(x + i * (seg_w + gap), 20, seg_w, 6, 3, fill=1, stroke=0)


def _points(s: Slide, points: list[dict], x: float, top: float, w: float, bottom: float, size: float = 21,
            cards: bool = False):
    n = len(points) or 1
    gap = 18 if cards else 16
    per = (top - bottom - gap * (n - 1)) / n
    y = top
    for p in points:
        badge_w = 0
        if p.get("badge"):
            badge_w = s._width(p["badge"], 16) + 40
        pad = 18 if cards else 0
        tw = w - 34 - badge_w - 2 * pad
        para = Paragraph(esc(p["text"]), s.style(size))
        fs = size
        _, h = para.wrap(tw, 10_000)
        while h > per - 2 * pad and fs > 13:
            fs -= 1
            para = Paragraph(esc(p["text"]), s.style(fs))
            _, h = para.wrap(tw, 10_000)
        box_h = max(h, fs * 1.4) + 2 * pad
        if cards:
            s.c.setFillColor(colors.white)
            s.c.setStrokeColor(HAIRLINE)
            s.c.roundRect(x, y - box_h, w, box_h, 10, fill=1, stroke=1)
            s.c.setFillColor(TONE_ALL.get(p.get("tone"), MUTED))
            s.c.rect(x, y - box_h + 8, 5, box_h - 16, fill=1, stroke=0)
        para.drawOn(s.c, x + pad + 34 + (6 if cards else 0), y - pad - h)
        s.mark(p.get("tone", "neutral"), x + pad + (6 if cards else 0), y - pad - fs * 1.05, 20)
        if p.get("badge"):
            s.chip(p["badge"], p.get("badge_tone", "positive"), x + w - pad, y - pad - 30, 16, right=True)
        y -= box_h + gap
        if y < bottom:
            break


def _score_ring(s: Slide, score, tone, cx, cy, R):
    c = s.c
    c.setLineWidth(22)
    c.setStrokeColor(colors.HexColor("#E3E8EB"))
    c.circle(cx, cy, R, fill=0, stroke=1)
    if score is not None:
        c.setStrokeColor(TONE.get(tone, MUTED))
        c.setLineCap(1)
        p = c.beginPath()
        p.arc(cx - R, cy - R, cx + R, cy + R, startAng=90, extent=-3.6 * max(1, score))
        c.drawPath(p, fill=0, stroke=1)
    s.text(str(score if score is not None else "-"), cx, cy - 26, 86, bold=True, color=INK, centre=True)
    s.text("/ 100", cx, cy - 62, 20, color=MUTED, centre=True)


CAPTION_H = 84


def _caption(s: Slide, text: str):
    """On-screen subtitle band above the footer, so the video also works muted (WhatsApp autoplay)."""
    c = s.c
    c.setFillColor(colors.Color(0.086, 0.157, 0.227, alpha=0.92))
    c.rect(0, FOOT, W, CAPTION_H, fill=1, stroke=0)
    s.para(esc(text), PAD, FOOT + CAPTION_H - 12, W - 2 * PAD, 24, color=colors.white, max_h=CAPTION_H - 20, align=1)


def render_slide(scene: Scene, idx: int, total: int, *, language: str, brand: str, name: str,
                 plan_png: bytes, thumbs: dict[str, bytes], caption: str | None = None) -> bytes:
    fonts = _fonts(language)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    s = Slide(c, fonts)
    _frame(s, scene, idx, total, brand, name)
    top, bottom = H - 130, FOOT + CAPTION_H + 22
    k, d = scene.kind, scene.data

    if k == "title":
        c.setFillColor(INK)
        c.rect(0, FOOT, W * 0.42, H - FOOT, fill=1, stroke=0)
        _mandala(c, W * 0.21, H * 0.55, 150)
        _grid_motif(c, PAD, H - 82, 30, colors.white, 1)
        s.text(brand, PAD + 42, H - 74, 20, bold=True, color=colors.white)
        x = W * 0.42 + 70
        s.text(scene.title, x, H - 150, 22, color=BRASS, bold=True)
        h = s.para(esc(d["name"]), x, H - 175, W - x - PAD, 50, bold=True, color=INK, max_h=140)
        y = H - 190 - h
        sub = " · ".join(v for v in (d.get("client"), d.get("date")) if v)
        if sub:
            s.text(sub, x, y, 20, color=MUTED)
        _score_ring(s, d.get("score"), d.get("tone"), x + 105, 230, 92)
        if d.get("band"):
            s.chip(d["band"], d.get("tone") or "neutral", x + 240, 222, 20)
    elif k in ("method", "rooms"):
        s.image(plan_png, PAD, bottom, 640, top - bottom + 10)
        _points(s, scene.points[:10], PAD + 680, top, W - 2 * PAD - 680, bottom, 19 if k == "rooms" else 22)
    elif k == "score":
        _score_ring(s, d.get("score"), d.get("tone"), PAD + 170, (top + bottom) / 2 + 30, 130)
        if d.get("band"):
            s.chip(d["band"], d.get("tone") or "neutral", PAD + 70, bottom + 10, 20)
        x0, y = PAD + 420, top - 10
        for cat in d.get("categories", []):
            s.text(cat["label"], x0, y - 22, 21, color=INK)
            bw = W - PAD - x0 - 260
            c.setFillColor(PAPER)
            c.roundRect(x0 + 230, y - 24, bw, 18, 9, fill=1, stroke=0)
            c.setFillColor(TONE.get(cat["tone"], MUTED))
            c.roundRect(x0 + 230, y - 24, max(18, bw * cat["score"] / 100), 18, 9, fill=1, stroke=0)
            s.text(str(cat["score"]), W - PAD - 10, y - 22, 21, bold=True, color=TONE.get(cat["tone"], MUTED))
            y -= 62
        cnt = d.get("counts") or {}
        x = x0
        for key in ("positive", "warning", "major"):
            s.mark(key, x, bottom + 8, 22)
            s.text(str(cnt.get(key, 0)), x + 32, bottom + 9, 26, bold=True, color=TONE[key])
            x += 120
    elif k == "room":
        thumb = thumbs.get(d.get("room_id"))
        if thumb:
            s.image(thumb, PAD, bottom, 600, top - bottom + 10)
        x = PAD + 650
        c.setFillColor(TONE.get(d.get("tone"), MUTED))
        c.circle(x + 30, top - 30, 30, fill=1, stroke=0)
        s.text(str(d.get("number")), x + 30, top - 42, 30, bold=True, color=colors.white, centre=True)
        s.text(d.get("type") or "", x + 76, top - 40, 20, color=MUTED)
        if d.get("score") is not None:
            s.chip(f"{d['score']} / 100", d.get("tone") or "neutral", W - PAD, top - 52, 18, right=True)
        _points(s, scene.points, x, top - 90, W - PAD - x, bottom, 22)
    elif k == "drags":
        _points(s, scene.points, PAD, top, W - 2 * PAD, bottom, 25, cards=True)
    elif k == "remedies":
        phases = d.get("phases", [])[:4]
        n = max(1, len(phases))
        gap = 24
        cw = (W - 2 * PAD - gap * (n - 1)) / n
        for i, ph in enumerate(phases):
            x = PAD + i * (cw + gap)
            c.setFillColor(colors.white)
            c.setStrokeColor(HAIRLINE)
            c.roundRect(x, bottom, cw, top - bottom, 12, fill=1, stroke=1)
            c.setFillColor(BRASS)
            c.circle(x + 36, top - 38, 18, fill=1, stroke=0)
            s.text(str(i + 1), x + 36, top - 45, 18, bold=True, color=colors.white, centre=True)
            s.para(esc(ph["label"]), x + 64, top - 22, cw - 80, 22, bold=True, color=INK)
            y = top - 86
            for it in ph["items"]:
                h = s.para(esc(it["text"]), x + 22, y, cw - 44, 20, color=TONE["major"] if it["structural"] else INK_SOFT,
                           max_h=(top - bottom - 110) / max(1, len(ph["items"])))
                y -= h + 14
    else:
        if k == "trust" and d.get("level"):
            s.chip(d["level"], d.get("tone") or "neutral", PAD, top - 30, 22)
            top -= 70
        if k == "stage" and d.get("stage"):
            s.chip(d["stage"], "action", PAD, top - 30, 22)
            top -= 70
        pts = scene.points or [{"text": scene.narration.split(". ")[0], "tone": "neutral"}]
        _points(s, pts[:6], PAD, top, W - 2 * PAD, bottom, 25, cards=True)

    if caption:
        _caption(s, caption)
    c.showPage()
    c.save()
    pdf = pdfium.PdfDocument(buf.getvalue())
    try:
        img = pdf[0].render(scale=1.5).to_pil().convert("RGB")
        out = io.BytesIO()
        img.save(out, "PNG", optimize=False)
        return out.getvalue()
    finally:
        pdf.close()
