from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from .models import FilamentColor


def generate_color_masks(index_map: np.ndarray, colors: list[FilamentColor]) -> dict[str, np.ndarray]:
    return {color.name: (index_map == idx).astype(np.uint8) * 255 for idx, color in enumerate(colors)}


def remove_tiny_islands(mask: np.ndarray, min_area_px: int) -> np.ndarray:
    """Remove connected white components smaller than min_area_px.

    Parameters:
        mask: uint8 2D mask where printable regions are non-zero.
        min_area_px: Components below this pixel area are erased.
    """
    if min_area_px <= 1:
        return mask.astype(np.uint8)
    binary = (mask > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = np.zeros_like(binary, dtype=np.uint8)
    for label in range(1, count):
        area = stats[label, cv2.CC_STAT_AREA]
        if area >= min_area_px:
            cleaned[labels == label] = 255
    return cleaned.astype(np.uint8)


def clean_index_map_tiny_islands(
    index_map: np.ndarray,
    colors: list[FilamentColor],
    minimum_feature_size_mm: float,
    mm_per_pixel: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    if mm_per_pixel <= 0:
        raise ValueError("mm_per_pixel must be positive.")
    min_area_px = max(1, int(round((minimum_feature_size_mm / mm_per_pixel) ** 2)))
    masks = generate_color_masks(index_map, colors)
    cleaned_masks = {name: remove_tiny_islands(mask, min_area_px) for name, mask in masks.items()}
    cleaned = index_map.copy()

    # Pixels removed from a tiny island are reassigned to the nearest surviving neighbor.
    # This keeps the index map complete while still erasing unprintable specks from masks.
    surviving = np.zeros_like(index_map, dtype=bool)
    for idx, color in enumerate(colors):
        current = cleaned_masks[color.name] > 0
        surviving |= current
        cleaned[current] = idx
    removed = ~surviving
    if np.any(removed):
        # Simple deterministic fallback: assign removed pixels to the most common surviving color.
        values = cleaned[surviving]
        fallback = int(np.bincount(values).argmax()) if values.size else 0
        cleaned[removed] = fallback
    final_masks = generate_color_masks(cleaned, colors)
    return cleaned, final_masks


def masks_to_pil(masks: dict[str, np.ndarray]) -> dict[str, Image.Image]:
    return {name: Image.fromarray(mask.astype(np.uint8), mode="L") for name, mask in masks.items()}
