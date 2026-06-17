from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
import trimesh

from .geometry import calculate_layer_plan
from .models import FilamentColor, LayerBand, LayerPlan, ProjectState
from .palette import enabled_colors
from .tf_layer_plan import layer_colors_for_project
from .utils import hex_to_rgb, safe_project_name


@dataclass(slots=True)
class ModelBounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def width_mm(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth_mm(self) -> float:
        return self.max_y - self.min_y

    @property
    def height_mm(self) -> float:
        return self.max_z - self.min_z

    def summary(self) -> str:
        return (
            f"Bounds X {self.min_x:.2f}–{self.max_x:.2f} mm, "
            f"Y {self.min_y:.2f}–{self.max_y:.2f} mm, "
            f"Z {self.min_z:.2f}–{self.max_z:.2f} mm · "
            f"size {self.width_mm:.2f} × {self.depth_mm:.2f} × {self.height_mm:.2f} mm"
        )


@dataclass(slots=True)
class ThreeDPreviewResult:
    source_path: Path
    preview_glb_path: Path
    model_name: str
    bounds: ModelBounds
    vertex_count: int
    face_count: int
    layer_plan: LayerPlan
    colors: list[FilamentColor]

    @property
    def dimensions_summary(self) -> str:
        return self.bounds.summary()


def _load_mesh(path: Path) -> trimesh.Trimesh:
    suffix = path.suffix.lower()
    if suffix != ".stl":
        if suffix == ".3mf":
            raise ValueError("3MF support is planned for a later v0.2 pass. Upload an STL for this MVP preview.")
        raise ValueError(f"Unsupported 3D file type '{suffix or '(none)'}'. Upload an STL file.")

    try:
        loaded = trimesh.load(path, force="mesh")
    except Exception as exc:  # pragma: no cover - trimesh parser-specific detail
        raise ValueError(f"Could not parse STL: {exc}") from exc

    if isinstance(loaded, trimesh.Scene):
        meshes = [geometry for geometry in loaded.geometry.values() if isinstance(geometry, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("The STL scene did not contain mesh geometry.")
        mesh = trimesh.util.concatenate(meshes)
    elif isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    else:
        raise ValueError("The uploaded STL did not load as triangle mesh geometry.")

    if mesh.vertices.size == 0 or mesh.faces.size == 0:
        raise ValueError("The STL contains no vertices or faces.")
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("The STL contains non-finite vertex coordinates.")

    mesh = mesh.copy()
    mesh.remove_unreferenced_vertices()
    return mesh


def _model_bounds(mesh: trimesh.Trimesh) -> ModelBounds:
    raw_bounds = np.asarray(mesh.bounds, dtype=float)
    if raw_bounds.shape != (2, 3) or not np.isfinite(raw_bounds).all():
        raise ValueError("Model bounds could not be calculated.")
    return ModelBounds(
        min_x=float(raw_bounds[0, 0]),
        max_x=float(raw_bounds[1, 0]),
        min_y=float(raw_bounds[0, 1]),
        max_y=float(raw_bounds[1, 1]),
        min_z=float(raw_bounds[0, 2]),
        max_z=float(raw_bounds[1, 2]),
    )


def _preview_colors_for_project(project: ProjectState) -> list[FilamentColor]:
    try:
        colors = layer_colors_for_project(project)
    except Exception:
        colors = []
    if colors:
        return colors

    fallback = enabled_colors(project.enabled_palette_colors)
    if fallback:
        return [FilamentColor(color.name, color.hex, True) for color in fallback]
    return [FilamentColor("Neutral Gray", "#888888", True)]


def preview_layer_plan_for_3d(project: ProjectState) -> tuple[LayerPlan, list[FilamentColor]]:
    colors = _preview_colors_for_project(project)
    custom_stops = project.layer_color_stops if len(colors) > 1 else None
    return calculate_layer_plan(project.printer_preferences, colors, custom_stops=custom_stops), colors


def _band_for_layer(plan: LayerPlan, layer_number: int) -> LayerBand:
    for band in plan.color_layers:
        end_layer = band.end_layer if band.end_layer is not None else band.layer_number
        if band.layer_number <= layer_number <= end_layer:
            return band
    return plan.color_layers[-1]


def layer_for_z(z_value: float, bounds: ModelBounds, total_layers: int) -> int:
    if total_layers <= 1 or bounds.height_mm <= 1e-9:
        return 1
    fraction = (z_value - bounds.min_z) / bounds.height_mm
    fraction = min(1.0, max(0.0, float(fraction)))
    return min(total_layers, max(1, int(math.floor(fraction * total_layers)) + 1))


def face_colors_from_z(mesh: trimesh.Trimesh, bounds: ModelBounds, plan: LayerPlan) -> np.ndarray:
    if len(plan.color_layers) < 1:
        raise ValueError("At least one color band is required for 3D preview.")
    centroids = np.asarray(mesh.triangles_center, dtype=float)
    if centroids.shape[0] != len(mesh.faces):
        raise ValueError("Could not calculate one centroid for every STL face.")

    rgba = np.zeros((len(mesh.faces), 4), dtype=np.uint8)
    for face_index, z_value in enumerate(centroids[:, 2]):
        layer = layer_for_z(float(z_value), bounds, plan.total_layers)
        band = _band_for_layer(plan, layer)
        r, g, b = hex_to_rgb(band.color_hex)
        rgba[face_index] = (r, g, b, 255)
    return rgba


def _center_for_preview(mesh: trimesh.Trimesh, bounds: ModelBounds) -> trimesh.Trimesh:
    preview = mesh.copy()
    center_x = (bounds.min_x + bounds.max_x) / 2.0
    center_y = (bounds.min_y + bounds.max_y) / 2.0
    preview.vertices = preview.vertices - np.asarray([center_x, center_y, bounds.min_z], dtype=float)
    return preview


def build_layer_color_3d_preview(
    source_path: Path | str,
    project: ProjectState,
    output_dir: Path | str = Path("outputs/3d-previews"),
) -> ThreeDPreviewResult:
    path = Path(source_path)
    if not path.exists():
        raise ValueError(f"3D model file does not exist: {path}")

    mesh = _load_mesh(path)
    bounds = _model_bounds(mesh)
    plan, colors = preview_layer_plan_for_3d(project)
    face_colors = face_colors_from_z(mesh, bounds, plan)

    preview_mesh = _center_for_preview(mesh, bounds)
    preview_mesh.visual.face_colors = face_colors

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_name = safe_project_name(path.stem) or "stl-preview"
    glb_path = output_path / f"{safe_name}-layer-color-preview.glb"
    preview_mesh.export(glb_path)

    return ThreeDPreviewResult(
        source_path=path,
        preview_glb_path=glb_path,
        model_name=path.name,
        bounds=bounds,
        vertex_count=int(len(mesh.vertices)),
        face_count=int(len(mesh.faces)),
        layer_plan=plan,
        colors=colors,
    )
