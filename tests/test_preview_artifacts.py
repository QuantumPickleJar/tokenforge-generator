from __future__ import annotations

import numpy as np
from PIL import Image

from tokenforge_local.models import FilamentColor, LayerColorStop, ProjectState, StyleSettings, TextLayoutConfig
from tokenforge_local.preview_artifacts import build_preview_artifacts
from tokenforge_local.preview_smoke import run_preview_smoke


def _gradient(width: int = 60, height: int = 24) -> Image.Image:
    image = Image.new("RGB", (width, height))
    for x in range(width):
        shade = int(255 * (x / max(1, width - 1)))
        for y in range(height):
            image.putpixel((x, y), (shade, shade, shade))
    return image


def _unstyled_project(stops: list[LayerColorStop] | None = None) -> ProjectState:
    style = StyleSettings(
        border_enabled=False,
        title_text=TextLayoutConfig(enabled=False),
        bottom_text=TextLayoutConfig(enabled=False),
    )
    return ProjectState(
        project_name="preview-test",
        enabled_palette_colors=[
            FilamentColor("Black", "#000000", True),
            FilamentColor("Gray", "#808080", True),
            FilamentColor("White", "#ffffff", True),
        ],
        style_settings=style,
        layer_color_stops=stops or [
            LayerColorStop(1, "Black", "#000000"),
            LayerColorStop(3, "Gray", "#808080"),
            LayerColorStop(5, "White", "#ffffff"),
        ],
    )


def test_preview_artifacts_build_styled_and_layer_span_previews() -> None:
    artifacts = build_preview_artifacts(_gradient(), _unstyled_project(), output_size=(60, 24), soften_boundaries=False)

    assert artifacts.composition.image.size == (60, 24)
    assert artifacts.layer_span_preview.size == (60, 24)
    assert artifacts.layer_index_map.shape == (24, 60)
    assert artifacts.layer_plan.total_layers >= len(artifacts.ordered_colors)
    assert len(set(artifacts.layer_index_map.flatten().tolist())) >= 2


def test_layer_span_preview_changes_when_first_color_consumes_more_layers() -> None:
    narrow_black = _unstyled_project(
        [
            LayerColorStop(1, "Black", "#000000"),
            LayerColorStop(2, "Gray", "#808080"),
            LayerColorStop(5, "White", "#ffffff"),
        ]
    )
    wide_black = _unstyled_project(
        [
            LayerColorStop(1, "Black", "#000000"),
            LayerColorStop(4, "Gray", "#808080"),
            LayerColorStop(5, "White", "#ffffff"),
        ]
    )

    narrow = build_preview_artifacts(_gradient(), narrow_black, output_size=(60, 24), soften_boundaries=False)
    wide = build_preview_artifacts(_gradient(), wide_black, output_size=(60, 24), soften_boundaries=False)

    narrow_black_pixels = int(np.count_nonzero(narrow.layer_index_map == 0))
    wide_black_pixels = int(np.count_nonzero(wide.layer_index_map == 0))

    assert wide_black_pixels > narrow_black_pixels


def test_preview_smoke_runner_writes_inspectable_pngs(tmp_path) -> None:
    paths = run_preview_smoke(tmp_path)

    assert paths["styled_preview"].exists()
    assert paths["layer_span_preview"].exists()
    assert Image.open(paths["styled_preview"]).size == (180, 252)
    assert Image.open(paths["layer_span_preview"]).size == (180, 252)
