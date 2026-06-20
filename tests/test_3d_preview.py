from __future__ import annotations

import pytest
import trimesh

from tokenforge_local.models import FilamentColor, ProjectState
from tokenforge_local.three_d_preview import build_layer_color_3d_preview, layer_for_z, preview_layer_plan_for_3d
from tokenforge_local.three_d_smoke import run_smoke


def _project() -> ProjectState:
    return ProjectState(
        enabled_palette_colors=[
            FilamentColor("Black", "#000000", True),
            FilamentColor("White", "#ffffff", True),
        ]
    )


def test_layer_for_z_maps_model_bounds_to_physical_layers() -> None:
    from tokenforge_local.three_d_preview import ModelBounds

    bounds = ModelBounds(0, 10, 0, 10, -1, 1)
    assert layer_for_z(-1, bounds, 6) == 1
    assert layer_for_z(1, bounds, 6) == 6
    assert 1 <= layer_for_z(0, bounds, 6) <= 6


def test_build_layer_color_3d_preview_exports_colored_glb(tmp_path) -> None:
    stl_path = tmp_path / "box.stl"
    mesh = trimesh.creation.box(extents=(10, 20, 2))
    mesh.export(stl_path)

    result = build_layer_color_3d_preview(stl_path, _project(), tmp_path / "previews")

    assert result.preview_glb_path.exists()
    assert result.preview_glb_path.suffix == ".glb"
    assert result.model_name == "box.stl"
    assert result.face_count > 0
    assert result.vertex_count > 0
    assert result.bounds.height_mm == pytest.approx(2.0)
    assert "size 10.00 × 20.00 × 2.00 mm" in result.dimensions_summary
    assert len(result.layer_plan.color_layers) == 2
    assert "enabled filament colors" in result.color_source_note


def test_3d_preview_falls_back_to_neutral_gray_when_no_colors_enabled() -> None:
    project = ProjectState(enabled_palette_colors=[])

    plan, colors, note = preview_layer_plan_for_3d(project)

    assert plan.total_layers >= 1
    assert len(colors) == 1
    assert colors[0].name == "Neutral Gray"
    assert "neutral gray fallback" in note


def test_3d_smoke_runner_exports_preview_artifacts(tmp_path) -> None:
    result = run_smoke(tmp_path)

    assert result.source_path.exists()
    assert result.preview_glb_path.exists()
    assert result.preview_glb_path.suffix == ".glb"
    assert "size 24.00 × 16.00 × 4.00 mm" in result.dimensions_summary


def test_3mf_reports_clear_not_yet_supported_error(tmp_path) -> None:
    model_path = tmp_path / "future.3mf"
    model_path.write_bytes(b"not actually a 3mf")

    with pytest.raises(ValueError, match="3MF support is planned"):
        build_layer_color_3d_preview(model_path, _project(), tmp_path / "previews")
