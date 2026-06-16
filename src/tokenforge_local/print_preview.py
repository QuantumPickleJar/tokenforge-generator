from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from .models import FilamentColor, LayerPlan
from .utils import hex_to_rgb


def _band_thresholds(layer_plan: LayerPlan) -> np.ndarray:
    """Return normalized cumulative top-Z thresholds for each color band.

    Parameters:
        layer_plan: The editable/manual-swap layer plan whose band spans should
            control the visual print preview.
    """
    if not layer_plan.color_layers:
        raise ValueError("Layer plan has no color bands to preview.")

    finished = max(float(layer_plan.finished_thickness_mm), 0.0001)
    thresholds = []
    for band in layer_plan.color_layers:
        top_z = band.top_z_height_mm if band.top_z_height_mm is not None else band.z_height_mm
        thresholds.append(max(0.0, min(1.0, float(top_z) / finished)))
    thresholds[-1] = 1.0
    return np.asarray(thresholds, dtype=np.float32)


def _normalized_luminance(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    luminance = (0.2126 * rgb[:, :, 0]) + (0.7152 * rgb[:, :, 1]) + (0.0722 * rgb[:, :, 2])
    lo = float(np.percentile(luminance, 1.0))
    hi = float(np.percentile(luminance, 99.0))
    if hi <= lo + 1e-6:
        return np.zeros(luminance.shape, dtype=np.float32)
    return np.clip((luminance - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def simulate_layer_span_print_preview(
    image: Image.Image,
    colors: list[FilamentColor],
    layer_plan: LayerPlan,
    *,
    soften_boundaries: bool = True,
) -> tuple[Image.Image, np.ndarray]:
    """Simulate the visible top color created by cumulative filament layers.

    Parameters:
        image: Styled token image used as the tonal source for the preview.
        colors: Filament colors in the same print order as ``layer_plan``.
        layer_plan: Editable layer plan. Changing a band's layer span changes the
            cumulative Z thresholds used here, so the preview responds like a
            practical single-nozzle color-swap print preview instead of plain
            nearest-color posterization.
        soften_boundaries: Apply a small blur to tonal values before quantizing,
            approximating the slightly blended feel of low-resolution relief art.
    """
    if not colors:
        raise ValueError("At least one filament color is required for print preview.")
    if len(colors) != len(layer_plan.color_layers):
        raise ValueError("Color count and layer-plan band count differ.")

    source = image.convert("RGB")
    if soften_boundaries:
        source = source.filter(ImageFilter.GaussianBlur(radius=0.35))

    tone_height = _normalized_luminance(source)
    thresholds = _band_thresholds(layer_plan)

    # searchsorted converts each tonal height into the first cumulative band that
    # can physically cover it. Wider early spans therefore consume more of the
    # tone range and become visibly larger in the print preview.
    indices = np.searchsorted(thresholds, tone_height, side="left").astype(np.uint8)
    indices = np.clip(indices, 0, len(colors) - 1)

    palette = np.asarray([hex_to_rgb(color.hex) for color in colors], dtype=np.uint8)
    preview = palette[indices]
    return Image.fromarray(preview, mode="RGB"), indices
