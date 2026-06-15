from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .composition import CompositionResult, build_styled_composition
from .geometry import calculate_layer_plan, height_map_from_indices, height_map_to_mesh
from .masks import clean_index_map_tiny_islands
from .models import FilamentColor, PrinterPreferences, ProjectState, TokenDefaults
from .palette import enabled_colors, map_image_to_palette, sort_colors_for_layering
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
    colors = sort_colors_for_layering(enabled_colors(project.enabled_palette_colors))
    if len(colors) < 2:
        raise ValueError("At least two enabled filament colors are required.")

    composition = build_styled_composition(
        prepared_image,
        project.token_defaults,
        project.style_settings,
        imported_fonts=project.imported_fonts,
    )
    working = resize_for_working_resolution(composition.image, max_mesh_width_px)
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

    plan = calculate_layer_plan(project.printer_preferences, colors, snap=snap_thickness)
    heights = height_map_from_indices(cleaned_index, colors, plan)

    # Style mask gently pushes frame/text features toward higher Z, so style choices are not preview-only.
    style_values = np.asarray(style_mask_small, dtype=np.float32) / 255.0
    heights = np.maximum(heights, style_values * plan.finished_thickness_mm)
    heights[token_mask_small.resize(working.size, Image.Resampling.NEAREST) == 0] = 0.0

    mesh = height_map_to_mesh(
        heights,
        project.token_defaults,
        token_mask=np.asarray(token_mask_small, dtype=np.uint8) > 0,
        simplify_stride=1,
    )
    project.generated_layer_plan = plan
    return PipelineResult(composition, posterized, layer_preview, cleaned_index, masks, plan, mesh, colors)
