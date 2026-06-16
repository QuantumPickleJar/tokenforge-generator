from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from PIL import Image, ImageFilter

from .geometry import calculate_layer_plan, z_height_for_layer
from .models import FilamentColor, LayerColorStop, ProjectState
from .palette import enabled_colors, sort_colors_for_layering
from .utils import hex_to_rgb


@dataclass(slots=True)
class LayerFitResult:
    stops: list[LayerColorStop]
    ordered_colors: list[FilamentColor]
    spans: list[int]
    total_layers: int
    estimated_rmse: float


def _resize_for_fit(image: Image.Image, target_width_px: int = 160) -> Image.Image:
    if image.width <= target_width_px:
        return image.convert("RGB")
    height = max(1, int(round(image.height * (target_width_px / image.width))))
    return image.convert("RGB").resize((target_width_px, height), Image.Resampling.LANCZOS)


def _normalized_luminance(image: Image.Image) -> np.ndarray:
    source = image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=0.35))
    pixels = np.asarray(source, dtype=np.float32)
    luminance = (0.2126 * pixels[:, :, 0]) + (0.7152 * pixels[:, :, 1]) + (0.0722 * pixels[:, :, 2])
    lo = float(np.percentile(luminance, 1.0))
    hi = float(np.percentile(luminance, 99.0))
    if hi <= lo + 1e-6:
        return np.zeros(luminance.shape, dtype=np.float32)
    return np.clip((luminance - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)


def _total_layers_for_project(project: ProjectState, colors: list[FilamentColor]) -> int:
    # The layer optimizer needs the physical layer budget before it can choose
    # band spans. A one-color dummy plan gives us that budget without requiring
    # the current enabled palette to already fit cleanly.
    dummy = [colors[0] if colors else FilamentColor("Dummy", "#000000", True)]
    return calculate_layer_plan(project.printer_preferences, dummy).total_layers


def _threshold_bin(project: ProjectState, layer_number: int, finished_thickness_mm: float, bins: int) -> int:
    top_z = z_height_for_layer(project.printer_preferences, layer_number)
    threshold = max(0.0, min(1.0, top_z / max(finished_thickness_mm, 0.0001)))
    return max(0, min(bins - 1, int(round(threshold * (bins - 1)))))


def _range_cost(prefix_costs: np.ndarray, color_index: int, low_bin: int, high_bin: int) -> float:
    if high_bin < low_bin:
        return 0.0
    low = max(0, min(prefix_costs.shape[1] - 1, low_bin))
    high = max(0, min(prefix_costs.shape[1] - 2, high_bin))
    if high < low:
        return 0.0
    return float(prefix_costs[color_index, high + 1] - prefix_costs[color_index, low])


def optimize_layer_stops_for_image(image: Image.Image, project: ProjectState, *, bins: int = 256) -> LayerFitResult:
    """Fit enabled filament color order and integer layer spans to the image.

    Parameters:
        image: The styled RGB preview image to approximate.
        project: The current project state, including enabled filament colors and
            printer layer heights.
        bins: Number of tone bins used by the dynamic-programming fitter.

    The resulting stops use the same cumulative-layer model as the live print
    preview: each color band owns an integer number of slicer layers, and the
    top Z threshold of that band determines which pixels would show that color.
    """
    colors = sort_colors_for_layering(enabled_colors(project.enabled_palette_colors))
    if len(colors) < 2:
        raise ValueError("Enable at least two filament colors before auto-fitting layers.")

    total_layers = _total_layers_for_project(project, colors)
    if len(colors) > total_layers:
        raise ValueError(
            f"There are {len(colors)} enabled colors but only {total_layers} physical layers. "
            "Increase finished thickness or disable some colors before auto-fitting."
        )

    layer_budget_plan = calculate_layer_plan(project.printer_preferences, [colors[0]])
    finished = layer_budget_plan.finished_thickness_mm

    working = _resize_for_fit(image)
    tone = _normalized_luminance(working)
    source_pixels = np.asarray(working, dtype=np.float32).reshape(-1, 3)
    tone_bins = np.clip((tone.reshape(-1) * (bins - 1)).astype(np.int32), 0, bins - 1)

    palette = np.asarray([hex_to_rgb(color.hex) for color in colors], dtype=np.float32)
    distances = ((source_pixels[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)

    bin_costs = np.zeros((len(colors), bins), dtype=np.float64)
    for color_index in range(len(colors)):
        np.add.at(bin_costs[color_index], tone_bins, distances[:, color_index])
    prefix_costs = np.concatenate([np.zeros((len(colors), 1), dtype=np.float64), np.cumsum(bin_costs, axis=1)], axis=1)

    thresholds_by_layer = [-1] + [_threshold_bin(project, layer, finished, bins) for layer in range(1, total_layers + 1)]
    color_count = len(colors)
    inf = float("inf")
    dp = np.full((color_count + 1, total_layers + 1), inf, dtype=np.float64)
    parent = np.full((color_count + 1, total_layers + 1), -1, dtype=np.int32)
    dp[0, 0] = 0.0

    for color_number in range(1, color_count + 1):
        color_index = color_number - 1
        min_end = color_number
        max_end = total_layers - (color_count - color_number)
        for end_layer in range(min_end, max_end + 1):
            best_cost = inf
            best_prev = -1
            for previous_end in range(color_number - 1, end_layer):
                if not math.isfinite(float(dp[color_number - 1, previous_end])):
                    continue
                low_bin = thresholds_by_layer[previous_end] + 1
                high_bin = thresholds_by_layer[end_layer]
                cost = float(dp[color_number - 1, previous_end]) + _range_cost(prefix_costs, color_index, low_bin, high_bin)
                if cost < best_cost:
                    best_cost = cost
                    best_prev = previous_end
            dp[color_number, end_layer] = best_cost
            parent[color_number, end_layer] = best_prev

    if not math.isfinite(float(dp[color_count, total_layers])):
        raise ValueError("Could not fit the enabled palette to the current layer count.")

    spans_reversed: list[int] = []
    end = total_layers
    for color_number in range(color_count, 0, -1):
        previous_end = int(parent[color_number, end])
        if previous_end < 0:
            raise ValueError("Layer fitting failed while reconstructing spans.")
        spans_reversed.append(end - previous_end)
        end = previous_end
    spans = list(reversed(spans_reversed))

    stops: list[LayerColorStop] = []
    start_layer = 1
    for color, span in zip(colors, spans, strict=True):
        stops.append(LayerColorStop(start_layer=start_layer, color_name=color.name, color_hex=color.hex))
        start_layer += max(1, int(span))

    pixel_count = max(1, source_pixels.shape[0])
    estimated_rmse = math.sqrt(float(dp[color_count, total_layers]) / (pixel_count * 3.0)) / 255.0
    return LayerFitResult(stops=stops, ordered_colors=colors, spans=spans, total_layers=total_layers, estimated_rmse=estimated_rmse)
