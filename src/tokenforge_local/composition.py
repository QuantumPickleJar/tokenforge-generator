from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .models import FontReference, StyleSettings, TokenDefaults
from .style_presets import fallback_if_unimplemented
from .text_layout import render_banner_mask, render_text_mask
from .utils import ensure_rgb


@dataclass(slots=True)
class CompositionResult:
    image: Image.Image
    style_height_mask: Image.Image
    rounded_token_mask: Image.Image


def rounded_token_mask(size: tuple[int, int], token: TokenDefaults) -> Image.Image:
    width_px, height_px = size
    radius_px = max(1, int(round(width_px * (token.corner_radius_mm / token.width_mm))))
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, width_px - 1, height_px - 1), radius=radius_px, fill=255)
    return mask


def _draw_border_mask(size: tuple[int, int], settings: StyleSettings) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    if not settings.border_enabled:
        return mask
    draw = ImageDraw.Draw(mask)
    thickness = max(2, settings.border_thickness_px)
    radius = max(8, int(width * 0.04))
    style = fallback_if_unimplemented(settings.border_style)

    def inset_rect(inset: int) -> tuple[int, int, int, int]:
        return (inset, inset, width - 1 - inset, height - 1 - inset)

    if style == "thin_line":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=255, width=max(2, thickness // 3))
    elif style == "double_line":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=255, width=max(2, thickness // 4))
        draw.rounded_rectangle(inset_rect(thickness * 2), radius=max(2, radius - thickness), outline=255, width=max(2, thickness // 5))
    elif style == "inset_panel":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=255, width=thickness)
        draw.rounded_rectangle(inset_rect(thickness * 3), radius=max(2, radius - thickness), outline=150, width=max(2, thickness // 5))
    elif style == "simple_plaque":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=255, width=thickness)
        for cx, cy in [(thickness * 2, thickness * 2), (width - thickness * 2, thickness * 2), (thickness * 2, height - thickness * 2), (width - thickness * 2, height - thickness * 2)]:
            draw.ellipse((cx - thickness, cy - thickness, cx + thickness, cy + thickness), fill=255)
    elif style == "wood_frame":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=255, width=thickness)
        for i in range(0, height, max(10, thickness)):
            draw.line((thickness, i, width - thickness, i + thickness // 2), fill=140, width=max(1, thickness // 8))
    elif style == "riveted_metal":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=230, width=thickness)
        step = max(24, thickness * 2)
        rivet_r = max(3, thickness // 4)
        for x in range(thickness * 2, width - thickness * 2 + 1, step):
            draw.ellipse((x - rivet_r, thickness - rivet_r, x + rivet_r, thickness + rivet_r), fill=255)
            draw.ellipse((x - rivet_r, height - thickness - rivet_r, x + rivet_r, height - thickness + rivet_r), fill=255)
        for y in range(thickness * 2, height - thickness * 2 + 1, step):
            draw.ellipse((thickness - rivet_r, y - rivet_r, thickness + rivet_r, y + rivet_r), fill=255)
            draw.ellipse((width - thickness - rivet_r, y - rivet_r, width - thickness + rivet_r, y + rivet_r), fill=255)
    elif style == "diamond_plate":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=220, width=thickness)
        spacing = max(18, thickness)
        for y in range(-height, height * 2, spacing):
            draw.line((0, y, width, y + width), fill=140, width=max(1, thickness // 10))
            draw.line((width, y, 0, y + width), fill=140, width=max(1, thickness // 10))
    elif style == "stone_frame":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=235, width=thickness)
        block = max(18, thickness)
        for x in range(thickness, width - thickness, block):
            draw.line((x, 0, x, thickness * 2), fill=120, width=max(1, thickness // 8))
            draw.line((x, height - thickness * 2, x, height), fill=120, width=max(1, thickness // 8))
        for y in range(thickness, height - thickness, block):
            draw.line((0, y, thickness * 2, y), fill=120, width=max(1, thickness // 8))
            draw.line((width - thickness * 2, y, width, y), fill=120, width=max(1, thickness // 8))
    elif style == "marble_frame":
        draw.rounded_rectangle(inset_rect(thickness // 2), radius=radius, outline=230, width=thickness)
        for i in range(0, width + height, max(14, thickness // 2)):
            draw.line((i, 0, i - height // 2, height), fill=120, width=max(1, thickness // 12))
    return mask.filter(ImageFilter.GaussianBlur(radius=0.2))


def _apply_mask_color(base: Image.Image, mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    overlay = Image.new("RGB", base.size, color)
    base.paste(overlay, mask=mask)
    return base


def build_styled_composition(
    prepared_art: Image.Image,
    token: TokenDefaults,
    settings: StyleSettings,
    imported_fonts: list[FontReference] | None = None,
    output_size: tuple[int, int] = (630, 879),
) -> CompositionResult:
    """Compose user art, procedural frame, banners, text, and badge into one image.

    Parameters:
        prepared_art: Confirmed/cropped user image, not the raw upload.
        token: Physical token dimensions used to derive rounded-corner mask.
        settings: Style settings that affect both preview and STL height mask.
        imported_fonts: Future local font metadata. Missing font paths fall back.
        output_size: Working preview size in pixels.
    """
    size = output_size
    art = ensure_rgb(prepared_art).resize(size, Image.Resampling.LANCZOS)
    token_mask = rounded_token_mask(size, token)
    base = Image.new("RGB", size, "white")
    base.paste(art, mask=token_mask)
    height_mask = Image.new("L", size, 0)

    if settings.background_panel_enabled:
        panel = Image.new("L", size, 0)
        draw = ImageDraw.Draw(panel)
        margin = int(size[0] * 0.055)
        draw.rounded_rectangle((margin, margin, size[0] - margin, size[1] - margin), radius=int(size[0] * 0.04), fill=80)
        height_mask = Image.composite(Image.new("L", size, 80), height_mask, panel)
        base = _apply_mask_color(base, panel, (225, 218, 200))

    border = _draw_border_mask(size, settings)
    base = _apply_mask_color(base, border, (35, 35, 35))
    height_mask = Image.composite(Image.new("L", size, 180), height_mask, border)

    for config, anchor, banner_color, text_color, emboss_value in [
        (settings.title_text, "top", (238, 232, 212), (20, 20, 20), 230),
        (settings.bottom_text, "bottom", (238, 232, 212), (20, 20, 20), 210),
    ]:
        banner = render_banner_mask(size, config, anchor)
        if config.enabled and config.banner_enabled:
            base = _apply_mask_color(base, banner, banner_color)
            height_mask = Image.composite(Image.new("L", size, 120), height_mask, banner)
        text_mask = render_text_mask(size, config, anchor, imported_fonts)
        if config.enabled:
            base = _apply_mask_color(base, text_mask, text_color)
            if config.emboss_mode == "emboss":
                height_mask = Image.composite(Image.new("L", size, emboss_value), height_mask, text_mask)
            else:
                height_mask = Image.composite(Image.new("L", size, 10), height_mask, text_mask)

    if settings.simple_badge_enabled:
        badge = Image.new("L", size, 0)
        draw = ImageDraw.Draw(badge)
        cx, cy = int(size[0] * 0.82), int(size[1] * 0.16)
        r = int(size[0] * 0.07)
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else int(r * 0.52)
            points.append((cx + int(math.cos(angle) * rr), cy + int(math.sin(angle) * rr)))
        draw.polygon(points, fill=255)
        base = _apply_mask_color(base, badge, (190, 150, 50))
        height_mask = Image.composite(Image.new("L", size, 240), height_mask, badge)

    # Outside the rounded token must stay blank and must not become geometry.
    blank = Image.new("RGB", size, "white")
    blank.paste(base, mask=token_mask)
    height_mask = Image.composite(height_mask, Image.new("L", size, 0), token_mask)
    return CompositionResult(blank, height_mask, token_mask)


def make_layer_preview(indices: np.ndarray, colors: list[tuple[int, int, int]]) -> Image.Image:
    palette = np.asarray(colors, dtype=np.uint8)
    return Image.fromarray(palette[indices], mode="RGB")
