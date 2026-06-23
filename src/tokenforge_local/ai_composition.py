"""Deterministic post-AI composition helpers.

CARD can provide rendered text/QR overlays later; the model output is always the
base image and never the source of truth for those critical elements.
"""

from __future__ import annotations

from PIL import Image


def apply_protected_overlay(base_image: Image.Image, overlay: Image.Image | None) -> Image.Image:
    """Return an RGB image with an optional transparent RGBA overlay reapplied."""
    base = base_image.convert("RGBA")
    if overlay is None:
        return base.convert("RGB")
    layer = overlay.convert("RGBA")
    if layer.size != base.size:
        layer = layer.resize(base.size, Image.Resampling.LANCZOS)
    base.alpha_composite(layer)
    return base.convert("RGB")
