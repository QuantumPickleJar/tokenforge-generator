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


def number(
    label: str,
    target: Any,
    attr: str,
    *,
    minimum: float | int | None = None,
    maximum: float | int | None = None,
    step: float | int = 1,
    as_int: bool = False,
    refresh: Callable[[], None] | None = None,
):
    return ui.number(
        label,
        value=getattr(target, attr),
        min=minimum,
        max=maximum,
        step=step,
        on_change=lambda e: set_num(target, attr, e.value, as_int=as_int, minimum=minimum, maximum=maximum, refresh=refresh),
    )


def _build_prepare_panel() -> None:
    ui.label("Upload and crop").classes("text-lg font-bold")
    with ui.card().classes("w-full gap-3"):
        ui.upload(on_upload=handle_upload, auto_upload=True, label="Upload token art").props("accept=image/*").classes("w-full")
        state.crop_image_widget = ui.interactive_image(
            size=(state.project.crop_transform.output_width_px, state.project.crop_transform.output_height_px),
            on_mouse=handle_crop_mouse,
            events=["mousedown", "mouseup", "mousemove"],
            cross=False,
        ).classes("w-full border rounded max-h-[58vh]")

        with ui.row().classes("items-center gap-2"):
            ui.button("Rotate 90°", on_click=lambda: (rotate_transform_90(state.project.crop_transform), refresh_after_crop_transform_change())).props("dense")
            ui.button("Reset", on_click=lambda: (setattr(state.project, "crop_transform", reset_transform(state.project.crop_transform)), refresh_after_crop_transform_change())).props("dense")
            ui.button("Confirm crop", on_click=confirm_crop).props("color=primary dense")

        ui.label("Pan and zoom").classes("font-bold")
        with ui.grid(columns=3).classes("w-full gap-3"):
            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: set_num(state.project.crop_transform, "pan_x_px", e.value, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "pan_x_px").tooltip("Pan X")
            ui.slider(min=-400, max=400, value=0, step=1, on_change=lambda e: set_num(state.project.crop_transform, "pan_y_px", e.value, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "pan_y_px").tooltip("Pan Y")
            ui.slider(min=0.5, max=3.0, value=1.0, step=0.01, on_change=lambda e: set_num(state.project.crop_transform, "scale", e.value, minimum=0.5, maximum=3.0, refresh=refresh_after_crop_transform_change)).props("label-always").bind_value(state.project.crop_transform, "scale").tooltip("Zoom/scale")


def _build_profile_panel() -> None:
    ui.label("Printer profile").classes("text-lg font-bold")
    prefs = state.project.printer_preferences
    with ui.card().classes("w-full"):
        ui.label("Layer heights here drive the color-change layer plan and final STL height.").classes("text-sm text-gray-600")
        with ui.grid(columns=2).classes("w-full gap-3"):
            number("Nozzle size mm", prefs, "nozzle_size_mm", minimum=0.1, step=0.05, refresh=_refresh_profile_dependents).classes("w-full")
            number("Initial layer height mm", prefs, "initial_layer_height_mm", minimum=0.05, step=0.01, refresh=_refresh_profile_dependents).classes("w-full")
            number("Standard layer height mm", prefs, "standard_layer_height_mm", minimum=0.05, step=0.01, refresh=_refresh_profile_dependents).classes("w-full")
            number("Finished thickness mm", prefs, "finished_model_thickness_mm", minimum=0.4, step=0.05, refresh=_refresh_profile_dependents).classes("w-full")
            number("Minimum feature size mm", prefs, "minimum_feature_size_mm", minimum=0.1, step=0.05, refresh=refresh_reduced_color_preview).classes("w-full")


def _build_style_panel() -> None:
    ui.label("Style and layout").classes("text-lg font-bold")
    style = state.project.style_settings

    with ui.expansion("Border", value=True).classes("w-full"):
        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.checkbox("Enable border", value=style.border_enabled, on_change=lambda e: style_changed(lambda: setattr(style, "border_enabled", bool(e.value))))
            ui.select(grouped_dropdown_options(include_future=True), label="Border style", value=style.border_style, on_change=lambda e: style_changed(lambda: setattr(style, "border_style", fallback_if_unimplemented(str(e.value))))).classes("w-full")
            number("Border thickness px", style, "border_thickness_px", minimum=2, step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")
            ui.checkbox("Simple badge/emblem placeholder", value=style.simple_badge_enabled, on_change=lambda e: style_changed(lambda: setattr(style, "simple_badge_enabled", bool(e.value))))

    with ui.expansion("Title text", value=True).classes("w-full"):
        ui.input("Title text", value=style.title_text.content, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "content", e.value or ""))).classes("w-full")
        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.checkbox("Enable title text", value=style.title_text.enabled, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "enabled", bool(e.value))))
            ui.checkbox("Uppercase title", value=style.title_text.uppercase, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "uppercase", bool(e.value))))
            ui.checkbox("Title banner", value=style.title_text.banner_enabled, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "banner_enabled", bool(e.value))))
            ui.toggle(["emboss", "engrave"], value=style.title_text.emboss_mode, on_change=lambda e: style_changed(lambda: setattr(style.title_text, "emboss_mode", e.value))).classes("w-full")
            number("Title size px", style.title_text, "size_px", minimum=8, step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")
            number("Title X offset", style.title_text, "offset_x_px", step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")
            number("Title Y offset", style.title_text, "offset_y_px", step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")

    with ui.expansion("Bottom text", value=False).classes("w-full"):
        ui.textarea("Bottom text", value=style.bottom_text.content, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "content", e.value or ""))).classes("w-full")
        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.checkbox("Enable bottom text", value=style.bottom_text.enabled, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "enabled", bool(e.value))))
            ui.checkbox("Bottom banner", value=style.bottom_text.banner_enabled, on_change=lambda e: style_changed(lambda: setattr(style.bottom_text, "banner_enabled", bool(e.value))))
            number("Bottom text size px", style.bottom_text, "size_px", minimum=8, step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")
            number("Bottom X offset", style.bottom_text, "offset_x_px", step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")
            number("Bottom Y offset", style.bottom_text, "offset_y_px", step=1, as_int=True, refresh=refresh_visual_previews).classes("w-full")

    ui.label("Font import is intentionally deferred. v0.1 stores font metadata and safely falls back if missing.").classes("text-sm text-gray-600")


def _build_palette_panel() -> None:
    ui.label("Filament palette and layer plan").classes("text-lg font-bold")
    with ui.card().classes("w-full gap-3"):
        ui.input("Project name", value=state.project.project_name, on_change=lambda e: (setattr(state.project, "project_name", safe_project_name(e.value)), mark_dirty(), refresh_reduced_color_preview(False))).classes("w-full")
        ui.label("Enable colors before generation. The layer rail below controls print order and color spans.").classes("text-sm text-gray-600")

        with ui.grid(columns=2).classes("w-full gap-2"):
            for color in state.project.enabled_palette_colors:
                with ui.row().classes("items-center no-wrap gap-2"):
                    ui.checkbox(color.name, value=color.enabled, on_change=lambda e, c=color: palette_changed(c, enabled=e.value)).classes("min-w-28")
                    ui.input("Hex", value=color.hex, on_change=lambda e, c=color: palette_changed(c, hex_value=e.value)).classes("w-28")

        with ui.row().classes("items-end gap-2"):
            new_name = ui.input("New color name", value="Accent").classes("w-40")
            new_hex = ui.input("#hex", value="#ff00ff").classes("w-28")

            def add_color() -> None:
                state.project.enabled_palette_colors.append(FilamentColor(new_name.value, new_hex.value, True))
                persist_preferences_from_ui()
                mark_dirty()
                refresh_layer_controls()
                refresh_reduced_color_preview(False)
                set_status("Color added. Refresh the page to see it in the simple v0.1 palette list.")

            ui.button("Add color", on_click=add_color).props("dense")

    state.layer_editor_container = ui.column().classes("w-full gap-2")
    refresh_layer_controls()


def _build_preview_panel() -> None:
    with ui.card().classes("w-full gap-3"):
        ui.label("Export controls").classes("text-lg font-bold")
        state.status = ui.label("Upload an image to begin.").classes("text-sm")
        with ui.row().classes("items-center gap-2"):
            ui.button("Refresh color preview", on_click=lambda: refresh_reduced_color_preview(True)).props("dense")
            ui.button("Generate STL + print package", on_click=generate_package).props("color=primary size=lg")
            ui.button("Show ZIP path", on_click=_show_output_path).props("dense")

    with ui.grid(columns=2).classes("w-full gap-3"):
        with ui.card().classes("w-full gap-1"):
            ui.label("Styled preview").classes("font-bold")
            ui.label("Art + current border/text/style.").classes("text-xs text-gray-600")
            state.styled_preview_widget = ui.image().classes("w-full border rounded")
        with ui.card().classes("w-full gap-1"):
            ui.label("Layer-span print preview").classes("font-bold")
            ui.label("Simulates cumulative layer spans, so changing a color's layer count changes this view.").classes("text-xs text-gray-600")
            state.reduced_preview_widget = ui.image().classes("w-full border rounded")

    with ui.card().classes("w-full gap-1"):
        ui.label("Generated layer preview").classes("font-bold")
        ui.label("Populated after full STL/package generation using the same span-aware preview model.").classes("text-xs text-gray-600")
        state.layer_preview_widget = ui.image().classes("w-full border rounded max-h-[45vh]")


def _show_output_path() -> None:
    if not state.package_paths:
        set_status("No package has been generated yet.", negative=True)
        return
    ui.notify(f"ZIP path: {state.package_paths['zip']}")


def build_ui() -> None:
    ui.page_title("Tokenforge Local v0.1.3")
    with ui.header().classes("items-center justify-between"):
        ui.label("Tokenforge Local v0.1.3").classes("text-xl font-bold")
        ui.label("Local-only · no G-code · no slicer · no AI")

    with ui.row().classes("w-full no-wrap items-start gap-4"):
        with ui.column().classes("w-1/2 gap-3"):
            with ui.tabs().classes("w-full") as tabs:
                prepare_tab = ui.tab("Prepare")
                style_tab = ui.tab("Style")
                palette_tab = ui.tab("Palette + layers")
                profile_tab = ui.tab("Printer")

            with ui.tab_panels(tabs, value=prepare_tab).classes("w-full"):
                with ui.tab_panel(prepare_tab).classes("gap-3"):
                    _build_prepare_panel()
                with ui.tab_panel(style_tab).classes("gap-3"):
                    _build_style_panel()
                with ui.tab_panel(palette_tab).classes("gap-3"):
                    _build_palette_panel()
                with ui.tab_panel(profile_tab).classes("gap-3"):
                    _build_profile_panel()

        with ui.column().classes("w-1/2 gap-3 sticky top-20 self-start"):
            _build_preview_panel()


def main() -> None:
    ui.run(title="Tokenforge Local", reload=False, show=True, root=build_ui)
