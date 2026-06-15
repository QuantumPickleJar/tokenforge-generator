from __future__ import annotations

from pathlib import Path
import tempfile
import traceback

from PIL import Image

from .export_package import export_print_package
from .image_editor import apply_crop_transform, default_crop_transform, preview_with_stencil, reset_transform, rotate_transform_90
from .image_pipeline import run_token_pipeline
from .models import FilamentColor, Preferences, ProjectState, StyleSettings
from .palette import validate_enabled_palette
from .preferences import load_preferences, save_preferences
from .style_presets import fallback_if_unimplemented, grouped_dropdown_options
from .utils import image_to_data_url, safe_project_name

try:
    from nicegui import events, ui
except ModuleNotFoundError as exc:  # pragma: no cover - only hit before dependencies are installed
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


class AppState:
    def __init__(self) -> None:
        self.preferences: Preferences = load_preferences()
        self.project = ProjectState(
            printer_preferences=self.preferences.printer,
            token_defaults=self.preferences.token_defaults,
            style_settings=self.preferences.style_defaults,
            enabled_palette_colors=[FilamentColor(c.name, c.hex, c.enabled) for c in self.preferences.palette],
            imported_fonts=self.preferences.imported_fonts,
        )
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.prepared_image: Image.Image | None = None
        self.package_paths: dict[str, Path] | None = None
        self.crop_image_widget = None
        self.styled_preview_widget = None
        self.layer_preview_widget = None
        self.status = None
        # Drag state for interactive crop preview
        # When the user drags on the crop preview image, we store the mouse
        # coordinates to compute delta offsets. These attributes are reset on
        # initialization and toggled during drag events.
        self.dragging: bool = False
        self.last_mouse_x: float = 0.0
        self.last_mouse_y: float = 0.0


state = AppState()


def set_status(message: str, negative: bool = False) -> None:
    if state.status:
        state.status.set_text(message)
    if negative:
        ui.notify(message, type="negative")
    else:
        ui.notify(message, type="info")


def refresh_crop_preview() -> None:
    if state.source_image is None or state.crop_image_widget is None:
        return
    preview = preview_with_stencil(state.source_image, state.project.crop_transform, state.project.token_defaults)
    state.crop_image_widget.set_source(image_to_data_url(preview))


def refresh_styled_preview() -> None:
    if state.prepared_image is None or state.styled_preview_widget is None:
        return
    from .composition import build_styled_composition

    composition = build_styled_composition(
        state.prepared_image,
        state.project.token_defaults,
        state.project.style_settings,
        state.project.imported_fonts,
    )
    state.styled_preview_widget.set_source(image_to_data_url(composition.image))


def handle_crop_mouse(e: events.MouseEventArguments) -> None:
    """Handle mouse drag events on the crop preview to adjust pan offsets.

    This callback listens for mousedown, mousemove and mouseup events on the
    interactive image. On mousedown we mark the beginning of a drag and
    remember the current mouse coordinates. While dragging (mousemove
    with the primary button pressed) we compute the delta between the new
    coordinates and the last ones, apply the deltas to the crop transform's
    pan values, and refresh the preview. On mouseup we end the drag.
    """
    if e.type == 'mousedown':
        state.dragging = True
        state.last_mouse_x = e.image_x
        state.last_mouse_y = e.image_y
    elif e.type == 'mouseup':
        state.dragging = False
    elif e.type == 'mousemove' and state.dragging:
        dx = e.image_x - state.last_mouse_x
        dy = e.image_y - state.last_mouse_y
        state.last_mouse_x = e.image_x
        state.last_mouse_y = e.image_y
        state.project.crop_transform.pan_x_px += dx
        state.project.crop_transform.pan_y_px += dy
        refresh_crop_preview()


async def handle_upload(e: events.UploadEventArguments) -> None:
    upload_file = getattr(e, "file", None)
    raw_name = getattr(e, "name", None) or getattr(upload_file, "name", None) or "uploaded-image.png"
    filename = Path(raw_name).name or "uploaded-image.png"
    name = safe_project_name(Path(filename).stem) or "uploaded-image"
    suffix = Path(filename).suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
        suffix = ".png"

    upload_dir = Path("outputs/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    if upload_file is not None and hasattr(upload_file, "save"):
        await upload_file.save(target)
    elif hasattr(e, "content"):
        data = e.content.read()
        if inspect.isawaitable(data):
            data = await data
        with target.open("wb") as handle:
            handle.write(data)
    else:
        set_status("Upload failed: unsupported NiceGUI upload payload.", negative=True)
        return
    state.source_path = target
    state.source_image = Image.open(target).convert("RGB")
    state.project.project_name = name
    state.project.source_image = str(target)
    state.project.crop_transform = default_crop_transform(str(target), state.project.token_defaults)
    refresh_crop_preview()
    set_status("Image uploaded. Adjust pan/zoom/rotation, then confirm the crop.")


def confirm_crop() -> None:
    if state.source_image is None:
        set_status("Upload an image first.", negative=True)
        return
    state.prepared_image = apply_crop_transform(state.source_image, state.project.crop_transform)
    refresh_styled_preview()
    set_status("Prepared image confirmed. Configure style/palette, then generate the package.")


def persist_preferences_from_ui() -> None:
    state.preferences.printer = state.project.printer_preferences
    state.preferences.token_defaults = state.project.token_defaults
    state.preferences.style_defaults = state.project.style_settings
    state.preferences.palette = state.project.enabled_palette_colors
    state.preferences.imported_fonts = state.project.imported_fonts
    save_preferences(state.preferences)


def generate_package() -> None:
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
    try:
        persist_preferences_from_ui()
        result = run_token_pipeline(state.prepared_image, state.project)
        output_dir = Path("outputs") / safe_project_name(state.project.project_name)
        paths = export_print_package(
            state.project,
            result.mesh,
            result.composition.image,
            result.layer_preview,
            output_dir,
        )
        state.package_paths = paths
        if state.styled_preview_widget:
            state.styled_preview_widget.set_source(image_to_data_url(result.composition.image))
        if state.layer_preview_widget:
            state.layer_preview_widget.set_source(image_to_data_url(result.layer_preview.resize((315, 440))))
        set_status(f"Print package created: {paths['zip']}")
    except Exception as exc:  # pragma: no cover - UI path
        traceback.print_exc()
        set_status(f"Generation failed: {exc}", negative=True)


def build_ui() -> None:
    ui.page_title("Tokenforge Local v0.1")
    with ui.header().classes("items-center justify-between"):
        ui.label("Tokenforge Local v0.1").classes("text-xl font-bold")
        ui.label("Local-only · no G-code · no slicer · no AI")

    with ui.row().classes("w-full no-wrap items-start"):
        with ui.column().classes("w-1/3 gap-4"):
            ui.label("1. Upload and prepare image").classes("text-lg font-bold")
            ui.upload(on_upload=handle_upload, auto_upload=True, label="Upload token art").props("accept=image/*").classes("w-full")

            # Use interactive image for drag-based pan. The size is determined by the crop transform.
            crop_size = (state.project.crop_transform.output_width_px, state.project.crop_transform.output_height_px)
            state.crop_image_widget = ui.interactive_image(
                size=crop_size,
                on_mouse=handle_crop_mouse,
                events=['mousedown','mouseup','mousemove'],
                cross=False,
            ).classes("w-full border rounded")
            with ui.row():
                ui.button("Rotate 90°", on_click=lambda: (rotate_transform_90(state.project.crop_transform), refresh_crop_preview()))
                ui.button("Reset", on_click=lambda: (setattr(state.project, "crop_transform", reset_transform(state.project.crop_transform)), refresh_crop_preview()))
                ui.button("Confirm crop", on_click=confirm_crop).props("color=primary")

            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: (setattr(state.project.crop_transform, "pan_x_px", e.value), refresh_crop_preview())).props("label-always").bind_value(state.project.crop_transform, "pan_x_px").tooltip("Pan X")
            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: (setattr(state.project.crop_transform, "pan_y_px", e.value), refresh_crop_preview())).props("label-always").bind_value(state.project.crop_transform, "pan_y_px").tooltip("Pan Y")
            ui.slider(min=0.5, max=3.0, value=1.0, step=0.01, on_change=lambda e: (setattr(state.project.crop_transform, "scale", float(e.value)), refresh_crop_preview())).props("label-always").bind_value(state.project.crop_transform, "scale").tooltip("Zoom/scale")

            ui.separator()
            ui.label("2. Printer/profile preferences").classes("text-lg font-bold")
            prefs = state.project.printer_preferences
            ui.number("Nozzle size mm", value=prefs.nozzle_size_mm, min=0.1, step=0.05, on_change=lambda e: setattr(prefs, "nozzle_size_mm", float(e.value)))
            ui.number("Initial layer height mm", value=prefs.initial_layer_height_mm, min=0.05, step=0.01, on_change=lambda e: setattr(prefs, "initial_layer_height_mm", float(e.value)))
            ui.number("Standard layer height mm", value=prefs.standard_layer_height_mm, min=0.05, step=0.01, on_change=lambda e: setattr(prefs, "standard_layer_height_mm", float(e.value)))
            ui.number("Finished thickness mm", value=prefs.finished_model_thickness_mm, min=0.4, step=0.05, on_change=lambda e: setattr(prefs, "finished_model_thickness_mm", float(e.value)))
            ui.number("Minimum feature size mm", value=prefs.minimum_feature_size_mm, min=0.1, step=0.05, on_change=lambda e: setattr(prefs, "minimum_feature_size_mm", float(e.value)))

        with ui.column().classes("w-1/3 gap-4"):
            ui.label("3. Style and layout").classes("text-lg font-bold")
            style = state.project.style_settings
            ui.checkbox("Enable border", value=style.border_enabled, on_change=lambda e: (setattr(style, "border_enabled", bool(e.value)), refresh_styled_preview()))
            options = grouped_dropdown_options(include_future=True)
            ui.select(options, label="Border style", value=style.border_style, on_change=lambda e: (setattr(style, "border_style", fallback_if_unimplemented(str(e.value))), refresh_styled_preview()))
            ui.number("Border thickness px", value=style.border_thickness_px, min=2, step=1, on_change=lambda e: (setattr(style, "border_thickness_px", int(e.value)), refresh_styled_preview()))

            ui.checkbox("Enable title text", value=style.title_text.enabled, on_change=lambda e: (setattr(style.title_text, "enabled", bool(e.value)), refresh_styled_preview()))
            ui.input("Title text", value=style.title_text.content, on_change=lambda e: (setattr(style.title_text, "content", e.value), refresh_styled_preview()))
            ui.checkbox("Uppercase title", value=style.title_text.uppercase, on_change=lambda e: (setattr(style.title_text, "uppercase", bool(e.value)), refresh_styled_preview()))
            ui.checkbox("Title banner", value=style.title_text.banner_enabled, on_change=lambda e: (setattr(style.title_text, "banner_enabled", bool(e.value)), refresh_styled_preview()))
            ui.number("Title size px", value=style.title_text.size_px, min=8, step=1, on_change=lambda e: (setattr(style.title_text, "size_px", int(e.value)), refresh_styled_preview()))
            with ui.row():
                ui.number("Title X offset", value=style.title_text.offset_x_px, step=1, on_change=lambda e: (setattr(style.title_text, "offset_x_px", int(e.value)), refresh_styled_preview()))
                ui.number("Title Y offset", value=style.title_text.offset_y_px, step=1, on_change=lambda e: (setattr(style.title_text, "offset_y_px", int(e.value)), refresh_styled_preview()))
            ui.toggle(["emboss", "engrave"], value=style.title_text.emboss_mode, on_change=lambda e: (setattr(style.title_text, "emboss_mode", e.value), refresh_styled_preview()))

            ui.separator()
            ui.checkbox("Enable bottom text", value=style.bottom_text.enabled, on_change=lambda e: (setattr(style.bottom_text, "enabled", bool(e.value)), refresh_styled_preview()))
            ui.textarea("Bottom text", value=style.bottom_text.content, on_change=lambda e: (setattr(style.bottom_text, "content", e.value), refresh_styled_preview())).classes("w-full")
            ui.checkbox("Bottom banner", value=style.bottom_text.banner_enabled, on_change=lambda e: (setattr(style.bottom_text, "banner_enabled", bool(e.value)), refresh_styled_preview()))
            ui.number("Bottom text size px", value=style.bottom_text.size_px, min=8, step=1, on_change=lambda e: (setattr(style.bottom_text, "size_px", int(e.value)), refresh_styled_preview()))
            with ui.row():
                ui.number("Bottom X offset", value=style.bottom_text.offset_x_px, step=1, on_change=lambda e: (setattr(style.bottom_text, "offset_x_px", int(e.value)), refresh_styled_preview()))
                ui.number("Bottom Y offset", value=style.bottom_text.offset_y_px, step=1, on_change=lambda e: (setattr(style.bottom_text, "offset_y_px", int(e.value)), refresh_styled_preview()))
            ui.checkbox("Simple badge/emblem placeholder", value=style.simple_badge_enabled, on_change=lambda e: (setattr(style, "simple_badge_enabled", bool(e.value)), refresh_styled_preview()))

            ui.label("Font import is intentionally deferred. v0.1 stores font metadata and safely falls back if missing.").classes("text-sm text-gray-600")

        with ui.column().classes("w-1/3 gap-4"):
            ui.label("4. Filament palette and export").classes("text-lg font-bold")
            ui.input("Project name", value=state.project.project_name, on_change=lambda e: setattr(state.project, "project_name", safe_project_name(e.value)))
            ui.label("Enable colors before generation. Hex values are local preferences.")
            for color in state.project.enabled_palette_colors:
                with ui.row().classes("items-center"):
                    ui.checkbox(color.name, value=color.enabled, on_change=lambda e, c=color: setattr(c, "enabled", bool(e.value)))
                    ui.input("Hex", value=color.hex, on_change=lambda e, c=color: setattr(c, "hex", e.value)).classes("w-28")

            with ui.row():
                new_name = ui.input("New color name", value="Accent")
                new_hex = ui.input("#hex", value="#ff00ff").classes("w-28")
                def add_color() -> None:
                    state.project.enabled_palette_colors.append(FilamentColor(new_name.value, new_hex.value, True))
                    persist_preferences_from_ui()
                    set_status("Color added. Refresh the page to see it in the simple v0.1 palette list.")
                ui.button("Add color", on_click=add_color)

            ui.button("Generate STL + print package", on_click=generate_package).props("color=primary size=lg")
            state.status = ui.label("Upload an image to begin.").classes("text-sm")

            ui.label("Styled preview").classes("font-bold")
            state.styled_preview_widget = ui.image().classes("w-full border rounded")
            ui.label("Reduced/layer preview").classes("font-bold")
            state.layer_preview_widget = ui.image().classes("w-full border rounded")

            def open_output() -> None:
                if not state.package_paths:
                    set_status("No package has been generated yet.", negative=True)
                    return
                ui.notify(f"ZIP path: {state.package_paths['zip']}")
            ui.button("Show ZIP path", on_click=open_output)


def main() -> None:
    # Pass the root function to NiceGUI to avoid script reloading errors
    ui.run(title="Tokenforge Local", reload=False, show=True, root=build_ui)


if __name__ in {"__main__", "__mp_main__"}:
    main()
