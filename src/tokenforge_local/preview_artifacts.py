from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .composition import CompositionResult, build_styled_composition
from .geometry import calculate_layer_plan
from .models import FilamentColor, LayerPlan, ProjectState
from .print_preview import simulate_layer_span_print_preview
from .tf_layer_plan import layer_colors_for_project
from .utils import safe_project_name


@dataclass(slots=True)
class PreviewArtifacts:
    composition: CompositionResult
    layer_plan: LayerPlan
    ordered_colors: list[FilamentColor]
    layer_span_preview: Image.Image
    layer_index_map: np.ndarray


def build_preview_artifacts(
    prepared_image: Image.Image,
    project: ProjectState,
    *,
    output_size: tuple[int, int] = (630, 879),
    soften_boundaries: bool = True,
) -> PreviewArtifacts:
    """Build every non-STL preview artifact from the current project state.

    Parameters:
        prepared_image: The confirmed/cropped image. This must not be the raw upload.
        project: The current project settings, including style, palette, and layer stops.
        output_size: Pixel size for the styled and layer-span previews. Tests can pass
            a smaller size to keep smoke runs fast.
        soften_boundaries: Passed to the cumulative layer-span preview quantizer.
    """

    if prepared_image is None:
        raise ValueError("A confirmed/cropped image is required before preview artifacts can be built.")

    ordered_colors = layer_colors_for_project(project)
    if not ordered_colors:
        raise ValueError("Enable at least one filament color before previewing.")

    composition = build_styled_composition(
        prepared_image,
        project.token_defaults,
        project.style_settings,
        imported_fonts=project.imported_fonts,
        output_size=output_size,
    )
    layer_plan = calculate_layer_plan(
        project.printer_preferences,
        ordered_colors,
        custom_stops=project.layer_color_stops,
    )
    layer_span_preview, layer_index_map = simulate_layer_span_print_preview(
        composition.image,
        ordered_colors,
        layer_plan,
        soften_boundaries=soften_boundaries,
    )

    return PreviewArtifacts(
        composition=composition,
        layer_plan=layer_plan,
        ordered_colors=ordered_colors,
        layer_span_preview=layer_span_preview,
        layer_index_map=layer_index_map,
    )


def save_preview_artifacts(artifacts: PreviewArtifacts, output_dir: Path | str, project_name: str) -> dict[str, Path]:
    """Write preview artifacts to disk for local smoke-test inspection.

    Parameters:
        artifacts: Preview outputs returned by ``build_preview_artifacts``.
        output_dir: Directory where PNG artifacts should be written.
        project_name: User-facing project name used to make stable filenames.
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_name = safe_project_name(project_name) or "tokenforge-token"

    paths = {
        "styled_preview": output_path / f"{safe_name}-styled-preview.png",
        "layer_span_preview": output_path / f"{safe_name}-layer-span-preview.png",
    }
    artifacts.composition.image.save(paths["styled_preview"])
    artifacts.layer_span_preview.save(paths["layer_span_preview"])
    return paths
