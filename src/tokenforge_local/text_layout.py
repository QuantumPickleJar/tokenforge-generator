from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import FontReference, TextLayoutConfig

SYSTEM_FONT_CANDIDATES = {
    "DejaVu Sans": ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "DejaVu Serif": ["DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "DejaVu Sans Bold": ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


def available_font_labels(imported_fonts: list[FontReference] | None = None) -> list[str]:
    labels = list(SYSTEM_FONT_CANDIDATES)
    for font in imported_fonts or []:
        if font.family not in labels:
            labels.append(font.family)
    return labels


def resolve_font_path(font_family: str, imported_fonts: list[FontReference] | None = None) -> str | None:
    for font in imported_fonts or []:
        if font.family == font_family and font.path and Path(font.path).exists():
            return font.path
    for candidate in SYSTEM_FONT_CANDIDATES.get(font_family, SYSTEM_FONT_CANDIDATES["DejaVu Sans"]):
        if Path(candidate).exists():
            return candidate
    return None


def load_font(font_family: str, size_px: int, imported_fonts: list[FontReference] | None = None) -> ImageFont.ImageFont:
    path = resolve_font_path(font_family, imported_fonts)
    if path:
        try:
            return ImageFont.truetype(path, size_px)
        except OSError:
            pass
    return ImageFont.load_default()


def render_text_mask(size: tuple[int, int], config: TextLayoutConfig, y_anchor: str, imported_fonts: list[FontReference] | None = None) -> Image.Image:
    """Render title or rules text to a grayscale mask.

    Parameters:
        size: Target composition size in pixels.
        config: Text settings to render.
        y_anchor: Either "top" or "bottom"; controls default vertical placement.
        imported_fonts: Future v0.2 local font references. Missing fonts fall back safely.
    """
    width, height = size
    mask = Image.new("L", size, 0)
    if not config.enabled or not config.content.strip():
        return mask

    draw = ImageDraw.Draw(mask)
    text = config.content.upper() if config.uppercase else config.content
    font = load_font(config.font_family, config.size_px, imported_fonts)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2 + config.offset_x_px
    if y_anchor == "top":
        y = int(height * 0.055) + config.offset_y_px
    else:
        y = int(height * 0.805) + config.offset_y_px
    draw.text((x, y), text, fill=255, font=font)
    return mask


def render_banner_mask(size: tuple[int, int], config: TextLayoutConfig, y_anchor: str) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    if not config.enabled or not config.banner_enabled:
        return mask
    draw = ImageDraw.Draw(mask)
    if y_anchor == "top":
        y0 = int(height * 0.035) + config.offset_y_px
        y1 = y0 + max(42, int(config.size_px * 1.55))
    else:
        y1 = int(height * 0.92) + config.offset_y_px
        y0 = y1 - max(48, int(config.size_px * 2.0))
    margin = int(width * 0.075)
    radius = max(8, int(width * 0.025))
    draw.rounded_rectangle((margin, y0, width - margin, y1), radius=radius, fill=255)
    return mask
