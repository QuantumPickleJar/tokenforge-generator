from __future__ import annotations

from pathlib import Path

import trimesh

from .models import FilamentColor, ProjectState
from .three_d_preview import build_layer_color_3d_preview


DEFAULT_OUTPUT_DIR = Path("outputs/test-runs/3d-smoke")


def build_smoke_stl(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stl_path = output_dir / "layer-color-smoke-box.stl"
    mesh = trimesh.creation.box(extents=(24.0, 16.0, 4.0))
    mesh.export(stl_path)
    return stl_path


def smoke_project() -> ProjectState:
    return ProjectState(
        project_name="three-d-smoke",
        enabled_palette_colors=[
            FilamentColor("Black", "#111111", True),
            FilamentColor("PLA Gold", "#c7a34a", True),
            FilamentColor("Ivory White", "#f2ead7", True),
        ],
    )


def run_smoke(output_dir: Path = DEFAULT_OUTPUT_DIR):
    stl_path = build_smoke_stl(output_dir)
    return build_layer_color_3d_preview(stl_path, smoke_project(), output_dir / "previews")


def main() -> int:
    result = run_smoke()
    print("3D preview smoke fixture generated")
    print(f"STL: {result.source_path}")
    print(f"GLB: {result.preview_glb_path}")
    print(result.dimensions_summary)
    print(result.color_source_note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
