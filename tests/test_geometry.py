import numpy as np

from tokenforge_local.geometry import calculate_layer_plan, export_stl, height_map_to_mesh
from tokenforge_local.models import FilamentColor, PrinterPreferences, TokenDefaults


def test_layer_thickness_calculation_snap_up():
    prefs = PrinterPreferences(initial_layer_height_mm=0.2, standard_layer_height_mm=0.2, finished_model_thickness_mm=1.11)
    colors = [FilamentColor("Black", "#000000"), FilamentColor("White", "#ffffff")]
    plan = calculate_layer_plan(prefs, colors, snap="up")
    assert plan.finished_thickness_mm == 1.2
    assert plan.snap_warning is not None
    assert plan.total_layers == 6


def test_swap_plan_generation():
    prefs = PrinterPreferences(finished_model_thickness_mm=1.0)
    colors = [FilamentColor("Black", "#000000"), FilamentColor("Gold", "#c7a34a"), FilamentColor("White", "#ffffff")]
    plan = calculate_layer_plan(prefs, colors)
    assert [band.color_name for band in plan.color_layers] == ["Black", "Gold", "White"]
    assert plan.color_layers[0].action.startswith("Start print")
    assert "Swap" in plan.color_layers[1].action


def test_stl_export_smoke(tmp_path):
    heights = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
    mesh = height_map_to_mesh(heights, TokenDefaults(width_mm=10, height_mm=10, corner_radius_mm=1), simplify_stride=1)
    path = export_stl(mesh, tmp_path / "smoke.stl")
    assert path.exists()
    assert path.stat().st_size > 100
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0
