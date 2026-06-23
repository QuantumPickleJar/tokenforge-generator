from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .app_state import mark_dirty, set_num, set_status, state
from .handoff import build_print_request, decode_handoff_param, serialize_print_request
from .image_editor import reset_transform, rotate_transform_90
from .models import FilamentColor
from .stl_viewer import render_model_viewer
from .style_presets import fallback_if_unimplemented, grouped_dropdown_options
from .tf_3d_handlers import handle_3d_upload, refresh_3d_preview
from .tf_app_handlers import confirm_crop, generate_package, handle_upload, palette_changed, persist_preferences_from_ui, style_changed
from .tf_card_handlers import detect_card_qr, generate_card_output, handle_card_upload, refresh_card_layout_preview, refresh_card_qr_preview
from .tf_handoff_ui import build_handoff_intake
from .tf_layer_ui import refresh_layer_controls
from .tf_preview_helpers import handle_crop_mouse, refresh_after_crop_transform_change, refresh_crop_preview, refresh_reduced_color_preview, refresh_visual_previews
from .tf_ai_handlers import accept_ai_candidate, check_ai_backend, generate_ai_candidate, reject_ai_candidate
from .utils import safe_project_name

try:
    from nicegui import app, context, ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


APP_VERSION = "0.2.1"
APP_BRAND = "Tokenforge"
MODE_IMG = "IMG"
MODE_CARD = "CARD"
MODE_3D = "3D"
MODE_OPTIONS = [MODE_IMG, MODE_CARD, MODE_3D]
DEFAULT_MODE = MODE_IMG
THREE_D_WORKFLOW_TEXT = "STL layer-color preview is available here. 3MF support is planned for a later v0.2 pass."
THREE_D_PREVIEW_LABEL = "Layer color preview — estimated from model Z-height and selected filament changes."
THREE_D_EMPTY_VIEWER_MESSAGE = "Upload an STL to see the layer-color preview here."
CARD_WORKFLOW_TEXT = "Business Card / Flat Relief turns a card image plus confirmed QR content into a clean printable plaque-style STL."
CARD_EDITOR_PLACEHOLDER = "Embedded 2D editor mount point: Fabric.js or Konva.js can later handle move/scale/rotate text, image, logo, and SVG objects."
WORKSPACE_GRID_CLASSES = "w-full grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.95fr)] gap-4 items-start"
EDITOR_COLUMN_CLASSES = "w-full min-w-0 gap-3"
PREVIEW_COLUMN_CLASSES = "w-full min-w-0 gap-3 xl:sticky top-20 self-start"
_OUTPUTS_STATIC_REGISTERED = False
_MODEL_VIEWER_HEAD_ADDED = False


def _load_handoff(encoded_handoff: str | None) -> None:
    """Load one query-string handoff without ever blocking the regular app."""
    result = decode_handoff_param(encoded_handoff)
    state.handoff = result.handoff
    state.handoff_error = result.error
    state.print_request_json = ""
    state.print_request_notes = result.handoff.print.notes if result.handoff else ""
    if result.handoff is None:
        return

    generator = result.handoff.generator
    suggested_name = generator.project_name or result.handoff.item.name
    if suggested_name:
        state.project.project_name = safe_project_name(suggested_name) or state.project.project_name
    if result.handoff.print.nozzle_mm is not None:
        state.project.printer_preferences.nozzle_size_mm = result.handoff.print.nozzle_mm
    if result.handoff.print.layer_height_mm is not None:
        state.project.printer_preferences.standard_layer_height_mm = result.handoff.print.layer_height_mm


def _handoff_workflow_paths() -> dict[str, Path | None]:
    return {
        "img_source": state.source_path,
        "img_stl_preview": state.stl_preview_path,
        "three_d_source": state.three_d_source_path,
        "three_d_preview": state.three_d_preview_path,
        "card_source": state.card_source_path,
        "card_stl": state.card_stl_path,
        "card_glb": state.card_glb_path,
        "card_preview": state.card_output_preview_path,
    }


def _prepare_print_request() -> None:
    if state.handoff is None:
        set_status("Open Tokenforge from a valid gallery handoff before preparing a Printdesk request.", negative=True)
        return
    request = build_print_request(
        state.handoff,
        state.project,
        mode=state.ui_mode,
        package_paths=state.package_paths,
        workflow_paths=_handoff_workflow_paths(),
        notes=state.print_request_notes,
    )
    state.print_request_json = serialize_print_request(request)
    if state.print_request_preview_widget is not None:
        state.print_request_preview_widget.set_value(state.print_request_json)
    set_status("Printdesk request prepared. Download the JSON when you are ready.")


def _download_print_request() -> None:
    if state.handoff is None:
        set_status("No gallery handoff is available for a Printdesk request.", negative=True)
        return
    if not state.print_request_json:
        _prepare_print_request()
    if not state.print_request_json:
        return
    filename = f"{safe_project_name(state.project.project_name) or 'tokenforge'}-printdesk-request.json"
    context.client.download(state.print_request_json.encode("utf-8"), filename, "application/json")
    set_status(f"Downloaded {filename}.")


def _show_handoff_source_dialog(kind: str, url: str) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[40rem] max-w-full gap-3"):
        ui.label(f"Use gallery {kind}").classes("text-lg font-bold")
        ui.label(
            "For this local-first MVP, Tokenforge does not fetch remote gallery files automatically. "
            "Copy this URL, download the file yourself, then upload it in the selected workflow."
        ).classes("text-sm text-gray-700")
        ui.input(f"Gallery {kind} URL", value=url).props("readonly").classes("w-full")
        ui.button("Close", on_click=dialog.close).props("dense")
    dialog.open()


def _ensure_static_outputs_and_viewer_script() -> None:
    global _OUTPUTS_STATIC_REGISTERED, _MODEL_VIEWER_HEAD_ADDED
    Path("outputs").mkdir(parents=True, exist_ok=True)
    if not _OUTPUTS_STATIC_REGISTERED:
        try:
            app.add_static_files("/outputs", "outputs")
        except Exception:
            pass
        _OUTPUTS_STATIC_REGISTERED = True
    if not _MODEL_VIEWER_HEAD_ADDED:
        ui.add_head_html('<script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>')
        _MODEL_VIEWER_HEAD_ADDED = True


def _refresh_profile_dependents() -> None:
    refresh_layer_controls()
    refresh_reduced_color_preview(False)


def _placeholder_status(label: str) -> None:
    set_status(f"{label} menu is reserved for v0.2 workflow actions.", notify=True)


def _set_ai_enabled(value: Any) -> None:
    state.ai_enabled = bool(value)
    state.ai_status = "AI Assist is ready for local ComfyUI." if state.ai_enabled else "AI Assist is disabled."
    if state.ai_entry_button is not None:
        state.ai_entry_button.set_visibility(state.ai_enabled)


def _show_ai_settings_dialog() -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[34rem] max-w-full gap-3"):
        ui.label("AI Backend Settings").classes("text-lg font-bold")
        ui.label("Tokenforge only talks to a separately running local ComfyUI server; it never loads AI models itself.").classes("text-sm text-gray-600")
        ui.input("ComfyUI endpoint", value=state.ai_endpoint, on_change=lambda e: setattr(state, "ai_endpoint", str(e.value or "").rstrip("/"))).classes("w-full")
        ui.input("Workflow JSON template path", value=state.ai_workflow_path, on_change=lambda e: setattr(state, "ai_workflow_path", str(e.value or ""))).classes("w-full")
        ui.label("Use {{input_image}}, {{prompt}}, {{negative_prompt}}, {{preset}}, and optionally {{mask_image}} in your API-format ComfyUI workflow JSON.").classes("text-xs text-gray-600")
        status = ui.label(state.ai_status).classes("text-sm")

        async def test() -> None:
            await check_ai_backend()
            status.set_text(state.ai_status)

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Test connection", on_click=test).props("dense")
            ui.button("Close", on_click=dialog.close).props("dense")
    dialog.open()


def _show_ai_edit_dialog() -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[48rem] max-w-full gap-3"):
        ui.label("✨ AI Edit (local ComfyUI)").classes("text-xl font-bold")
        ui.label("Candidates are previews only. Accept commits one into the IMG workflow; Reject leaves the working image untouched.").classes("text-sm text-gray-600")
        ui.input("Edit prompt", value=state.ai_prompt, on_change=lambda e: setattr(state, "ai_prompt", str(e.value or ""))).classes("w-full")
        ui.input("Negative prompt", value=state.ai_negative_prompt, on_change=lambda e: setattr(state, "ai_negative_prompt", str(e.value or ""))).classes("w-full")
        with ui.grid(columns=2).classes("w-full gap-3"):
            ui.select(["Cleanup", "Background cleanup", "Contrast/detail enhancement", "Inpaint/region edit (workflow placeholder)"], label="Preset", value=state.ai_preset, on_change=lambda e: setattr(state, "ai_preset", str(e.value or "Cleanup"))).classes("w-full")
            ui.select({"current": "Iterate from current image", "candidate": "Iterate from latest candidate"}, label="Iteration source", value=state.ai_iteration_source, on_change=lambda e: setattr(state, "ai_iteration_source", str(e.value or "current"))).classes("w-full")
        ui.checkbox("Protect text / QR", value=state.ai_protect_text_qr, on_change=lambda e: setattr(state, "ai_protect_text_qr", bool(e.value)))
        ui.label("IMG mode has no deterministic overlay by default. CARD can later supply text/QR layers, which Tokenforge will composite over the AI base.").classes("text-xs text-gray-600")
        state.ai_status_label = ui.label(state.ai_status).classes("text-sm")
        state.ai_candidate_preview_widget = ui.image().classes("w-full border rounded max-h-[45vh]")
        if state.ai_candidate_image is not None:
            from .utils import image_to_data_url
            state.ai_candidate_preview_widget.set_source(image_to_data_url(state.ai_candidate_image))

        async def generate() -> None:
            await generate_ai_candidate()

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.button("Generate / Iterate", on_click=generate).props("color=primary")
            ui.button("Test backend", on_click=check_ai_backend).props("dense")
            ui.button("Accept changes", on_click=accept_ai_candidate).props("color=positive dense")
            ui.button("Reject changes", on_click=reject_ai_candidate).props("color=negative dense")
            ui.button("Backend settings", on_click=_show_ai_settings_dialog).props("flat dense")
            ui.button("Close", on_click=dialog.close).props("flat dense")
    dialog.open()


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
        state.ai_entry_button = ui.button("✨ AI Edit", on_click=_show_ai_edit_dialog).props("dense color=secondary")
        state.ai_entry_button.set_visibility(state.ai_enabled)
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


def _build_palette_color_controls() -> None:
    with ui.grid(columns=2).classes("w-full gap-2"):
        for color in state.project.enabled_palette_colors:
            with ui.row().classes("items-center no-wrap gap-2"):
                ui.checkbox(color.name, value=color.enabled, on_change=lambda e, c=color: palette_changed(c, enabled=e.value)).classes("min-w-28")
                ui.input("Hex", value=color.hex, on_change=lambda e, c=color: palette_changed(c, hex_value=e.value)).classes("w-28")


def _build_add_color_row() -> None:
    with ui.row().classes("items-end gap-2"):
        new_name = ui.input("New color name", value="Accent").classes("w-40")
        new_hex = ui.input("#hex", value="#ff00ff").classes("w-28")

        def add_color() -> None:
            state.project.enabled_palette_colors.append(FilamentColor(new_name.value, new_hex.value, True))
            persist_preferences_from_ui()
            mark_dirty()
            refresh_layer_controls()
            refresh_reduced_color_preview(False)
            refresh_card_qr_preview()
            set_status("Color added. Refresh the page to see it in the simple palette list.")

        ui.button("Add color", on_click=add_color).props("dense")


def _build_palette_panel() -> None:
    ui.label("Filament palette and layer plan").classes("text-lg font-bold")
    with ui.card().classes("w-full gap-3"):
        ui.input("Project name", value=state.project.project_name, on_change=lambda e: (setattr(state.project, "project_name", safe_project_name(e.value)), mark_dirty(), refresh_reduced_color_preview(False))).classes("w-full")
        ui.label("Enable colors before generation. The layer rail below controls print order and color spans.").classes("text-sm text-gray-600")
        _build_palette_color_controls()
        _build_add_color_row()

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
            ui.label("Reduced-color filament preview").classes("font-bold")
            ui.label("Layer-span print preview: simulates cumulative layer spans, so changing a color's layer count changes this view.").classes("text-xs text-gray-600")
            state.reduced_preview_widget = ui.image().classes("w-full border rounded")

    with ui.card().classes("w-full gap-1"):
        ui.label("Generated layer preview").classes("font-bold")
        ui.label("Populated after full STL/package generation using the same span-aware preview model.").classes("text-xs text-gray-600")
        state.layer_preview_widget = ui.image().classes("w-full border rounded max-h-[45vh]")

    with ui.card().classes("w-full gap-1"):
        ui.label("Generated 3D STL viewer").classes("font-bold")
        ui.label("Populated after generation. The STL is still exported; this viewer uses a matching GLB preview artifact.").classes("text-xs text-gray-600")
        state.stl_viewer_container = ui.column().classes("w-full")
        render_model_viewer(state.stl_viewer_container, state.stl_preview_path)


def _show_output_path() -> None:
    if not state.package_paths:
        set_status("No package has been generated yet.", negative=True)
        return
    ui.notify(f"ZIP path: {state.package_paths['zip']}")


def _build_card_settings_panel() -> None:
    settings = state.card_settings
    with ui.card().classes("w-full gap-3"):
        ui.label("Step 4 — Relief settings").classes("text-lg font-bold")
        ui.label("These settings favor single-nozzle/manual filament-change prints: base card, raised QR/text band, optional higher accent later.").classes("text-sm text-gray-600")
        with ui.grid(columns=2).classes("w-full gap-3"):
            number("Card width mm", settings, "card_width_mm", minimum=30, step=0.5, refresh=refresh_card_qr_preview).classes("w-full")
            number("Card height mm", settings, "card_height_mm", minimum=20, step=0.5, refresh=refresh_card_qr_preview).classes("w-full")
            number("Base thickness mm", settings, "base_thickness_mm", minimum=0.2, step=0.05, refresh=refresh_card_qr_preview).classes("w-full")
            number("Raised QR/text height mm", settings, "raised_feature_height_mm", minimum=0.05, step=0.05, refresh=refresh_card_qr_preview).classes("w-full")
            number("Optional accent height mm", settings, "accent_height_mm", minimum=0.05, step=0.05, refresh=refresh_card_qr_preview).classes("w-full")
            number("Corner radius mm", settings, "corner_radius_mm", minimum=0, step=0.25, refresh=refresh_card_qr_preview).classes("w-full")
            number("QR physical size mm", settings, "qr_size_mm", minimum=8, step=0.5, refresh=refresh_card_qr_preview).classes("w-full")
            number("QR quiet zone modules", settings, "qr_quiet_zone_modules", minimum=0, maximum=12, step=1, as_int=True, refresh=refresh_card_qr_preview).classes("w-full")
        state.card_feature_warning_label = ui.label("QR feature warning: enter or detect QR content to estimate module size.").classes("text-sm text-orange-700")


def _build_card_workflow() -> None:
    with ui.element("div").classes(WORKSPACE_GRID_CLASSES):
        with ui.column().classes(EDITOR_COLUMN_CLASSES):
            with ui.card().classes("w-full gap-3"):
                ui.label("Business Card / Flat Relief").classes("text-xl font-bold")
                ui.label(CARD_WORKFLOW_TEXT).classes("text-sm text-gray-600")
                ui.label("AI editing is reserved for non-critical background/art cleanup. Deterministic Tokenforge QR and text layers remain the source of truth.").classes("text-xs text-gray-600")

            with ui.card().classes("w-full gap-3"):
                ui.label("Step 1 — Upload card image").classes("text-lg font-bold")
                ui.upload(on_upload=handle_card_upload, auto_upload=True, label="Upload business card image").props("accept=image/png,image/jpeg,image/webp").classes("w-full")
                ui.label("Boundary detection/rectify is staged for a later pass. Use a reasonably straight card image for this MVP.").classes("text-xs text-gray-600")
                state.card_source_preview_widget = ui.image().classes("w-full border rounded max-h-[36vh]")

            with ui.card().classes("w-full gap-3"):
                ui.label("Step 2 — Detect or enter QR").classes("text-lg font-bold")
                state.card_qr_label = ui.label("QR detection: upload a card image or enter QR content manually.").classes("text-sm")
                ui.button("Detect QR from uploaded image", on_click=detect_card_qr).props("dense color=primary")
                state.card_qr_input = ui.textarea(
                    "Confirmed/manual QR content or URL",
                    value=state.card_qr_content,
                    on_change=lambda e: (setattr(state, "card_qr_content", e.value or ""), refresh_card_qr_preview()),
                ).classes("w-full")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Generate / validate clean QR", on_click=refresh_card_qr_preview).props("dense")
                    ui.button("Refresh card layout preview", on_click=refresh_card_layout_preview).props("dense")
                state.card_qr_validation_label = ui.label("QR validation: waiting for content.").classes("text-sm text-gray-700")
                state.card_qr_preview_widget = ui.image().classes("w-56 max-w-full border rounded")

            with ui.card().classes("w-full gap-3"):
                ui.label("Step 3 — Layout extraction / cleanup").classes("text-lg font-bold")
                ui.select(
                    [
                        "Source image as reference only",
                        "Simple threshold/vector extraction",
                        "Regenerated QR + simple relief blocks",
                    ],
                    label="Cleanup mode",
                    value=state.card_layout_mode,
                    on_change=lambda e: setattr(state, "card_layout_mode", str(e.value or "")),
                ).classes("w-full")
                ui.label("Current MVP generates a clean regenerated QR on a printable card base. Text/logo extraction hooks are intentionally placeholder-only.").classes("text-sm text-gray-600")
                with ui.card().classes("w-full bg-grey-1"):
                    ui.label(CARD_EDITOR_PLACEHOLDER).classes("text-xs text-gray-600")

            _build_card_settings_panel()

            with ui.card().classes("w-full gap-3"):
                ui.label("Layer plan for manual filament changes").classes("font-bold")
                ui.label("Use the same Tokenforge palette/rail to plan base and raised QR color changes. Single-nozzle output is the primary target.").classes("text-sm text-gray-600")
                _build_palette_color_controls()
                _build_add_color_row()
            state.layer_editor_container = ui.column().classes("w-full gap-2")
            refresh_layer_controls()

        with ui.column().classes(PREVIEW_COLUMN_CLASSES):
            with ui.card().classes("w-full gap-3"):
                ui.label("Step 5 — Preview and output").classes("text-lg font-bold")
                state.status = ui.label("Upload a card or enter QR content to begin.").classes("text-sm")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Generate card STL + browser preview", on_click=generate_card_output).props("color=primary dense")
                    ui.button("Refresh 2D preview", on_click=refresh_card_layout_preview).props("dense")
                state.card_output_label = ui.label("No business card output generated yet.").classes("text-sm text-gray-700")

            with ui.card().classes("w-full gap-2"):
                ui.label("Reduced-color 2D card preview").classes("font-bold")
                ui.label("Clean regenerated QR on a plaque-style card base; source image is reference-only in this MVP.").classes("text-xs text-gray-600")
                state.card_output_preview_widget = ui.image().classes("w-full border rounded")

            with ui.card().classes("w-full gap-2"):
                ui.label("Business card relief 3D preview").classes("font-bold")
                ui.label("Generated as a GLB beside the STL so you can inspect it without downloading first.").classes("text-xs text-gray-600")
                state.card_viewer_container = ui.column().classes("w-full")
                render_model_viewer(state.card_viewer_container, state.card_glb_path, empty_message="Generate card relief output to populate the 3D preview.")

    refresh_card_qr_preview()


def _build_img_workflow() -> None:
    with ui.element("div").classes(WORKSPACE_GRID_CLASSES):
        with ui.column().classes(EDITOR_COLUMN_CLASSES):
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

        with ui.column().classes(PREVIEW_COLUMN_CLASSES):
            _build_preview_panel()

    refresh_crop_preview()
    if state.prepared_image is not None:
        refresh_visual_previews()


def _build_3d_workflow() -> None:
    with ui.element("div").classes(WORKSPACE_GRID_CLASSES):
        with ui.column().classes(EDITOR_COLUMN_CLASSES):
            with ui.card().classes("w-full gap-3"):
                ui.label("3D model import").classes("text-lg font-bold")
                ui.label(THREE_D_WORKFLOW_TEXT).classes("text-sm text-gray-600")
                ui.upload(on_upload=handle_3d_upload, auto_upload=True, label="Upload STL model").props("accept=.stl,.STL,.3mf,.3MF").classes("w-full")
                state.status = ui.label("Upload an STL to begin the 3D layer-color preview workflow.").classes("text-sm")
                state.three_d_model_label = ui.label(f"Model: {state.three_d_model_name or 'none loaded'}").classes("text-sm font-bold")
                state.three_d_bounds_label = ui.label(state.three_d_bounds_summary or "Bounds: no model loaded yet.").classes("text-sm text-gray-700")
                state.three_d_color_label = ui.label(state.three_d_color_summary or "Colors: using current Tokenforge palette and layer rail.").classes("text-sm text-gray-700")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Refresh 3D layer preview", on_click=refresh_3d_preview).props("color=primary dense")
                    ui.button("3MF support", on_click=lambda: set_status("3MF parsing is coming later in v0.2; upload STL for now.", notify=True)).props("dense flat")

            with ui.card().classes("w-full gap-3"):
                ui.label("Filament colors used by 3D preview").classes("font-bold")
                ui.label("These are the same local palette colors used in IMG mode. The rail below maps them to the imported model's Z height.").classes("text-sm text-gray-600")
                _build_palette_color_controls()
                _build_add_color_row()

            state.layer_editor_container = ui.column().classes("w-full gap-2")
            refresh_layer_controls()

        with ui.column().classes(PREVIEW_COLUMN_CLASSES):
            with ui.card().classes("w-full gap-2"):
                ui.label("Layer color preview").classes("text-lg font-bold")
                ui.label(THREE_D_PREVIEW_LABEL).classes("text-sm text-gray-600")
                ui.label("MVP accuracy: each triangle is colored by its face-centroid Z height. Triangles are not split at exact layer boundaries yet.").classes("text-xs text-gray-600")
                state.three_d_viewer_container = ui.column().classes("w-full")
                render_model_viewer(state.three_d_viewer_container, state.three_d_preview_path, empty_message=THREE_D_EMPTY_VIEWER_MESSAGE)


def build_ui(handoff: str | None = None) -> None:
    _ensure_static_outputs_and_viewer_script()
    ui.page_title(f"{APP_BRAND} Local v{APP_VERSION}")
    _load_handoff(handoff)
    initial_mode = DEFAULT_MODE
    if state.handoff and state.handoff.generator.mode in MODE_OPTIONS:
        initial_mode = state.handoff.generator.mode
    state.ui_mode = initial_mode
    content_container: Any | None = None
    mode_toggle: Any | None = None

    def render_mode(mode: str) -> None:
        selected = mode if mode in MODE_OPTIONS else DEFAULT_MODE
        state.ui_mode = selected
        if mode_toggle is not None:
            mode_toggle.set_value(selected)
        if content_container is None:
            return
        content_container.clear()
        with content_container:
            if selected == MODE_3D:
                _build_3d_workflow()
            elif selected == MODE_CARD:
                _build_card_workflow()
            else:
                _build_img_workflow()

    with ui.header().classes("w-full items-center gap-3 no-wrap px-3 py-2"):
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.label(APP_BRAND).classes("text-xl font-bold")
            ui.label(f"v{APP_VERSION}").classes("text-xs text-gray-200")
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.button("File", on_click=lambda: _placeholder_status("File")).props("flat dense")
            ui.button("Edit", on_click=lambda: _placeholder_status("Edit")).props("flat dense")
            with ui.button("View").props("flat dense"):
                with ui.menu().classes("p-2 gap-2"):
                    ui.checkbox("Enable AI Assist", value=state.ai_enabled, on_change=lambda e: _set_ai_enabled(e.value))
                    ui.button("AI Backend Settings", on_click=_show_ai_settings_dialog).props("flat dense")
            ui.button("Undo", icon="undo").props("flat dense disable").tooltip("Undo history is planned for v0.2.")
            ui.button("Redo", icon="redo").props("flat dense disable").tooltip("Redo history is planned for v0.2.")
        ui.space()
        mode_toggle = ui.toggle(MODE_OPTIONS, value=initial_mode, on_change=lambda e: render_mode(str(e.value))).props("dense unelevated toggle-color=primary").classes("font-bold min-w-[13rem]")

    content_container = ui.column().classes("w-full p-3 gap-3")
    state.print_request_preview_widget = build_handoff_intake(
        state.handoff,
        state.handoff_error,
        notes=state.print_request_notes,
        request_json=state.print_request_json,
        on_notes_change=lambda value: setattr(state, "print_request_notes", value),
        on_prepare_request=_prepare_print_request,
        on_download_request=_download_print_request,
        on_use_image=lambda: (render_mode(MODE_IMG), _show_handoff_source_dialog("image", state.handoff.item.image_url)),
        on_use_model=lambda: (render_mode(MODE_3D), _show_handoff_source_dialog("model", state.handoff.item.model_url)),
    )
    render_mode(initial_mode)


def main() -> None:
    ui.run(title="Tokenforge Local", reload=False, show=True, root=build_ui)
