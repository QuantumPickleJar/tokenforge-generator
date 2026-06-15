from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from PIL import Image
import trimesh

from .geometry import export_stl
from .models import LayerPlan, ProjectState, dataclass_to_dict
from .utils import safe_project_name, write_json


def write_swap_plan_csv(path: Path, layer_plan: LayerPlan) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "layer_number",
        "end_layer",
        "span_layers",
        "z_height_mm",
        "top_z_height_mm",
        "gcode_insert_before_layer",
        "gcode_insert_at_z_mm",
        "color_name",
        "color_hex",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for band in layer_plan.color_layers:
            writer.writerow(dataclass_to_dict(band))
    return path


def style_summary(project: ProjectState) -> str:
    settings = project.style_settings
    lines = [
        f"Border enabled: {settings.border_enabled}",
        f"Border style: {settings.border_style}",
        f"Border thickness px: {settings.border_thickness_px}",
        f"Title text enabled: {settings.title_text.enabled}",
        f"Title text: {settings.title_text.content!r}",
        f"Bottom text enabled: {settings.bottom_text.enabled}",
        f"Bottom text: {settings.bottom_text.content!r}",
        f"Title/banner enabled: {settings.title_text.banner_enabled}",
        f"Bottom/banner enabled: {settings.bottom_text.banner_enabled}",
        f"Simple badge enabled: {settings.simple_badge_enabled}",
    ]
    return "\n".join(lines)


def write_print_notes(path: Path, project: ProjectState, layer_plan: LayerPlan) -> Path:
    prefs = project.printer_preferences
    token = project.token_defaults
    lines: list[str] = []
    lines.append(f"Tokenforge Local print notes for {project.project_name}")
    lines.append("=" * 72)
    lines.append("")
    if layer_plan.snap_warning:
        lines.append(f"Thickness warning: {layer_plan.snap_warning}")
        lines.append("")
    lines.append("Printer/profile")
    lines.append(f"- Nozzle size: {prefs.nozzle_size_mm:.3f} mm")
    lines.append(f"- Initial layer height: {prefs.initial_layer_height_mm:.3f} mm")
    lines.append(f"- Standard layer height: {prefs.standard_layer_height_mm:.3f} mm")
    lines.append(f"- Finished model thickness: {layer_plan.finished_thickness_mm:.3f} mm")
    lines.append(f"- Expected layer count: {layer_plan.total_layers}")
    lines.append("")
    lines.append("Token dimensions")
    lines.append(f"- Width: {token.width_mm:.3f} mm")
    lines.append(f"- Height: {token.height_mm:.3f} mm")
    lines.append(f"- Corner radius: {token.corner_radius_mm:.3f} mm")
    lines.append("")
    lines.append("Enabled style options")
    lines.append(style_summary(project))
    lines.append("")
    lines.append("Filament order and manual swaps")
    for band in layer_plan.color_layers:
        end_layer = band.end_layer if band.end_layer is not None else band.layer_number
        lines.append(
            f"- Layers {band.layer_number}-{end_layer} ({band.span_layers} layers), "
            f"Z start={band.z_height_mm:.3f} mm, Z top={(band.top_z_height_mm if band.top_z_height_mm is not None else band.z_height_mm):.3f} mm: {band.color_name} ({band.color_hex})"
        )
        if band.gcode_insert_before_layer is None:
            lines.append("  G-code: no edit before layer 1; start the print with this filament loaded.")
        else:
            lines.append(
                f"  G-code: add M600 / Pause at Height / slicer color change before layer "
                f"{band.gcode_insert_before_layer} at or before Z={band.gcode_insert_at_z_mm:.3f} mm."
            )
    lines.append("")
    lines.append("Slicer checklist")
    lines.append("- Import STL.")
    lines.append("- Confirm X/Y/Z dimensions.")
    lines.append("- Confirm initial and standard layer heights match this note.")
    lines.append("- Do not scale Z in the slicer.")
    lines.append("- Add color changes or pauses at the listed layer/Z checkpoints.")
    lines.append("- Preview before printing.")
    lines.append("- Export G-code from the slicer, not from Tokenforge Local.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_print_package(
    project: ProjectState,
    mesh: trimesh.Trimesh,
    preview: Image.Image,
    layer_preview: Image.Image,
    output_dir: Path | str,
) -> dict[str, Path]:
    if project.generated_layer_plan is None:
        raise ValueError("Project has no generated layer plan. Run the pipeline first.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = safe_project_name(project.project_name)

    stl_path = output_dir / f"{name}.stl"
    preview_path = output_dir / f"{name}-preview.png"
    layer_preview_path = output_dir / f"{name}-layer-preview.png"
    csv_path = output_dir / f"{name}-swap-plan.csv"
    notes_path = output_dir / f"{name}-print-notes.txt"
    json_path = output_dir / f"{name}.tokenforge.json"
    zip_path = output_dir / f"{name}-print-package.zip"

    export_stl(mesh, stl_path)
    preview.save(preview_path)
    layer_preview.save(layer_preview_path)
    write_swap_plan_csv(csv_path, project.generated_layer_plan)
    write_print_notes(notes_path, project, project.generated_layer_plan)
    write_json(json_path, project)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in [stl_path, preview_path, layer_preview_path, csv_path, notes_path, json_path]:
            archive.write(path, arcname=path.name)

    return {
        "stl": stl_path,
        "preview": preview_path,
        "layer_preview": layer_preview_path,
        "swap_plan": csv_path,
        "print_notes": notes_path,
        "project_json": json_path,
        "zip": zip_path,
    }
