from pathlib import Path
import zipfile

import numpy as np
from PIL import Image

from tokenforge_local.export_package import export_print_package
from tokenforge_local.geometry import calculate_layer_plan, height_map_to_mesh
from tokenforge_local.models import FilamentColor, ProjectState


def test_zip_package_creation(tmp_path):
    colors = [FilamentColor("Black", "#000000"), FilamentColor("White", "#ffffff")]
    project = ProjectState(project_name="zip-test", enabled_palette_colors=colors)
    project.generated_layer_plan = calculate_layer_plan(project.printer_preferences, colors)
    mesh = height_map_to_mesh(np.ones((2, 2), dtype=np.float32) * 0.4, project.token_defaults)
    preview = Image.new("RGB", (20, 30), "white")
    paths = export_print_package(project, mesh, preview, preview, tmp_path)

    assert paths["zip"].exists()
    with zipfile.ZipFile(paths["zip"], "r") as archive:
        names = set(archive.namelist())
    assert "zip-test.stl" in names
    assert "zip-test-preview.png" in names
    assert "zip-test-layer-preview.png" in names
    assert "zip-test-swap-plan.csv" in names
    assert "zip-test-print-notes.txt" in names
    assert "zip-test.tokenforge.json" in names
