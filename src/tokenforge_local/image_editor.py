from __future__ import annotations

from PIL import Image, ImageDraw

from .models import CropTransform, TokenDefaults
from .composition import rounded_token_mask
from .utils import ensure_rgb


def default_crop_transform(source_image: str | None, token: TokenDefaults, px_per_mm: int = 10) -> CropTransform:
    return CropTransform(
        source_image=source_image,
        output_width_px=int(round(token.width_mm * px_per_mm)),
        output_height_px=int(round(token.height_mm * px_per_mm)),
    )


def apply_crop_transform(source: Image.Image, transform: CropTransform) -> Image.Image:
    """Apply pan, scale, and 90-degree rotation against the token output frame.

    Parameters:
        source: User-uploaded image.
        transform: Saved crop/transform values. The output size comes from this object.
    """
    image = ensure_rgb(source)
    rotation = transform.rotation_degrees % 360
    if rotation:
        image = image.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)

    output_size = (transform.output_width_px, transform.output_height_px)
    out_w, out_h = output_size
    src_w, src_h = image.size
    fit_scale = max(out_w / src_w, out_h / src_h)
    scale = max(0.05, transform.scale) * fit_scale
    resized = image.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", output_size, "white")
    x = (out_w - resized.width) // 2 + int(transform.pan_x_px)
    y = (out_h - resized.height) // 2 + int(transform.pan_y_px)
    canvas.paste(resized, (x, y))
    return canvas


def preview_with_stencil(source: Image.Image, transform: CropTransform, token: TokenDefaults) -> Image.Image:
    prepared = apply_crop_transform(source, transform)
    overlay = prepared.copy().convert("RGBA")
    mask = rounded_token_mask(prepared.size, token)
    dim = Image.new("RGBA", prepared.size, (0, 0, 0, 120))
    clear = Image.new("RGBA", prepared.size, (0, 0, 0, 0))
    outside = Image.composite(clear, dim, mask)
    overlay.alpha_composite(outside)
    draw = ImageDraw.Draw(overlay)
    radius_px = max(1, int(round(prepared.width * (token.corner_radius_mm / token.width_mm))))
    draw.rounded_rectangle((0, 0, prepared.width - 1, prepared.height - 1), radius=radius_px, outline=(255, 255, 255, 240), width=max(3, prepared.width // 140))
    draw.rounded_rectangle((8, 8, prepared.width - 9, prepared.height - 9), radius=max(1, radius_px - 8), outline=(0, 0, 0, 190), width=max(1, prepared.width // 260))
    return overlay.convert("RGB")


def reset_transform(transform: CropTransform) -> CropTransform:
    return CropTransform(
        source_image=transform.source_image,
        output_width_px=transform.output_width_px,
        output_height_px=transform.output_height_px,
    )


def rotate_transform_90(transform: CropTransform, clockwise: bool = True) -> CropTransform:
    delta = 90 if clockwise else -90
    transform.rotation_degrees = (transform.rotation_degrees + delta) % 360
    return transform
