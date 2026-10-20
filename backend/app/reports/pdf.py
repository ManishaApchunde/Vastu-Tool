"""PDF renderer for the Vastu evaluation report.

Lays out the structure produced by `report_data.build_report_data()`; it contains no Vastu
reasoning of its own. Page flow (length depends on the property):

    Cover + executive summary
    Property layout & directional assessment  (details, annotated plan, legend)
    Room-wise Vastu compliance overview       (room table, score breakdown, zone summary)
    Room-by-room detailed analysis            (one card per room, page breaks as needed)
    Vastu findings                            (positive, warnings, major issues)
    Phase-wise remedial plan                  (immediate to long term, then remedy details)
    Vastu evaluation summary                  (score, strengths, weaknesses, priorities, next steps)
    Disclaimer

Language: all fixed wording comes from reports/i18n.py (`texts_for(language)`), and the font set
comes from FONTS. English keeps the original Helvetica layout. Marathi embeds Noto Sans Devanagari
(Latin + Devanagari in one face, so user-typed English names still render) with HarfBuzz shaping,
which ReportLab needs to form Devanagari conjuncts and vowel signs correctly.
"""
from __future__ import annotations

import io
import math
import threading
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from app.reports.i18n import EnglishTexts, texts_for

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
HEADER_H = 15 * mm
FOOTER_H = 11 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X
COVER_PANEL = 0.31  # share of the cover page taken by the artwork panel

INK = colors.HexColor("#16283A")
INK_SOFT = colors.HexColor("#2C4156")
MUTED = colors.HexColor("#5A6B7B")
HAIRLINE = colors.HexColor("#D3DADF")
PAPER = colors.HexColor("#F4F6F6")
BRASS = colors.HexColor("#9C6B1C")
BRASS_LIGHT = colors.HexColor("#F3E7D0")
TONE = {"positive": colors.HexColor("#2F7355"), "warning": colors.HexColor("#B0731A"),
        "major": colors.HexColor("#A8322F"), "neutral": colors.HexColor("#5A6B7B")}
TONE_LIGHT = {"positive": colors.HexColor("#E3F0E9"), "warning": colors.HexColor("#F8ECD8"),
              "major": colors.HexColor("#F6E1E0"), "neutral": colors.HexColor("#EEF1F3")}


FONT_DIR = Path(__file__).parent / "fonts"
FONTS = {
    "en": {"regular": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique", "shaping": False,
           "leading": 1.0},
    # Devanagari needs a little more line height for vowel signs above and below the letters.
    "mr": {"regular": "NotoSansDevanagari", "bold": "NotoSansDevanagari-Bold", "italic": "NotoSansDevanagari",
           "shaping": True, "leading": 1.12},
}
_font_lock = threading.Lock()
_devanagari_ready = False


def _register_devanagari() -> None:
    """Embeds Noto Sans Devanagari (subset per PDF, so the file opens correctly on any computer)."""
    global _devanagari_ready
    if _devanagari_ready:
        return
    with _font_lock:
        if _devanagari_ready:
            return
        from reportlab.lib.fonts import addMapping
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        regular = TTFont("NotoSansDevanagari", str(FONT_DIR / "NotoSansDevanagari-Regular.ttf"), shapable=True)
        bold = TTFont("NotoSansDevanagari-Bold", str(FONT_DIR / "NotoSansDevanagari-Bold.ttf"), shapable=True)
        if not (regular.shapable and bold.shapable):
            # Without shaping, conjuncts and vowel signs come out in the wrong order: refuse instead.
            raise RuntimeError("Marathi PDFs need HarfBuzz text shaping. Install 'uharfbuzz' (requirements.txt).")
        pdfmetrics.registerFont(regular)
        pdfmetrics.registerFont(bold)
        for b, i, name in ((0, 0, regular.fontName), (1, 0, bold.fontName), (0, 1, regular.fontName),
                           (1, 1, bold.fontName)):
            addMapping("NotoSansDevanagari", b, i, name)
        _devanagari_ready = True


def _fonts(language: str) -> dict:
    if language not in FONTS:
        raise ValueError(f"No PDF font set for language '{language}'.")
    if language == "mr":
        _register_devanagari()
    return FONTS[language]


def draw_text(c, x: float, y: float, text: str, font: str, size: float, shaping: bool, centre: bool = False) -> float:
    """drawString replacement. With Devanagari, the canvas's own shaping misplaces pre-base vowel signs
    (ि) and drops conjuncts, while Paragraph shapes correctly, so shaped text is drawn as a one-line
    Paragraph whose baseline sits exactly at y. Returns the drawn width."""
    if not shaping:
        c.setFont(font, size)
        (c.drawCentredString if centre else c.drawString)(x, y, text)
        return c.stringWidth(text, font, size)
    p = Paragraph(esc(text), ParagraphStyle("dt", fontName=font, fontSize=size, leading=size,
                                            textColor=c._fillColorObj, shaping=1))
    p.wrap(100_000, size * 3)
    w = p.getActualLineWidths0()[0]
    p.drawOn(c, x - w / 2 if centre else x, y)
    return w


def _hex(c) -> str:
    return "#" + c.hexval()[2:]


# --- styles --------------------------------------------------------------------------------------
def _styles(texts: EnglishTexts | None = None, fonts: dict | None = None):
    texts, fonts = texts or texts_for("en"), fonts or FONTS["en"]
    R, B, k = fonts["regular"], fonts["bold"], fonts["leading"]
    body = ParagraphStyle("body", fontName=R, fontSize=9.6, leading=14.2 * k, textColor=INK_SOFT,
                          shaping=1 if fonts["shaping"] else 0)
    return {
        "t": texts, "fonts": fonts,
        "body": body,
        "lead": ParagraphStyle("lead", parent=body, fontSize=10.2, leading=15.2 * k),
        "small": ParagraphStyle("small", parent=body, fontSize=8.2, leading=11.5 * k, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=body, fontSize=9, leading=12.2 * k),
        "cell_b": ParagraphStyle("cell_b", parent=body, fontName=B, fontSize=9, leading=12.2 * k,
                                 textColor=INK),
        "th": ParagraphStyle("th", parent=body, fontName=B, fontSize=8.8, leading=11.5 * k,
                             textColor=INK),
        "label": ParagraphStyle("label", parent=body, fontSize=7.8, leading=10 * k, textColor=MUTED),
        "h2": ParagraphStyle("h2", parent=body, fontName=B, fontSize=13.5, leading=18 * k,
                             textColor=INK, spaceBefore=4, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=body, fontName=B, fontSize=11, leading=15 * k,
                             textColor=INK, spaceBefore=8, spaceAfter=4),
        "title": ParagraphStyle("title", parent=body, fontName=B, fontSize=25, leading=30 * k,
                                textColor=INK),
        "subtitle": ParagraphStyle("subtitle", parent=body, fontSize=12.5, leading=17 * k, textColor=MUTED),
        "big": ParagraphStyle("big", parent=body, fontName=B, fontSize=46, leading=52 * k,
                              textColor=INK),
        "chip": ParagraphStyle("chip", parent=body, fontName=B, fontSize=8.6, leading=11 * k,
                               alignment=TA_LEFT),
    }


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- small flowables -----------------------------------------------------------------------------
def _frame_top_gap(doc, used_height: float) -> float:
    """How far below the top of the current frame a flowable of `used_height` starts."""
    f = doc.frame
    return (f._y2 - f._topPadding) - (f._y + used_height)


class SectionStart(Flowable):
    """Starts a report section. The page header band shows the section in effect at the top of a
    page, so a section that begins mid-page draws its own heading band here instead; when it lands
    at the top of a page the header already names it and only a small gap remains."""

    def __init__(self, title: str, visible: bool = False):
        super().__init__()
        self.title, self.visible = title, visible
        self.width = CONTENT_W
        self.height = 13 * mm if visible else 0

    def wrap(self, *_):
        return (CONTENT_W, self.height)

    def draw(self):
        doc = self.canv._doctemplate
        at_top = _frame_top_gap(doc, self.height) < 5 * mm  # allow for the spacer above it
        doc._section = self.title
        if at_top:
            doc._page_section = self.title
        elif self.visible:
            c = self.canv
            c.setFillColor(INK)
            c.rect(0, 3 * mm, CONTENT_W, 9 * mm, fill=1, stroke=0)
            c.setFillColor(BRASS)
            c.rect(0, 3 * mm - 1, CONTENT_W, 1, fill=1, stroke=0)
            c.setFillColor(colors.white)
            draw_text(c, 4 * mm, 3 * mm + 3.1 * mm, self.title, doc._fonts["bold"], 11.5, doc._fonts["shaping"])


class Mark(Flowable):
    """Vector status mark: tick (positive), cross (major), ! (warning), dot (neutral), diamond (action)."""

    def __init__(self, kind: str, size: float = 9.5):
        super().__init__()
        self.kind, self.size = kind, size
        self.width = self.height = size

    def wrap(self, *_):
        return self.size, self.size

    def draw(self):
        c, s = self.canv, self.size
        r = s / 2
        if self.kind == "action":
            c.setFillColor(BRASS)
            p = c.beginPath()
            p.moveTo(r, 0.6)
            p.lineTo(s - 1.2, r)
            p.lineTo(r, s - 0.6)
            p.lineTo(1.2, r)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            return
        c.setFillColor(TONE.get(self.kind, TONE["neutral"]))
        c.circle(r, r, r, fill=1, stroke=0)
        c.setStrokeColor(colors.white)
        c.setFillColor(colors.white)
        c.setLineWidth(s * 0.13)
        c.setLineCap(1)
        if self.kind == "positive":
            c.line(s * 0.27, s * 0.52, s * 0.44, s * 0.33)
            c.line(s * 0.44, s * 0.33, s * 0.74, s * 0.68)
        elif self.kind == "major":
            c.line(s * 0.32, s * 0.32, s * 0.68, s * 0.68)
            c.line(s * 0.32, s * 0.68, s * 0.68, s * 0.32)
        elif self.kind == "warning":
            c.line(r, s * 0.43, r, s * 0.75)
            c.circle(r, s * 0.25, s * 0.075, fill=1, stroke=0)
        else:
            c.circle(r, r, s * 0.14, fill=1, stroke=0)


class ScoreBar(Flowable):
    def __init__(self, score, tone: str, width: float, height: float = 6):
        super().__init__()
        self.score, self.tone, self.width, self.height = score, tone, width, height

    def wrap(self, *_):
        return self.width, self.height + 2

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(PAPER)
        c.roundRect(0, 1, w, h, h / 2, fill=1, stroke=0)
        if self.score is not None:
            c.setFillColor(TONE[self.tone])
            c.roundRect(0, 1, max(h, w * max(0, min(100, self.score)) / 100), h, h / 2, fill=1, stroke=0)


class PhaseIcon(Flowable):
    """Ring filled a quarter per phase, with the phase number: 1 immediate ... 4 long term."""

    def __init__(self, n: int, size: float = 26):
        super().__init__()
        self.n, self.size = n, size
        self.width = self.height = size

    def wrap(self, *_):
        return self.size, self.size

    def draw(self):
        c, s = self.canv, self.size
        r = s / 2
        c.setLineWidth(3)
        c.setStrokeColor(BRASS_LIGHT)
        c.circle(r, r, r - 2, fill=0, stroke=1)
        c.setStrokeColor(BRASS)
        c.setLineCap(1)
        p = c.beginPath()
        p.arc(2, 2, s - 2, s - 2, startAng=90, extent=-90 * self.n)
        c.drawPath(p, stroke=1, fill=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", s * 0.42)
        c.drawCentredString(r, r - s * 0.15, str(self.n))


def _image(png: bytes, max_w: float, max_h: float) -> Image:
    from PIL import Image as PILImage

    w, h = PILImage.open(io.BytesIO(png)).size
    k = min(max_w / w, max_h / h)
    img = Image(io.BytesIO(png), width=w * k, height=h * k)
    img.hAlign = "CENTER"
    return img


def _chip(text: str, tone: str, st, width: float | None = None, align: str = "LEFT") -> Table:
    t = Table([[Paragraph(esc(text), ParagraphStyle("c", parent=st["chip"], textColor=TONE[tone]))]],
              colWidths=[width] if width else None)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TONE_LIGHT[tone]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                           ("ROUNDEDCORNERS", [3, 3, 3, 3])]))
    t.hAlign = align
    return t


def _mark_text(tone: str, text: str, style, size: float = 9) -> Table:
    t = Table([[Mark(tone, size), Paragraph(text, style)]], colWidths=[size + 2.2 * mm, None])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _rows(items: list[tuple[Flowable, list]], width: float, gap: float = 3.5) -> Table:
    """Two-column list [mark | content]; the mark lines up with the first line of text."""
    t = Table([[m, c] for m, c in items], colWidths=[6 * mm, width - 6 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (0, -1), 2.6), ("TOPPADDING", (1, 0), (1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), gap)]))
    return t


def _kv_table(rows, st, label_w=42 * mm, width=CONTENT_W) -> Table:
    data = [[Paragraph(esc(k), st["cell"]), Paragraph(v if isinstance(v, str) and v.startswith("<") else esc(v),
                                                      st["cell_b"])] for k, v in rows]
    t = Table(data, colWidths=[label_w, width - label_w])
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 6.5), ("LEFTPADDING", (0, 0), (-1, -1), 9),
             ("LINEAFTER", (0, 0), (0, -1), 0.6, HAIRLINE), ("BOX", (0, 0), (-1, -1), 0.6, HAIRLINE),
             ("ROUNDEDCORNERS", [4, 4, 4, 4])]
    style += [("BACKGROUND", (0, i), (-1, i), PAPER) for i in range(0, len(data), 2)]
    t.setStyle(TableStyle(style))
    return t


def _grid_table(data, widths, header=True, extra=None) -> Table:
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, HAIRLINE),
             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
             ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), PAPER), ("LINEABOVE", (0, 0), (-1, 0), 0.5, HAIRLINE)]
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _score_card(score, band, tone, st, right) -> Table:
    left = [Paragraph(st["t"].ui("score_card_title"), st["cell_b"]),
            Paragraph(f"{score if score is not None else '-'}<font size='16' color='#5A6B7B'> / 100</font>",
                      st["big"]),
            _chip(band, tone, st, 36 * mm)]
    card = Table([[left, right]], colWidths=[66 * mm, CONTENT_W - 66 * mm])
    card.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBEFORE", (0, 0), (0, 0), 3, BRASS),
                              ("LEFTPADDING", (0, 0), (0, 0), 10), ("LEFTPADDING", (1, 0), (1, 0), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return card


# --- page decoration -----------------------------------------------------------------------------
def _grid_motif(c, x, y, size, color, width=0.8):
    """Small 3 x 3 Vastu grid with a centre dot (brand motif)."""
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.rect(x, y, size, size, stroke=1, fill=0)
    for k in (1, 2):
        c.line(x + size * k / 3, y, x + size * k / 3, y + size)
        c.line(x, y + size * k / 3, x + size, y + size * k / 3)
    c.setFillColor(color)
    c.circle(x + size / 2, y + size / 2, size * 0.07, fill=1, stroke=0)


def _footer(c, doc, brand):
    f = doc._fonts
    c.saveState()
    c.setFillColor(INK)
    c.rect(0, 0, PAGE_W, FOOTER_H, fill=1, stroke=0)
    _grid_motif(c, MARGIN_X, FOOTER_H / 2 - 3 * mm, 6 * mm, colors.white, 0.6)
    c.setFillColor(colors.white)
    draw_text(c, MARGIN_X + 8.5 * mm, FOOTER_H / 2 - 3, brand, f["bold"], 9, f["shaping"])
    c.setFont(f["regular"], 7.5)
    c.setFillColor(colors.HexColor("#B9C3CC"))
    note_x = MARGIN_X + 8.5 * mm + c.stringWidth(brand, f["bold"], 9) + 10
    note = doc._footer_note
    while note and c.stringWidth(note, f["regular"], 7.5) > PAGE_W - MARGIN_X - 14 * mm - note_x:
        note = note[:-2]
    draw_text(c, note_x, FOOTER_H / 2 - 3, note, f["regular"], 7.5, f["shaping"])
    box = 7.5 * mm
    c.setFillColor(BRASS)
    c.rect(PAGE_W - MARGIN_X - box, (FOOTER_H - box) / 2, box, box, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(PAGE_W - MARGIN_X - box / 2, FOOTER_H / 2 - 3, str(doc.page))
    c.restoreState()


def _header(c, doc):
    c.saveState()
    top = PAGE_H - HEADER_H
    c.setFillColor(INK)
    c.rect(0, top, PAGE_W, HEADER_H, fill=1, stroke=0)
    c.setFillColor(BRASS)
    c.rect(0, top - 1.2, PAGE_W, 1.2, fill=1, stroke=0)
    c.setFillColor(colors.white)
    draw_text(c, MARGIN_X, top + HEADER_H / 2 - 5, getattr(doc, "_page_section", ""), doc._fonts["bold"], 14,
              doc._fonts["shaping"])
    s = 8.5 * mm
    _grid_motif(c, PAGE_W - MARGIN_X - s, top + (HEADER_H - s) / 2, s, colors.HexColor("#C99A4B"), 0.9)
    c.restoreState()


def _cover_art(c, doc, brand):
    """Navy panel with a vector Vastu mandala: compass ring, 3 x 3 grid and the eight directions."""
    c.saveState()
    panel_h = PAGE_H * COVER_PANEL
    y0 = PAGE_H - panel_h
    c.setFillColor(INK)
    c.rect(0, y0, PAGE_W, panel_h, fill=1, stroke=0)
    cx, cy, R = PAGE_W * 0.7, y0 + panel_h * 0.5, panel_h * 0.4
    c.setStrokeColor(colors.HexColor("#2C4156"))
    c.setLineWidth(1)
    for k in (1.0, 0.86, 1.22):
        c.circle(cx, cy, R * k, fill=0, stroke=1)
    c.setStrokeColor(colors.HexColor("#C99A4B"))
    for i in range(72):
        a = math.radians(i * 5)
        inner = R * (0.9 if i % 9 == 0 else 0.95)
        c.setLineWidth(1.2 if i % 9 == 0 else 0.5)
        c.line(cx + math.sin(a) * inner, cy + math.cos(a) * inner, cx + math.sin(a) * R, cy + math.cos(a) * R)
    sq = R * 1.08
    _grid_motif(c, cx - sq / 2, cy - sq / 2, sq, colors.HexColor("#C99A4B"), 1.1)
    c.setFillColor(INK)
    c.circle(cx, cy, sq * 0.07 + 1, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#C99A4B"))
    c.setLineWidth(1.1)
    c.circle(cx, cy, sq * 0.05, fill=0, stroke=1)
    c.setFillColor(colors.HexColor("#C99A4B"))
    c.setFont("Helvetica-Bold", 7.5)
    for row, line in enumerate([["NW", "N", "NE"], ["W", "", "E"], ["SW", "S", "SE"]]):
        for col, code in enumerate(line):
            if code:
                c.drawCentredString(cx - sq / 2 + sq * (col + 0.5) / 3, cy + sq / 2 - sq * (row + 0.5) / 3 - 2.5, code)
    c.setFont("Helvetica-Bold", 10.5)
    c.setFillColor(colors.white)
    for label, ang in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        a = math.radians(ang)
        c.drawCentredString(cx + math.sin(a) * R * 1.11, cy + math.cos(a) * R * 1.11 - 3.7, label)
    f = doc._fonts
    _grid_motif(c, MARGIN_X, PAGE_H - 21 * mm, 7.5 * mm, colors.white, 0.8)
    c.setFillColor(colors.white)
    draw_text(c, MARGIN_X + 10.5 * mm, PAGE_H - 18.5 * mm, brand, f["bold"], 13, f["shaping"])
    c.setFont(f["regular"], 9.5)
    c.setFillColor(colors.HexColor("#B9C3CC"))
    draw_text(c, MARGIN_X, y0 + 19 * mm, doc._texts.ui("cover_kicker"), f["regular"], 9.5, f["shaping"])
    c.setFont(f["bold"], 17)
    c.setFillColor(colors.white)
    name = doc._cover_property
    while c.stringWidth(name, f["bold"], 17) > PAGE_W * 0.48 and len(name) > 4:
        name = name[:-2]
    draw_text(c, MARGIN_X, y0 + 10.5 * mm, name if name == doc._cover_property else name.rstrip() + "…",
              f["bold"], 17, f["shaping"])
    c.setFillColor(BRASS)
    c.rect(0, y0 - 1.5, PAGE_W, 1.5, fill=1, stroke=0)
    c.restoreState()


# --- sections ------------------------------------------------------------------------------------
def _section(title: str) -> list:
    """Section that always starts on a new page."""
    return [PageBreak(), SectionStart(title)]


def _soft_section(title: str, min_space: float = 90 * mm, first: list | None = None) -> list:
    """Section that continues on the current page when there is room for a meaningful start.
    `first` (the section's opening block) is kept on the same page as the heading."""
    head = [Spacer(1, 4 * mm), SectionStart(title, visible=True)]
    return [CondPageBreak(min_space), KeepTogether(head + (first or []))]


def _cover(r: dict, st) -> list:
    p, a, t = r["property"], r["assessment"], st["t"]
    score = r["overall_score"]
    out = [Paragraph(esc(r["report_title"]), st["title"]), Spacer(1, 1.5 * mm),
           Paragraph(esc(p["name"]) + (f" &nbsp;·&nbsp; {esc(p['address'])}" if p["address"] else ""),
                     st["subtitle"]),
           Spacer(1, 4 * mm),
           Paragraph(
               t.ui("cover_lead", name=esc(p["name"]), rule_set=esc(a["rule_set"]["name"]),
                    methodology=esc(a["rule_set"]["methodology"][:1].lower() + a["rule_set"]["methodology"][1:])),
               st["lead"]),
           Spacer(1, 5 * mm), Paragraph(t.ui("sec_executive"), st["h2"]),
           _kv_table([(t.ui("customer_name"), p["client_name"] or t.ui("not_specified")),
                      (t.ui("property"), p["name"]),
                      (t.ui("property_type"), p["property_type"]),
                      (t.ui("assessment_date"), a["date"]),
                      (t.ui("overall_compliance"),
                       f"<font size='11'>{score if score is not None else '-'} / 100</font>"
                       f"&nbsp;&nbsp;<font color='{_hex(TONE[r['score_tone']])}'>{esc(r['score_band'])}</font>")],
                     st),
           Spacer(1, 4 * mm)]
    out += [Paragraph(esc(t), ParagraphStyle("es", parent=st["body"], spaceAfter=4)) for t in r["executive_summary"]]
    return out


def _layout_section(r: dict, st, plan_png: bytes) -> list:
    p, a, t = r["property"], r["assessment"], st["t"]
    details = [(t.ui("property"), p["name"]), (t.ui("property_type"), p["property_type"])]
    if p["address"]:
        details.append((t.ui("address"), p["address"]))
    if p["built_up_area"]:
        details.append((t.ui("built_up_area"), p["built_up_area"]))
    details += [(t.ui("rooms_analysed"), str(p["rooms_count"])), (t.ui("north"), a["north_text"]),
                (t.ui("main_entrance"), t.ui("marked") if a["has_main_entrance"] else t.ui("not_marked")),
                (t.ui("rule_set"), t.ui("rule_set_value", name=a["rule_set"]["name"], version=a["rule_set"]["version"]))]
    half = math.ceil(len(details) / 2)
    col_w = CONTENT_W / 2 - 2.5 * mm
    pair = Table([[_kv_table(details[:half], st, 30 * mm, col_w), _kv_table(details[half:], st, 30 * mm, col_w)]],
                 colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (1, 0), (1, 0), 5 * mm)]))
    evaluate = [(Mark("action", 8), [Paragraph(t.ui("eval_line", label=esc(c["label"]), n=c["findings"],
                                                    s="s" if c["findings"] != 1 else "", weight=f"{c['weight']:.0%}"),
                                               st["cell"])])
                for c in r["categories"]]
    half = math.ceil(len(evaluate) / 2)
    ev = Table([[_rows(evaluate[:half], CONTENT_W / 2, 1), _rows(evaluate[half:], CONTENT_W / 2, 1)]],
               colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    ev.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    legend = Table([[_mark_text(k, t.ui(f"legend_{k}"), st["small"]) for k in ("positive", "warning", "major", "neutral")]],
                   colWidths=[CONTENT_W / 4] * 4)
    legend.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [
        pair, Spacer(1, 4 * mm),
        Paragraph(t.ui("layout_intro"), st["body"]),
        Paragraph(t.ui("what_evaluated"), st["h3"]), ev, Spacer(1, 3 * mm),
        _image(plan_png, CONTENT_W, 128 * mm), Spacer(1, 2.5 * mm), legend, Spacer(1, 1.5 * mm),
        Paragraph(t.ui("plan_note_start")
                  + (t.ui("plan_note_entrance") if a["has_main_entrance"] else t.ui("plan_note_no_entrance"))
                  + t.ui("plan_note_end"), st["small"]),
    ]


def _overview_section(r: dict, st) -> list:
    t = st["t"]
    data = [[Paragraph(t.ui(x), st["th"]) for x in ("th_no", "th_room", "th_room_type", "th_direction_zone",
                                                    "th_result", "th_room_score")]]
    extra = []
    for i, room in enumerate(r["rooms"], 1):
        data.append([Paragraph(f"<b>{room['number']}</b>", st["cell"]), Paragraph(esc(room["label"]), st["cell_b"]),
                     Paragraph(esc(room["room_type_label"]), st["cell"]),
                     Paragraph(esc(room["zone_name"] or "-"), st["cell"]),
                     _mark_text(room["tone"], esc(room["result"]), st["cell"]),
                     Paragraph(f"<b>{room['score']}%</b>" if room["score"] is not None else "-", st["cell"])])
        extra.append(("LINEBEFORE", (0, i), (0, i), 3, TONE[room["tone"]]))
    widths = [13 * mm, 37 * mm, 33 * mm, 34 * mm, 36 * mm, CONTENT_W - 153 * mm]
    out = [Paragraph(t.ui("overview_intro", n=len(r["rooms"]), s="s" if len(r["rooms"]) != 1 else ""), st["body"]),
           Spacer(1, 3 * mm), _grid_table(data, widths, extra=extra)]

    counts = r["counts"]
    tile_w = (CONTENT_W - 66 * mm) / 3
    tiles = Table([[Paragraph(f"<b>{counts[k]}</b>", ParagraphStyle("t", parent=st["body"], fontSize=20,
                                                                    leading=24, textColor=TONE[k]))
                    for k in ("positive", "warning", "major")],
                   [Paragraph(t.ui(x), st["small"]) for x in ("tile_positive", "tile_warning", "tile_major")]],
                  colWidths=[tile_w] * 3)
    tiles.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), TONE_LIGHT["positive"]),
                               ("BACKGROUND", (1, 0), (1, -1), TONE_LIGHT["warning"]),
                               ("BACKGROUND", (2, 0), (2, -1), TONE_LIGHT["major"]),
                               ("LINEAFTER", (0, 0), (1, -1), 4, colors.white),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, 0), 9),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
    bar_w = 50 * mm
    rows = [[Paragraph(t.ui(x) if x else "", st["th"])
             for x in ("th_category", "", "th_score", "th_earned", "th_findings", "th_weight")]]
    for c in r["categories"]:
        rows.append([Paragraph(esc(c["label"]), st["cell_b"]), ScoreBar(c["score"], c["tone"], bar_w),
                     Paragraph(f"<font color='{_hex(TONE[c['tone']])}'><b>{'-' if c['score'] is None else c['score']}"
                               "</b></font>", st["cell"]),
                     Paragraph(f"{c['earned']:g} / {c['possible']:g}", st["cell"]),
                     Paragraph(str(c["findings"]), st["cell"]), Paragraph(f"{c['weight']:.0%}", st["cell"])])
    cats = _grid_table(rows, [30 * mm, bar_w + 6 * mm, 16 * mm, 32 * mm, 20 * mm, CONTENT_W - 154 * mm])
    out += [CondPageBreak(105 * mm), Spacer(1, 7 * mm), Paragraph(t.ui("score_breakdown"), st["h2"]),
            _score_card(r["overall_score"], r["score_band"], r["score_tone"], st, tiles),
            Spacer(1, 5 * mm), cats, Spacer(1, 2 * mm), Paragraph(esc(r["scoring_method"]), st["small"])]

    zrows = [[Paragraph(t.ui(x), st["th"]) for x in ("th_zone", "th_coverage", "th_zone_rooms")]]
    for z in r["zones"]:
        tone = "positive" if z["coverage"] >= 90 else "warning" if z["coverage"] >= 60 else "major"
        zrows.append([Paragraph(esc(z["name"]), st["cell_b"]),
                      Paragraph(f"<font color='{_hex(TONE[tone])}'><b>{z['coverage']}%</b></font>", st["cell"]),
                      Paragraph(esc(", ".join(z["rooms"]) or "-"), st["cell"])])
    out += [CondPageBreak(80 * mm), Spacer(1, 7 * mm), Paragraph(t.ui("zone_summary"), st["h2"]),
            Paragraph(t.ui("zone_summary_note"), st["small"]), Spacer(1, 2 * mm),
            _grid_table(zrows, [48 * mm, 30 * mm, CONTENT_W - 78 * mm])]
    return out


def _room_card(room: dict, st, thumb: bytes | None, flip: bool) -> list:
    t = st["t"]
    score = t.ui("not_scored") if room["score"] is None else t.ui("score_chip", score=room["score"])
    title = Table([[Paragraph(t.ui("room_title", number=room["number"], label=esc(room["label"])), st["h2"]),
                    _chip(score, room["tone"], st, align="RIGHT")]], colWidths=[CONTENT_W - 34 * mm, 34 * mm])
    title.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    meta = Table([[Paragraph(t.ui(x), st["label"]) for x in ("meta_room_type", "meta_zone", "meta_direction",
                                                             "meta_result")],
                  [Paragraph(esc(room["room_type_label"]), st["cell_b"]),
                   Paragraph(esc(room["zone_name"] or "-"), st["cell_b"]),
                   Paragraph(esc(room["direction_name"] or "-"), st["cell_b"]),
                   _mark_text(room["tone"], f"<b>{esc(room['result'])}</b>", st["cell"])]],
                 colWidths=[CONTENT_W / 4] * 4)
    meta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PAPER), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                              ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
                              ("TOPPADDING", (0, 1), (-1, 1), 1), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LINEBEFORE", (0, 0), (0, -1), 3, TONE[room["tone"]])]))
    intro = [Paragraph(t.ui("room_intro"), ParagraphStyle("ri", parent=st["h3"], spaceBefore=0))]
    intro += [Paragraph(esc(t), ParagraphStyle("rb", parent=st["body"], spaceAfter=3)) for t in room["introduction"]]
    thumb_w = 62 * mm
    if thumb:
        img = _image(thumb, thumb_w, 56 * mm)
        text_w = CONTENT_W - thumb_w - 6 * mm
        body = Table([[intro, img]] if flip else [[img, intro]],
                     colWidths=[text_w, thumb_w + 6 * mm] if flip else [thumb_w + 6 * mm, text_w])
        body.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("ALIGN", (1 if flip else 0, 0), (1 if flip else 0, 0), "RIGHT" if flip else "LEFT")]))
    else:
        body = intro

    cons = [(Mark(c["tone"], 9), [Paragraph(esc(c["text"]), st["body"])]) for c in room["considerations"]]
    recs = []
    for rec in room["recommendations"]:
        parts = [Paragraph(esc(rec["action"]), st["body"])]
        tag = f"{rec['kind_label']} · " + t.ui("priority_tag", priority=t.priority(rec["priority"]))
        if not rec["approved"]:
            tag += t.ui("placeholder_tag")
        if rec["visual"]:
            tag += t.ui("on_plan_tag", visual=rec["visual"])
        parts.append(Paragraph(esc(tag), st["small"]))
        if rec["structural_note"]:
            parts.append(Paragraph(f"<font color='{_hex(TONE['major'])}'><b>{t.ui('structural_option_needs')}"
                                   f"</b></font> {esc(rec['structural_note'])}", st["small"]))
        recs.append((Mark("action", 8), parts))
    if not recs:
        recs = [(Mark("neutral", 9), [Paragraph(t.ui("no_corrective"), st["body"])])]
    # A room card is kept on one page whenever it fits, so a room is never split from its
    # recommendations; an unusually long card can still break between its blocks.
    return [KeepTogether([title, Spacer(1, 1.5 * mm), meta, Spacer(1, 4 * mm), body,
                          Paragraph(t.ui("considerations"), st["h3"]), _rows(cons, CONTENT_W),
                          Paragraph(t.ui("recommendations"), st["h3"]), _rows(recs, CONTENT_W),
                          Spacer(1, 2 * mm),
                          HRFlowable(width="100%", thickness=0.6, color=HAIRLINE, spaceAfter=7 * mm)])]


def _findings_section(r: dict, st) -> list:
    t = st["t"]
    out = [Paragraph(t.ui("findings_intro"), st["body"]), Spacer(1, 4 * mm)]
    for key in ("positive", "warning", "major"):
        title, empty = t.ui(f"findings_{key}"), t.ui(f"findings_empty_{key}")
        items = r["findings"][key]
        head = _mark_text(key, f"<b>{title} ({len(items)})</b>",
                          ParagraphStyle("fh", parent=st["h3"], textColor=TONE[key], spaceBefore=0, spaceAfter=0), 11)
        band = Table([[head]], colWidths=[CONTENT_W])
        band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TONE_LIGHT[key]), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        rows = [(Mark(key, 9), [Paragraph(f"<b>{esc(f['subject'])}</b>: {esc(f['text'])}", st["body"])]
                 + ([Paragraph(esc(f["explanation"]), st["small"])] if f["explanation"] else []))
                for f in items] or [(Mark("neutral", 9), [Paragraph(empty, st["body"])])]
        out.append(KeepTogether([band, Spacer(1, 3 * mm), _rows(rows[:2], CONTENT_W)]))
        if len(rows) > 2:
            out.append(_rows(rows[2:], CONTENT_W))
        out.append(Spacer(1, 5 * mm))
    return out


def _remedies_section(r: dict, st) -> list:
    t = st["t"]
    out = [Paragraph(t.ui("remedies_intro"), st["body"]), Spacer(1, 4 * mm)]
    phase_style = ParagraphStyle("ph", parent=st["h3"], spaceBefore=3, spaceAfter=3)
    for i, phase in enumerate(r["remedy_plan"], 1):
        items = [(Mark("action", 8),
                  [Paragraph(f"<b>{esc(it['subject'])}</b>: {esc(it['text'])}"
                             + (f" <font color='{_hex(TONE['major'])}'>{t.ui('structural_needed')}</font>"
                                if it["structural"] else ""), st["body"])])
                 for it in phase["items"]] or [(Mark("neutral", 9), [Paragraph(t.ui("nothing_scheduled"),
                                                                                 st["small"])])]
        block = Table([[PhaseIcon(i), [Paragraph(phase["label"], phase_style), _rows(items, CONTENT_W - 15 * mm, 3)]]],
                      colWidths=[15 * mm, CONTENT_W - 15 * mm])
        block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        out.append(block)

    if r["remedies"]:
        out += [CondPageBreak(70 * mm), Spacer(1, 5 * mm), Paragraph(t.ui("remedy_details"), st["h2"])]
        for rem in r["remedies"]:
            tone = {"high": "major", "medium": "warning"}.get(rem["priority"], "neutral")
            rows = [[Paragraph(t.ui("why_it_matters"), st["label"]),
                     Paragraph(esc(" ".join(x for x in (rem["why"], rem["rule_explanation"]) if x)), st["cell"])],
                    [Paragraph(t.ui("recommended_action"), st["label"]), Paragraph(esc(rem["action"]), st["cell"])]]
            if rem["visual"]:
                rows.append([Paragraph(t.ui("on_the_plan"), st["label"]), Paragraph(esc(rem["visual"]), st["cell"])])
            if rem["structural_note"]:
                rows.append([Paragraph(t.ui("structural_option"), st["label"]),
                             Paragraph(esc(rem["structural_note"]) + t.ui("consult_professional"), st["cell"])])
            if not rem["approved"]:
                rows.append([Paragraph(t.ui("note"), st["label"]),
                             Paragraph(t.ui("no_approved_remedy"), st["cell"])])
            chips = Table([[_chip(t.priority_chip(rem["priority"]), tone, st),
                            _chip(rem["kind_label"], "neutral", st)]])
            chips.hAlign = "RIGHT"
            chips.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
            where = esc(rem["subject"]) + (f" · {esc(rem['zone_name'])}" if rem["zone_name"] else "")
            title = Table([[Paragraph(f"<b>{esc(rem['problem'])}</b><br/><font color='#5A6B7B'>{where}</font>",
                                      st["cell"]), chips]], colWidths=[CONTENT_W - 72 * mm, 54 * mm])
            title.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                       ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
            detail = Table(rows, colWidths=[32 * mm, CONTENT_W - 32 * mm - 18 * mm])
            detail.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
            card = Table([[[title, Spacer(1, 3), detail]]], colWidths=[CONTENT_W])
            card.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 3, TONE[tone]),
                                      ("LINEABOVE", (0, 0), (-1, 0), 0.5, HAIRLINE),
                                      ("LINEBELOW", (0, -1), (-1, -1), 0.5, HAIRLINE),
                                      ("LINEAFTER", (-1, 0), (-1, -1), 0.5, HAIRLINE),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                      ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            out += [KeepTogether(card), Spacer(1, 4 * mm)]
    return out


def _summary_section(r: dict, st) -> list:
    fs, t, c = r["final_summary"], st["t"], r["counts"]
    score = fs["score"]
    text = Paragraph(t.ui("summary_lead", score=score if score is not None else "-", rule_set=esc(fs["rule_set"]),
                          pos=c["positive"], ps="" if c["positive"] == 1 else "s",
                          warn=c["warning"], ws="" if c["warning"] == 1 else "s",
                          maj=c["major"], ms="" if c["major"] == 1 else "s",
                          rooms=r["property"]["rooms_count"]), st["lead"])
    pad = Table([[text]], colWidths=[CONTENT_W - 66 * mm])
    pad.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 6)]))

    def marked(items, empty):
        if not items:
            return _rows([(Mark("neutral", 9), [Paragraph(empty, st["body"])])], CONTENT_W)
        return _rows([(Mark(i["tone"], 9), [Paragraph(esc(i["text"]), st["body"])]) for i in items], CONTENT_W, 3)

    def ordered(items):
        t = Table([[Paragraph(f"<b>{i}</b>", ParagraphStyle("n", parent=st["body"], textColor=BRASS)),
                    Paragraph(esc(x), st["body"])] for i, x in enumerate(items, 1)],
                  colWidths=[6 * mm, CONTENT_W - 6 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
        return t

    out = [_score_card(score, fs["band"], r["score_tone"], st, pad), Spacer(1, 6 * mm),
           KeepTogether([Paragraph(t.ui("strongest"), st["h3"]),
                         marked(fs["strengths"], t.ui("no_positive"))]),
           KeepTogether([Paragraph(t.ui("needing_attention"), st["h3"]),
                         marked(fs["weaknesses"], t.ui("nothing_flagged"))])]
    if fs["priorities"]:
        out.append(KeepTogether([Paragraph(t.ui("top_priorities"), st["h3"]), ordered(fs["priorities"])]))
    out.append(KeepTogether([Paragraph(t.ui("next_steps"), st["h3"]), ordered(fs["next_steps"])]))
    return out


def _action_plan_section(ap: dict, st) -> list:
    """Personal action plan (see reports/action_plan.py): the insight tools applied to this household."""
    out = [Paragraph(esc(ap["intro"]), st["lead"]), Spacer(1, 3 * mm)]

    def bullets(items, key="text"):
        return _rows([(Mark(i.get("tone") or {"major": "major", "warning": "warning"}.get(i.get("bucket"), "action"), 8.5),
                       [Paragraph((f"<b>{esc(i['subject'])}</b>: " if i.get("subject") else "") + esc(i[key])
                                  + (f" <font color='{_hex(MUTED)}'>({esc(i['deadline'])})</font>" if i.get("deadline") else ""),
                                  st["body"])]) for i in items], CONTENT_W, 3)

    sc = ap["score"]
    if sc["items"]:
        rows = [[Paragraph(f"<b>{esc(i['subject'])}</b>: {esc(i['text'])}", st["cell"]),
                 _chip(i["gain"], "positive", st, align="RIGHT")] for i in sc["items"]]
        tbl = Table(rows, colWidths=[CONTENT_W - 34 * mm, 34 * mm])
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                 ("LINEBELOW", (0, 0), (-1, -2), 0.4, HAIRLINE), ("ALIGN", (1, 0), (1, -1), "RIGHT")]))
        block = [Paragraph(esc(sc["heading"]), st["h3"]), Paragraph(esc(sc["intro"]), st["small"]), Spacer(1, 2 * mm), tbl]
        if sc["ceiling"]:
            block += [Spacer(1, 2 * mm), Paragraph(esc(sc["ceiling"]), st["small"])]
        out.append(KeepTogether(block))

    tr = ap["trust"]
    head = Table([[Paragraph(esc(tr["heading"]), st["h3"]), _chip(tr["label"], tr["tone"], st, align="RIGHT")]],
                 colWidths=[CONTENT_W - 50 * mm, 50 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    out.append(KeepTogether([Spacer(1, 3 * mm), head,
                             bullets(tr["reasons"]) if tr["reasons"] else Paragraph(esc(tr["none"]), st["body"])]))

    fit = ap.get("fit")
    if fit:
        out += [CondPageBreak(60 * mm), Spacer(1, 3 * mm), Paragraph(esc(fit["heading"]), st["h3"]),
                Paragraph(esc(fit["situation"]) + " " + esc(fit["summary"]), st["body"]), Spacer(1, 3 * mm)]
        for it in fit["items"]:
            lines = [Paragraph(f"<b>{esc(it['subject'])}</b> · {esc(it['problem'])}", st["cell"])]
            if it["action"]:
                lines.append(Paragraph(f"<font color='{_hex(MUTED)}'>{esc(fit['do_this'])} · {esc(it['option'])}:</font> "
                                       + esc(it["action"]), st["cell"]))
            for c in it["conditions"]:
                lines.append(Paragraph(f"<font color='{_hex(TONE['warning'])}'>! {esc(c)}</font>", st["small"]))
            for c in it["not_possible"]:
                lines.append(Paragraph(f"{esc(fit['why_not'])} · {esc(c)}", st["small"]))
            card = Table([[lines, _chip(it["verdict_label"], it["tone"], st, align="RIGHT")]],
                         colWidths=[CONTENT_W - 46 * mm, 40 * mm])
            card.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBEFORE", (0, 0), (0, -1), 3, TONE[it["tone"]]),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                      ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                      ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
            out += [KeepTogether(card), Spacer(1, 2.5 * mm)]

    stg = ap.get("stage")
    if stg:
        block = [Spacer(1, 3 * mm), Paragraph(esc(stg["heading"]), st["h3"]), Paragraph(esc(stg["description"]), st["small"]),
                 Spacer(1, 2 * mm), Paragraph(f"<b>{esc(stg['act_now_h'])}</b>", st["body"]), Spacer(1, 1.5 * mm),
                 bullets(stg["act_now"]) if stg["act_now"] else Paragraph(esc(stg["act_none"]), st["body"])]
        out += [CondPageBreak(50 * mm), KeepTogether(block)]
        if stg["checklist"]:
            out.append(KeepTogether([Spacer(1, 3 * mm), Paragraph(f"<b>{esc(stg['checklist_h'])}</b>", st["body"]),
                                     Spacer(1, 1.5 * mm),
                                     _rows([(Mark("neutral", 8), [Paragraph(esc(x), st["body"])]) for x in stg["checklist"]],
                                           CONTENT_W, 3)]))

    fam = ap.get("family")
    if fam:
        rows = [[Paragraph(f"<b>{i}</b>", ParagraphStyle("n", parent=st["body"], textColor=BRASS)),
                 Paragraph(f"<b>{esc(x['subject'])}</b>: {esc(x['text'])}", st["body"])]
                for i, x in enumerate(fam["order"], 1)]
        tbl = Table(rows or [["", Paragraph("—", st["body"])]], colWidths=[6 * mm, CONTENT_W - 6 * mm])
        tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
        out += [CondPageBreak(45 * mm), KeepTogether([Spacer(1, 3 * mm), Paragraph(esc(fam["heading"]), st["h3"]),
                                                      Paragraph(esc(fam["intro"]), st["body"]), Spacer(1, 2 * mm),
                                                      Paragraph(f"<b>{esc(fam['order_h'])}</b>", st["body"]),
                                                      Spacer(1, 1.5 * mm), tbl])]
    if ap.get("not_set"):
        out += [Spacer(1, 4 * mm), _rows([(Mark("neutral", 8), [Paragraph(esc(ap["not_set"]), st["small"])])], CONTENT_W)]
    return out


def _disclaimer_section(r: dict, st) -> list:
    t = st["t"]
    italic = ParagraphStyle("it", parent=st["body"], fontName=st["fonts"]["italic"])
    return [Paragraph(esc(r["disclaimer"]["rule_set"]), italic), Spacer(1, 4 * mm),
            _rows([(Mark("neutral", 8), [Paragraph(esc(p), st["body"])]) for p in r["disclaimer"]["points"]],
                  CONTENT_W, 5),
            Spacer(1, 6 * mm),
            Paragraph(t.ui("generated_by", brand=esc(r["brand"]), date=esc(r["generated_on"]),
                           plan=esc(r["assessment"]["plan_file"]), rule_set=esc(r["assessment"]["rule_set"]["name"]),
                           version=esc(r["assessment"]["rule_set"]["version"])), st["small"])]


# --- document ------------------------------------------------------------------------------------
def build_pdf(report: dict, plan_png: bytes, room_thumbs: dict[str, bytes], language: str = "en") -> bytes:
    t, fonts = texts_for(language), _fonts(language)
    st = _styles(t, fonts)
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title=t.ui("doc_title", name=report["property"]["name"]),
                          author=report["brand"], subject=t.ui("doc_subject"), lang=None if language == "en" else language)
    doc._texts, doc._fonts = t, fonts
    doc._section = t.ui("sec_executive")  # shown if the summary runs past the cover
    doc._cover_property = report["property"]["name"]
    doc._footer_note = t.ui("footer_note", name=report["property"]["name"], date=report["generated_on"])
    brand = report["brand"]

    bottom = FOOTER_H + 9 * mm
    cover_top = PAGE_H * COVER_PANEL + 10 * mm
    cover_frame = Frame(MARGIN_X, bottom, CONTENT_W, PAGE_H - cover_top - bottom, id="cover",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    body_frame = Frame(MARGIN_X, bottom, CONTENT_W, PAGE_H - HEADER_H - 10 * mm - bottom, id="body",
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame],
                     onPage=lambda c, d: (_cover_art(c, d, brand), _footer(c, d, brand))),
        PageTemplate(id="content", frames=[body_frame],
                     onPage=lambda c, d: setattr(d, "_page_section", d._section),
                     onPageEnd=lambda c, d: (_header(c, d), _footer(c, d, brand))),
    ])

    story = [NextPageTemplate("content")]
    story += _cover(report, st)
    story += _section(t.ui("sec_layout")) + _layout_section(report, st, plan_png)
    story += _section(t.ui("sec_overview")) + _overview_section(report, st)
    cards = [_room_card(room, st, room_thumbs.get(room["id"]), flip=i % 2 == 1)
             for i, room in enumerate(report["rooms"])]
    if cards:
        story += _soft_section(t.ui("sec_rooms"), 110 * mm, first=cards[0])
        for card in cards[1:]:
            story += card
    findings = _findings_section(report, st)
    story += _soft_section(t.ui("sec_findings"), 90 * mm, first=findings[:3]) + findings[3:]
    story += _section(t.ui("sec_remedies")) + _remedies_section(report, st)
    if report.get("action_plan"):
        story += _section(report["action_plan"]["title"]) + _action_plan_section(report["action_plan"], st)
    story += _section(t.ui("sec_summary")) + _summary_section(report, st)
    story += _soft_section(t.ui("sec_disclaimer"), 110 * mm) + _disclaimer_section(report, st)
    doc.build(story)
    return buf.getvalue()
