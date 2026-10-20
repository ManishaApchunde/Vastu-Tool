"""Upload validation and normalization: verify real file type, rasterize PDFs, strip metadata,
produce a PNG preview and a blur/quality estimate."""
import io
from dataclasses import dataclass, field

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import AppError

MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg", b"%PDF-": "application/pdf"}
EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf"}


@dataclass
class PreparedUpload:
    content_type: str
    preview_png: bytes
    width: int
    height: int
    quality: dict = field(default_factory=dict)


def sniff(data: bytes) -> str | None:
    return next((ct for sig, ct in MAGIC.items() if data.startswith(sig)), None)


def validate_and_prepare(filename: str, data: bytes) -> PreparedUpload:
    if not data:
        raise AppError("empty_file", "The file is empty.", 400)
    if len(data) > settings.max_upload_bytes:
        raise AppError("file_too_large", f"The file is larger than {settings.max_upload_mb} MB.", 413,
                       "Export the plan at a lower resolution or compress it, then upload again.")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in EXT:
        raise AppError("unsupported_format", "Upload a JPG, PNG or PDF floor plan.", 415)
    actual = sniff(data)
    if actual is None or actual != EXT[ext]:
        raise AppError("invalid_file", "The file content doesn't match its extension or is corrupted.", 400)

    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels
    try:
        img = _rasterize_pdf(data) if actual == "application/pdf" else _open_image(data)
    except Image.DecompressionBombError as exc:
        raise AppError("image_too_large", "The image resolution is too high to process safely.", 413) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise AppError("invalid_file", "The file couldn't be read as a floor plan image.", 400) from exc

    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < settings.min_image_side:
        raise AppError("image_too_small", f"The plan is too small (under {settings.min_image_side}px on a side).", 400,
                       "Upload a higher-resolution export of the plan.")
    img.thumbnail((2400, 2400))  # working resolution for AI + display
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)  # re-encoding also drops metadata
    return PreparedUpload(actual, buf.getvalue(), img.width, img.height, assess_quality(img))


def _open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.verify()
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def _rasterize_pdf(data: bytes) -> Image.Image:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise AppError("invalid_file", "The PDF couldn't be opened. It may be damaged or password-protected.",
                       400) from exc
    if len(pdf) == 0:
        raise AppError("invalid_file", "The PDF has no pages.", 400)
    page = pdf[0]
    scale = min(3.0, 2400 / max(page.get_width(), page.get_height()))
    return page.render(scale=max(scale, 1.0)).to_pil()


def assess_quality(img: Image.Image) -> dict:
    gray = img.convert("L")
    gray.thumbnail((1200, 1200))
    lap = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
    blur_score = round(ImageStat.Stat(lap).var[0], 1)
    contrast = round(ImageStat.Stat(gray).stddev[0], 1)
    warnings = []
    if blur_score < settings.blur_threshold:
        warnings.append("The plan looks blurry. Detection may miss rooms or labels; check them carefully.")
    if contrast < 20:
        warnings.append("The plan has low contrast. Detection may be unreliable.")
    return {"blur_score": blur_score, "contrast": contrast, "warnings": warnings}
