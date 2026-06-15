from __future__ import annotations

from typing import Any, Callable

from .app_state import mark_dirty, set_num, set_status, state
from .image_editor import reset_transform, rotate_transform_90
from .models import FilamentColor
from .style_presets import fallback_if_unimplemented, grouped_dropdown_options
from .tf_app_handlers import confirm_crop, generate_package, handle_upload, palette_changed, persist_preferences_from_ui, style_changed
from .tf_layer_ui import refresh_layer_controls
from .tf_preview_helpers import handle_crop_mouse, refresh_after_crop_transform_change, refresh_reduced_color_preview, refresh_visual_previews
from .utils import safe_project_name

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


def _refresh_profile_dependents() -> None:
    refresh_layer_controls()
    refresh_reduced_color_preview(False)


def number(label: str, target: Any, attr: str, *, minimum: float | int | None = None, maximum: float | int | None = None, step: float | int = 1, as_int: bool = False, refresh: Callable[[], None] | None = None):
    return ui.number(
        label,
        value=getattr(target, attr),
        min=minimum,
        max=maximum,
        step=step,
        on_change=lambda e: set_num(target, attr, e.value, as_int=as_int, minimum=minimum, maximum=maximum, refresh=refresh),
    )


def build_ui() -> None:
    ui.page_title("Tokenforge Local v0.1.2")
    with ui.header().classes("items-center justify-between"):
        ui.label("Tokenforge Local v0.1.2").classes("text-xl font-bold")
        ui.label("Local-only · no G-code · no slicer · no AI")

    with ui.row().classes("w-full no-wrap items-start"):
        with ui.column().classes("w-1/3 gap-4"):
            ui.label("1. Upload and prepare image").classes("text-lg font-bold")
            ui.upload(on_upload=handle_upload, auto_upload=True, label="Upload token art").props("accept=image/*").classes("w-full")
            state.crop_image_widget = ui.interactive_image(
                size=(state.project.crop_transform.output_width_px, state.project.crop_transform.output_height_px),
                on_mouse=handle_crop_mouse,
                events=["mousedown", "mouseup", "mousemove"],
                cross=False,
            ).classes("w-full border rounded")
            with ui.row():
                ui.button("Rotate 90°", on_click=lambda: (rotate_transform_90(state.project.crop_transform), refresh_after_crop_transform_change()))
                ui.button("Reset", on_click=lambda: (setattr(state.project, "crop_transform", reset_transform(state.project.crop_transform)), refresh_after_crop_transform_change()))
                ui.button("Confirm crop", on_click=confirm_crop).props("color=primary")

            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: set_num(state.project.crop_transform, "pan_x_px", e.value, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "pan_x_px").tooltip("Pan X")
            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: set_num(state.project.crop_transform, "pan_y_px", e.value, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "pan_y_px").tooltip("Pan Y")
            ui.slider(min=0.5, max=3.0, value=1.0, step=0.01, on_change=lambda e: set_num(state.project.crop_transform, "scale", e.value, minimum=0.5, maximum=3.0, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "scale").tooltip("Zoom/scale")

            ui.separator()
            ui.label("2. Printer/profile preferences").classes("text-lg font-bold")
            prefs = state.project.printer_preferences
            number("Nozzle size mm", prefs, "nozzle_size_mm", minimum=0.1, step=0.05, refresh=_refresh_profile_dependents)
            number("Initial layer height mm", prefs, "initial_layer_height_mm", minimum=0.05, step=0.01, refresh=_refresh_profile_dependents)
            number("Standard layer height mm", prefs, "standard_layer_height_mm", minimum=0.05, step=0.01, refresh=_refresh_profile_dependents)
            number("Finished thickness mm", prefs, "finished_model_thickness_mm", minimum=0.4, step=0.05, refresh=_refresh_profile_dependents)
            number("Minimum feature size mm", prefs, "minimum_feature_size_mm", minimum=0.1, step=0.05, refresh=refresh_reduced_color_preview)

        with ui.column().classes("w-1/3 gap-4"):
            ui.label("3. Style and layout").classes("text-lg font-bold")
            style = state.project.style_settings
            ui.checkbox("Enable border", value=style.border_enabled, on_change=lambda e: style_changed(lambda: setattr(style, "border_enabled", bool(e.value))))
            ui.select(grouped_dropdown_options(include_future=True), label="Border style", value=style.border_style, on_change=lambda e: style_changed(lambda: setattr(style, "border_style", fallback_if_unimplemented(str(e.value)))))
            number("Border thickness px", style, "border_thickness_px", minimum=2, step=1, as_int=True, refresh=refresh_visual_previews)

            ui.checkbox("Enable title text", value=style.title_text.enabled, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "enabled", bool(e.value))))
            ui.input("Title text", value=style.title_text.content, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "content", e.value or "")))
            ui.checkbox("Uppercase title", value=style.title_text.uppercase, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "uppercase", bool(e.value))))
            ui.checkbox("Title banner", value=style.title_text.banner_enabled, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "banner_enabled", bool(e.value))))
            number("Title size px", style.title_text, "size_px", minimum=8, step=1, as_int=True, refresh=refresh_visual_previews)
            with ui.row():
                number("Title X offset", style.title_text, "offset_x_px", step=1, as_int=True, refresh=refresh_visual_previews)
                number("Title Y offset", style.title_text, "offset_y_px", step=1, as_int=True, refresh=refresh_visual_previews)
            ui.toggle(["emboss", "engrave"], value=style.title_text.emboss_mode, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "emboss_mode", e.value)))

            ui.separator()
            ui.checkbox("Enable bottom text", value=style.bottom_text.enabled, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "enabled", bool(e.value))))
            ui.textarea("Bottom text", value=style.bottom_text.content, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "content", e.value or ""))).classes("w-full")
            ui.checkbox("Bottom banner", value=style.bottom_text.banner_enabled, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "banner_enabled", bool(e.value))))
            number("Bottom text size px", style.bottom_text, "size_px", minimum=8, step=1, as_int=True, refresh=refresh_visual_previews)
            with ui.row():
                number("Bottom X offset", style.bottom_text, "offset_x_px", step=1, as_int=True, refresh=refresh_visual_previews)
                number("Bottom Y offset", style.bottom_text, "offset_y_px", step=1, as_int=True, refresh=refresh_visual_previews)
            ui.checkbox("Simple badge/emblem placeholder", value=style.simple_badge_enabled, on_change=lambda e: style_changed(lambda: setattr(style, "simple_badge_enabled", bool(e.value))))
            ui.label("Font import is intentionally deferred. v0.1 stores font metadata and safely falls back if missing.").classes("text-sm text-gray-600")

        with ui.column().classes("w-1/3 gap-4"):
            ui.label("4. Filament palette and export").classes("text-lg font-bold")
            ui.input("Project name", value=state.project.project_name, on_change=lambda e: (setattr(state.project, "project_name", safe_project_name(e.value)), mark_dirty(), refresh_reduced_color_preview(False)))
            ui.label("Enable colors before generation. Hex values are local preferences.")
            for color in state.project.enabled_palette_colors:
                with ui.row().classes("items-center"):
                    ui.checkbox(color.name, value=color.enabled, on_change=lambda e, c=color: palette_changed(c, enabled=e.value))
                    ui.input("Hex", value=color.hex, on_change=lambda e, c=color: palette_changed(c, hex_value=e.value)).classes("w-28")

            with ui.row():
                new_name = ui.input("New color name", value="Accent")
                new_hex = ui.input("#hex", value="#ff00ff").classes("w-28")

                def add_color() -> None:
                    state.project.enabled_palette_colors.append(FilamentColor(new_name.value, new_hex.value, True))
                    persist_preferences_from_ui()
                    mark_dirty()
                    refresh_layer_controls()
                    refresh_reduced_color_preview(False)
                    set_status("Color added. Refresh the page to see it in the simple v0.1 palette list.")

                ui.button("Add color", on_click=add_color)

            state.layer_editor_container = ui.column().classes("w-full gap-2")
            refresh_layer_controls()

            with ui.row():
                ui.button("Refresh color preview", on_click=lambda: refresh_reduced_color_preview(True))
                ui.button("Generate STL + print package", on_click=generate_package).props("color=primary size=lg")
            state.status = ui.label("Upload an image to begin.").classes("text-sm")

            ui.label("Styled preview: art + current border/text/style").classes("font-bold")
            state.styled_preview_widget = ui.image().classes("w-full border rounded")
            ui.label("Reduced-color filament preview: posterized to enabled palette colors").classes("font-bold")
            state.reduced_preview_widget = ui.image().classes("w-full border rounded")
            ui.label("Generated layer preview: populated after full STL/package generation").classes("font-bold")
            state.layer_preview_widget = ui.image().classes("w-full border rounded")

            def open_output() -> None:
                if not state.package_paths:
                    set_status("No package has been generated yet.", negative=True)
                    return
                ui.notify(f"ZIP path: {state.package_paths['zip']}")

            ui.button("Show ZIP path", on_click=open_output)


def main() -> None:
    ui.run(title="Tokenforge Local", reload=False, show=True, root=build_ui)
