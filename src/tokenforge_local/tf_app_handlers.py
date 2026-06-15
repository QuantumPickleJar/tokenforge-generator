from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import asyncio
import inspect
import traceback
from typing import Any, Callable

from PIL import Image

from .app_state import clear_widget, mark_dirty, set_status, state
from .export_package import export_print_package
from .image_editor import apply_crop_transform, default_crop_transform
from .image_pipeline import run_token_pipeline
from .models import FilamentColor, LayerPlan, ProjectState
from .palette import validate_enabled_palette
from .preferences import save_preferences
from .tf_layer_ui import refresh_layer_controls
from .tf_preview_helpers import refresh_crop_preview, refresh_reduced_color_preview, refresh_styled_preview, refresh_visual_previews
from .utils import image_to_data_url, safe_project_name

try:
    from nicegui import events, ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


async def handle_upload(e: events.UploadEventArguments) -> None:
    upload_file = getattr(e, "file", None)
    raw_name = (
        getattr(e, "name", None)
        or getattr(e, "filename", None)
        or getattr(upload_file, "filename", None)
        or getattr(upload_file, "name", None)
        or "uploaded-image.png"
    )
    filename = Path(str(raw_name)).name or "uploaded-image.png"
    project_name = safe_project_name(Path(filename).stem) or "uploaded-image"
    suffix = Path(filename).suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
        suffix = ".png"

    upload_dir = Path("outputs/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{project_name}{suffix}"
    counter = 1
    while target.exists():
        target = upload_dir / f"{project_name}-{counter}{suffix}"
        counter += 1

    if upload_file is not None and hasattr(upload_file, "save"):
        saved = upload_file.save(target)
        if inspect.isawaitable(saved):
            await saved
    elif hasattr(e, "content"):
        content = e.content
        data = content.read() if hasattr(content, "read") else content
        if inspect.isawaitable(data):
            data = await data
        if isinstance(data, str):
            data = data.encode()
        with target.open("wb") as handle:
            handle.write(data)
    else:
        set_status("Upload failed: unsupported NiceGUI upload payload.", negative=True)
        return

    try:
        state.source_path = target
        state.source_image = Image.open(target).convert("RGB")
    except Exception as exc:
        set_status(f"Upload failed: could not read image ({exc}).", negative=True)
        return

    state.project.project_name = project_name
    state.project.source_image = str(target)
    state.project.crop_transform = default_crop_transform(str(target), state.project.token_defaults)
    state.project.layer_color_stops = []
    state.prepared_image = None
    state.reduced_preview_path = None
    state.is_generating = False
    mark_dirty()
    for widget in (state.styled_preview_widget, state.reduced_preview_widget, state.layer_preview_widget):
        clear_widget(widget)
    refresh_layer_controls()
    refresh_crop_preview()
    set_status("Image uploaded. Adjust pan/zoom/rotation, then confirm the crop.")


def confirm_crop() -> None:
    if state.source_image is None:
        set_status("Upload an image first.", negative=True)
        return
    state.prepared_image = apply_crop_transform(state.source_image, state.project.crop_transform)
    mark_dirty()
    refresh_layer_controls()
    refresh_styled_preview()
    ok, message = refresh_reduced_color_preview(False)
    set_status("Prepared image confirmed. Reduced-color preview updated; configure style/palette/layer plan or generate the package." if ok else f"Prepared image confirmed. {message}")


def persist_preferences_from_ui() -> None:
    state.preferences.printer = state.project.printer_preferences
    state.preferences.token_defaults = state.project.token_defaults
    state.preferences.style_defaults = state.project.style_settings
    state.preferences.palette = state.project.enabled_palette_colors
    state.preferences.imported_fonts = state.project.imported_fonts
    save_preferences(state.preferences)


def _build_print_package(prepared_image: Image.Image, project_snapshot: ProjectState) -> tuple[dict[str, Path], Image.Image, Image.Image, LayerPlan]:
    result = run_token_pipeline(prepared_image, project_snapshot)
    output_dir = Path("outputs") / safe_project_name(project_snapshot.project_name)
    paths = export_print_package(project_snapshot, result.mesh, result.composition.image, result.layer_preview, output_dir)
    return paths, result.composition.image, result.layer_preview, result.layer_plan


async def generate_package() -> None:
    if state.is_generating:
        set_status("Generation is already running. Wait for the current package build to finish.", negative=True)
        return
    if state.prepared_image is None:
        set_status("Confirm the prepared image before generating.", negative=True)
        return

    warnings = validate_enabled_palette(state.project.enabled_palette_colors)
    errors = [warning.message for warning in warnings if warning.severity == "error"]
    if errors:
        set_status(errors[0], negative=True)
        return
    for warning in warnings:
        if warning.severity == "warning":
            ui.notify(warning.message, type="warning")

    state.is_generating = True
    set_status("Generating STL + print package. The UI should stay connected while the worker runs.", notify=True)
    try:
        persist_preferences_from_ui()
        prepared_image = state.prepared_image.copy()
        project_snapshot = deepcopy(state.project)
        paths, styled_preview, layer_preview, layer_plan = await asyncio.to_thread(
            _build_print_package,
            prepared_image,
            project_snapshot,
        )

        state.package_paths = paths
        state.project.generated_layer_plan = layer_plan
        if state.styled_preview_widget:
            state.styled_preview_widget.set_source(image_to_data_url(styled_preview))
        if state.layer_preview_widget:
            state.layer_preview_widget.set_source(image_to_data_url(layer_preview.resize((315, 440))))
        refresh_layer_controls()
        set_status(f"Print package created: {paths['zip']}")
    except MemoryError:
        traceback.print_exc()
        set_status(
            "Generation ran out of memory before the package could be completed. Try fewer enabled colors or a simpler image.",
            negative=True,
        )
    except Exception as exc:  # pragma: no cover - UI path
        traceback.print_exc()
        set_status(f"Generation failed without dropping the session: {exc}", negative=True)
    finally:
        state.is_generating = False


def palette_changed(color: FilamentColor, *, enabled: Any | None = None, hex_value: Any | None = None) -> None:
    if enabled is not None:
        color.enabled = bool(enabled)
    if hex_value is not None:
        incoming = str(hex_value or "").strip()
        if incoming:
            color.hex = incoming
    mark_dirty()
    refresh_layer_controls()
    refresh_reduced_color_preview(False)


def style_changed(setter: Callable[[], None]) -> None:
    setter()
    mark_dirty()
    refresh_visual_previews()
