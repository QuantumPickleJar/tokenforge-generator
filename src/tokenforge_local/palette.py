from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .models import FilamentColor
from .utils import hex_to_rgb


@dataclass(slots=True)
class PaletteWarning:
    severity: str
    message: str


def enabled_colors(colors: list[FilamentColor]) -> list[FilamentColor]:
    return [color for color in colors if color.enabled]


def validate_enabled_palette(colors: list[FilamentColor]) -> list[PaletteWarning]:
    count = len(enabled_colors(colors))
    warnings: list[PaletteWarning] = []
    if count < 2:
        warnings.append(PaletteWarning("error", "Enable at least two filament colors before generating a token."))
    if count > 6:
        warnings.append(PaletteWarning("warning", "More than six enabled colors is usually painful for manual filament swaps."))
    return warnings


def palette_rgb_array(colors: list[FilamentColor]) -> np.ndarray:
    if not colors:
        raise ValueError("At least one filament color is required.")
    return np.asarray([hex_to_rgb(color.hex) for color in colors], dtype=np.float32)


def map_image_to_palette(image: Image.Image, colors: list[FilamentColor]) -> tuple[Image.Image, np.ndarray]:
    """Map every RGB pixel to the nearest enabled filament color.

    Parameters:
        image: PIL RGB-compatible image to reduce.
        colors: Enabled filament colors, in the same order used for layer planning.
    """
    if len(colors) < 1:
        raise ValueError("Cannot posterize without at least one enabled color.")
    rgb = image.convert("RGB")
    pixels = np.asarray(rgb, dtype=np.float32)
    palette = palette_rgb_array(colors)
    # Squared Euclidean RGB distance is deterministic and intentionally boring.
    # A later v0.2/v0.3 pass can add perceptual LAB distance without changing callers.
    distances = ((pixels[:, :, None, :] - palette[None, None, :, :]) ** 2).sum(axis=3)
    indices = np.argmin(distances, axis=2).astype(np.uint8)
    mapped = palette[indices].astype(np.uint8)
    return Image.fromarray(mapped, mode="RGB"), indices


def sort_colors_for_layering(colors: list[FilamentColor]) -> list[FilamentColor]:
    """Order colors from dark to light so high bands tend to carry visual detail."""
    def luminance(color: FilamentColor) -> float:
        r, g, b = hex_to_rgb(color.hex)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    return sorted(colors, key=luminance)
