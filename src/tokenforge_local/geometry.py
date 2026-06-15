from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh

from .models import FilamentColor, LayerBand, LayerPlan, PrinterPreferences, TokenDefaults
from .utils import hex_to_rgb


def calculate_layer_plan(preferences: PrinterPreferences, colors: list[FilamentColor], snap: str = "nearest") -> LayerPlan:
    """Calculate slicer-compatible layer/Z positions for manual color swaps.

    Parameters:
        preferences: Printer layer heights and requested finished thickness.
        colors: Enabled filament colors in print order.
        snap: "down", "up", or "nearest" when thickness does not align.
    """
    if preferences.initial_layer_height_mm <= 0 or preferences.standard_layer_height_mm <= 0:
        raise ValueError("Layer heights must be positive.")
    if preferences.finished_model_thickness_mm <= preferences.initial_layer_height_mm:
        raise ValueError("Finished thickness must exceed the initial layer height.")
    if not colors:
        raise ValueError("At least one enabled color is required.")

    requested = preferences.finished_model_thickness_mm
    raw_standard_layers = (requested - preferences.initial_layer_height_mm) / preferences.standard_layer_height_mm
    floor_layers = max(0, math.floor(raw_standard_layers + 1e-9))
    ceil_layers = max(0, math.ceil(raw_standard_layers - 1e-9))
    aligned = abs(raw_standard_layers - round(raw_standard_layers)) < 1e-6

    if aligned:
        standard_layers = int(round(raw_standard_layers))
        snapped = requested
        warning = None
        snapped_from = None
    else:
        if snap == "down":
            standard_layers = floor_layers
        elif snap == "up":
            standard_layers = ceil_layers
        else:
            standard_layers = floor_layers if abs(raw_standard_layers - floor_layers) <= abs(ceil_layers - raw_standard_layers) else ceil_layers
        snapped = preferences.initial_layer_height_mm + standard_layers * preferences.standard_layer_height_mm
        warning = f"Requested thickness {requested:.3f} mm does not align to layer heights; snapped to {snapped:.3f} mm."
        snapped_from = requested

    total_layers = 1 + standard_layers
    if len(colors) > total_layers:
        raise ValueError("Not enough physical layers for every enabled color. Increase thickness or reduce colors.")

    # Allocate one or more complete slicer layers to each color band.
    base = total_layers // len(colors)
    remainder = total_layers % len(colors)
    color_layers: list[LayerBand] = []
    current_layer = 1
    for idx, color in enumerate(colors):
        band_layers = base + (1 if idx < remainder else 0)
        z = preferences.initial_layer_height_mm if current_layer == 1 else preferences.initial_layer_height_mm + (current_layer - 1) * preferences.standard_layer_height_mm
        action = "Start print with this filament" if idx == 0 else f"Swap to {color.name} at or before Z={z:.3f} mm"
        color_layers.append(LayerBand(current_layer, round(z, 4), color.name, color.hex, action))
        current_layer += band_layers

    return LayerPlan(
        base_layers=1,
        color_layers=color_layers,
        total_layers=total_layers,
        finished_thickness_mm=round(snapped, 4),
        snapped_from_mm=snapped_from,
        snap_warning=warning,
    )


def height_map_from_indices(index_map: np.ndarray, colors: list[FilamentColor], layer_plan: LayerPlan) -> np.ndarray:
    if index_map.ndim != 2:
        raise ValueError("index_map must be 2D.")
    z_by_color_name = {band.color_name: band.z_height_mm for band in layer_plan.color_layers}
    max_z = layer_plan.finished_thickness_mm
    heights = np.zeros(index_map.shape, dtype=np.float32)
    for idx, color in enumerate(colors):
        # Each color is a Z band. Later/lighter colors sit higher, making the slicer swap plan meaningful.
        band_z = z_by_color_name.get(color.name, max_z)
        heights[index_map == idx] = max(band_z, 0.01)
    return heights


def _add_quad(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], a, b, c, d, flip: bool = False) -> None:
    start = len(vertices)
    vertices.extend([a, b, c, d])
    if flip:
        faces.append((start, start + 2, start + 1))
        faces.append((start, start + 3, start + 2))
    else:
        faces.append((start, start + 1, start + 2))
        faces.append((start, start + 2, start + 3))


def height_map_to_mesh(
    heights: np.ndarray,
    token: TokenDefaults,
    token_mask: np.ndarray | None = None,
    simplify_stride: int = 2,
) -> trimesh.Trimesh:
    """Create a closed blocky 2.5D mesh from a height map.

    Parameters:
        heights: 2D array of millimeter Z heights for each working pixel/cell.
        token: Physical token dimensions in millimeters.
        token_mask: Optional boolean/uint8 mask. False cells are omitted, preserving rounded corners.
        simplify_stride: Downsample cell grid before meshing to keep STL sizes practical.
    """
    if simplify_stride < 1:
        raise ValueError("simplify_stride must be >= 1")
    if simplify_stride > 1:
        heights = heights[::simplify_stride, ::simplify_stride]
        if token_mask is not None:
            token_mask = token_mask[::simplify_stride, ::simplify_stride]
    h, w = heights.shape
    if token_mask is None:
        inside = np.ones((h, w), dtype=bool)
    else:
        inside = token_mask.astype(bool)
        inside = inside[:h, :w]

    dx = token.width_mm / w
    dy = token.height_mm / h
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []

    def coord(xi: int, yi: int, z: float) -> tuple[float, float, float]:
        return (xi * dx - token.width_mm / 2, token.height_mm / 2 - yi * dy, float(z))

    for y in range(h):
        for x in range(w):
            if not inside[y, x]:
                continue
            z = float(max(0.01, heights[y, x]))
            # Top and bottom for every included cell. Duplicate vertices are acceptable here;
            # watertightness is handled by explicit side quads at every boundary/discontinuity.
            _add_quad(vertices, faces, coord(x, y, z), coord(x + 1, y, z), coord(x + 1, y + 1, z), coord(x, y + 1, z))
            _add_quad(vertices, faces, coord(x, y, 0.0), coord(x, y + 1, 0.0), coord(x + 1, y + 1, 0.0), coord(x + 1, y, 0.0), flip=False)

            neighbors = [
                (0, -1, (coord(x, y, 0.0), coord(x + 1, y, 0.0), coord(x + 1, y, z), coord(x, y, z))),
                (1, 0, (coord(x + 1, y, 0.0), coord(x + 1, y + 1, 0.0), coord(x + 1, y + 1, z), coord(x + 1, y, z))),
                (0, 1, (coord(x + 1, y + 1, 0.0), coord(x, y + 1, 0.0), coord(x, y + 1, z), coord(x + 1, y + 1, z))),
                (-1, 0, (coord(x, y + 1, 0.0), coord(x, y, 0.0), coord(x, y, z), coord(x, y + 1, z))),
            ]
            for dxn, dyn, quad in neighbors:
                nx, ny = x + dxn, y + dyn
                outside = nx < 0 or ny < 0 or nx >= w or ny >= h or not inside[ny, nx]
                if outside:
                    _add_quad(vertices, faces, *quad)
                else:
                    nz = float(max(0.01, heights[ny, nx]))
                    if abs(nz - z) > 1e-6:
                        z_low, z_high = sorted((nz, z))
                        if dxn == 0 and dyn == -1:
                            wall = (coord(x, y, z_low), coord(x + 1, y, z_low), coord(x + 1, y, z_high), coord(x, y, z_high))
                        elif dxn == 1:
                            wall = (coord(x + 1, y, z_low), coord(x + 1, y + 1, z_low), coord(x + 1, y + 1, z_high), coord(x + 1, y, z_high))
                        elif dyn == 1:
                            wall = (coord(x + 1, y + 1, z_low), coord(x, y + 1, z_low), coord(x, y + 1, z_high), coord(x + 1, y + 1, z_high))
                        else:
                            wall = (coord(x, y + 1, z_low), coord(x, y, z_low), coord(x, y, z_high), coord(x, y + 1, z_high))
                        _add_quad(vertices, faces, *wall)

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices, dtype=np.float32), faces=np.asarray(faces, dtype=np.int64), process=True)
    if mesh.is_empty:
        raise ValueError("Generated mesh is empty.")
    return mesh


def export_stl(mesh: trimesh.Trimesh, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)
    return path
