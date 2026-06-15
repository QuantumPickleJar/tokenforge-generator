from __future__ import annotations

from dataclasses import dataclass

import math  # for dynamic resolution calculation based on nozzle size
import cv2  # for Gaussian smoothing of height maps
import numpy as np
from PIL import Image

from .composition import CompositionResult, build_styled_composition
from .geometry import calculate_layer_plan, height_map_from_indices, height_map_to_mesh
from .masks import clean_index_map_tiny_islands
from .models import FilamentColor, ProjectState
from .palette import map_image_to_palette
from .tf_layer_plan import layer_colors_for_project
from .utils import hex_to_rgb


@dataclass(slots=True)
class PipelineResult:
    composition: CompositionResult
    posterized_preview: Image.Image
    layer_preview: Image.Image
    cleaned_index_map: np.ndarray
    masks: dict[str, np.ndarray]
    layer_plan: object
    mesh: object
    ordered_colors: list[FilamentColor]


def resize_for_working_resolution(image: Image.Image, max_width_px: int = 180) -> Image.Image:
    if image.width <= max_width_px:
        return image.copy()
    height = max(1, int(round(image.height * (max_width_px / image.width))))
    return image.resize((max_width_px, height), Image.Resampling.LANCZOS)


def run_token_pipeline(
    prepared_image: Image.Image,
    project: ProjectState,
    max_mesh_width_px: int = 150,
    snap_thickness: str = "nearest",
) -> PipelineResult:
    colors = layer_colors_for_project(project)
    if len(colors) < 2:
        raise ValueError("At least two enabled filament colors are required.")

    composition = build_styled_composition(
        prepared_image,
        project.token_defaults,
        project.style_settings,
        imported_fonts=project.imported_fonts,
    )
    # Dynamically adjust the working resolution based on the printer's nozzle size.  A
    # finer mesh leads to smoother 2.5D reliefs on printers with smaller nozzles.
    # We target a cell size of roughly one quarter of the nozzle width (e.g. ~0.1 mm
    # for a 0.4 mm nozzle).  The desired pixel width is computed by dividing the
    # token width in mm by the target mm-per-cell, then rounded up.  We take the
    # maximum of this dynamic width and the provided max_mesh_width_px to avoid
    # downsampling large images.  See the README for context on this heuristic.
    target_mm_per_cell = project.printer_preferences.nozzle_size_mm / 4.0
    if target_mm_per_cell <= 0:
        desired_width_px = max_mesh_width_px
    else:
        desired_width_px = int(math.ceil(project.token_defaults.width_mm / target_mm_per_cell))
    working = resize_for_working_resolution(
        composition.image,
        max(desired_width_px, max_mesh_width_px),
    )
    style_mask_small = composition.style_height_mask.resize(working.size, Image.Resampling.BILINEAR)
    token_mask_small = composition.rounded_token_mask.resize(working.size, Image.Resampling.NEAREST)

    posterized, index_map = map_image_to_palette(working, colors)
    mm_per_pixel = project.token_defaults.width_mm / working.width
    cleaned_index, masks = clean_index_map_tiny_islands(
        index_map,
        colors,
        project.printer_preferences.minimum_feature_size_mm,
        mm_per_pixel,
    )

    palette_rgb = [hex_to_rgb(color.hex) for color in colors]
    layer_pixels = np.asarray(palette_rgb, dtype=np.uint8)[cleaned_index]
    layer_preview = Image.fromarray(layer_pixels, mode="RGB")

    plan = calculate_layer_plan(project.printer_preferences, colors, snap=snap_thickness, custom_stops=project.layer_color_stops)
    heights = height_map_from_indices(cleaned_index, colors, plan)

    # Style mask gently pushes frame/text features toward higher Z, so style choices are not preview-only.
    style_values = np.asarray(style_mask_small, dtype=np.float32) / 255.0
    heights = np.maximum(heights, style_values * plan.finished_thickness_mm)

    # Smooth the height map to reduce blockiness in the generated mesh.
    try:
        heights = cv2.GaussianBlur(heights.astype(np.float32), (5, 5), sigmaX=1)
    except Exception:
        pass

    token_mask_array = np.asarray(token_mask_small, dtype=np.uint8)
    heights[token_mask_array == 0] = 0.0

    mesh = height_map_to_mesh(
        heights,
        project.token_defaults,
        token_mask=token_mask_array > 0,
        simplify_stride=1,
    )
    project.generated_layer_plan = plan
    return PipelineResult(composition, posterized, layer_preview, cleaned_index, masks, plan, mesh, colors)
