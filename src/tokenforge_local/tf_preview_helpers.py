from __future__ import annotations

from pathlib import Path
import traceback

from .app_state import clear_widget, mark_dirty, set_status, state
from .composition import build_styled_composition
from .image_editor import apply_crop_transform, preview_with_stencil
from .palette import map_image_to_palette
from .tf_layer_plan import layer_colors_for_project
from .utils import image_to_data_url, safe_project_name

try:
    from nicegui import events
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


def refresh_crop_preview() -> None:
    if state.source_image is None or state.crop_image_widget is None:
        return
    image = preview_with_stencil(state.source_image, state.project.crop_transform, state.project.token_defaults)
    state.crop_image_widget.set_source(image_to_data_url(image))


def build_current_composition():
    if state.prepared_image is None:
        return None
    return build_styled_composition(
        state.prepared_image,
        state.project.token_defaults,
        state.project.style_settings,
        state.project.imported_fonts,
    )


def refresh_styled_preview() -> None:
    composition = build_current_composition()
    if composition is not None and state.styled_preview_widget is not None:
        state.styled_preview_widget.set_source(image_to_data_url(composition.image))


def refresh_reduced_color_preview(notify_user: bool = False) -> tuple[bool, str]:
    if state.prepared_image is None:
        message = "Confirm a crop before generating the reduced-color preview."
        if notify_user:
            set_status(message, negative=True)
        return False, message
    if state.reduced_preview_widget is None:
        return False, "Reduced-color preview UI is not ready yet."

    colors = layer_colors_for_project(state.project)
    if not colors:
        message = "Enable at least one filament color to render the reduced-color preview."
        clear_widget(state.reduced_preview_widget)
        set_status(message, negative=True, notify=notify_user)
        return False, message

    try:
        composition = build_current_composition()
        if composition is None:
            raise RuntimeError("styled composition was not available")
        preview, _ = map_image_to_palette(composition.image, colors)
        preview_dir = Path("outputs/previews")
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{safe_project_name(state.project.project_name) or 'tokenforge-token'}-reduced-preview.png"
        preview.save(preview_path)
        state.reduced_preview_path = preview_path
        state.reduced_preview_widget.set_source(image_to_data_url(preview))
        message = f"Reduced-color preview updated: {preview_path}"
        if notify_user:
            set_status(message)
        return True, message
    except Exception as exc:  # pragma: no cover - UI path
        traceback.print_exc()
        clear_widget(state.reduced_preview_widget)
        message = f"Reduced-color preview failed: {exc}. You can still try Generate STL + print package."
        set_status(message, negative=True, notify=notify_user)
        return False, message


def refresh_visual_previews() -> None:
    refresh_styled_preview()
    refresh_reduced_color_preview(False)


def refresh_after_crop_transform_change() -> None:
    refresh_crop_preview()
    if state.source_image is not None and state.prepared_image is not None:
        state.prepared_image = apply_crop_transform(state.source_image, state.project.crop_transform)
        mark_dirty()
        refresh_visual_previews()


def handle_crop_mouse(e: events.MouseEventArguments) -> None:
    if e.type == "mousedown":
        state.dragging = True
        state.last_mouse_x = e.image_x
        state.last_mouse_y = e.image_y
    elif e.type == "mouseup":
        state.dragging = False
    elif e.type == "mousemove" and state.dragging:
        state.project.crop_transform.pan_x_px += e.image_x - state.last_mouse_x
        state.project.crop_transform.pan_y_px += e.image_y - state.last_mouse_y
        state.last_mouse_x = e.image_x
        state.last_mouse_y = e.image_y
        refresh_after_crop_transform_change()
