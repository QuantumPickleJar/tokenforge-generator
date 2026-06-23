from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from PIL import Image

from .business_card import BusinessCardSettings
from .models import FilamentColor, Preferences, ProjectState
from .preferences import load_preferences

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
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
        self.ui_mode: str = "IMG"
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.prepared_image: Image.Image | None = None
        # Optional local AI editing session. These are deliberately separate from
        # the normal IMG state until the user explicitly accepts a candidate.
        self.ai_enabled: bool = False
        self.ai_backend: str = "comfyui"
        self.ai_endpoint: str = "http://127.0.0.1:8188"
        self.ai_workflow_path: str = ""
        self.ai_status: str = "AI Assist is disabled."
        self.ai_last_error: str | None = None
        self.ai_job_running: bool = False
        self.ai_original_image: Image.Image | None = None
        self.ai_original_path: Path | None = None
        self.ai_candidate_image: Image.Image | None = None
        self.ai_candidate_path: Path | None = None
        self.ai_previous_candidate_image: Image.Image | None = None
        self.ai_prompt: str = ""
        self.ai_negative_prompt: str = ""
        self.ai_preset: str = "Cleanup"
        self.ai_prompt_history: list[str] = []
        self.ai_candidate_history: list[Path] = []
        self.ai_iteration_source: str = "current"
        self.ai_protect_text_qr: bool = True
        self.ai_protected_overlay: Image.Image | None = None
        self.package_paths: dict[str, Path] | None = None
        self.reduced_preview_path: Path | None = None
        self.stl_preview_path: Path | None = None

        self.three_d_source_path: Path | None = None
        self.three_d_preview_path: Path | None = None
        self.three_d_model_name: str | None = None
        self.three_d_bounds_summary: str | None = None
        self.three_d_color_summary: str | None = None
        self.three_d_face_count: int | None = None
        self.three_d_vertex_count: int | None = None
        self.three_d_last_error: str | None = None

        self.card_settings = BusinessCardSettings()
        self.card_source_path: Path | None = None
        self.card_source_image: Image.Image | None = None
        self.card_qr_content: str = ""
        self.card_layout_mode: str = "Regenerated QR + simple relief blocks"
        self.card_output_preview_path: Path | None = None
        self.card_stl_path: Path | None = None
        self.card_glb_path: Path | None = None

        self.crop_image_widget = None
        self.styled_preview_widget = None
        self.reduced_preview_widget = None
        self.layer_preview_widget = None
        self.layer_editor_container = None
        self.stl_viewer_container = None
        self.three_d_viewer_container = None
        self.three_d_model_label = None
        self.three_d_bounds_label = None
        self.three_d_color_label = None

        self.card_source_preview_widget = None
        self.card_qr_preview_widget = None
        self.card_output_preview_widget = None
        self.card_viewer_container = None
        self.card_qr_label = None
        self.card_qr_validation_label = None
        self.card_feature_warning_label = None
        self.card_output_label = None
        self.card_qr_input = None
        self.ai_status_label = None
        self.ai_candidate_preview_widget = None
        self.ai_entry_button = None

        self.status = None
        self.is_generating = False
        self.dragging = False
        self.last_mouse_x = 0.0
        self.last_mouse_y = 0.0


state = AppState()


def set_status(message: str, negative: bool = False, notify: bool = True) -> None:
    if state.status:
        state.status.set_text(message)
    if notify:
        ui.notify(message, type="negative" if negative else "info")


def coerce_int(value: Any, fallback: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(fallback) if value is None or value == "" else int(float(value))
    except (TypeError, ValueError):
        result = int(fallback)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def coerce_float(value: Any, fallback: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        result = float(fallback) if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        result = float(fallback)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def mark_dirty() -> None:
    state.package_paths = None
    state.stl_preview_path = None
    state.three_d_preview_path = None
    state.project.generated_layer_plan = None


def set_num(target: Any, attr: str, value: Any, *, as_int: bool = False, minimum: float | int | None = None, maximum: float | int | None = None, refresh: Callable[[], None] | None = None) -> None:
    current = getattr(target, attr)
    converted = coerce_int(value, current, minimum, maximum) if as_int else coerce_float(value, current, minimum, maximum)
    setattr(target, attr, converted)
    mark_dirty()
    if refresh:
        refresh()


def clear_widget(widget: Any) -> None:
    if widget is None:
        return
    try:
        widget.set_source("")
    except Exception:
        try:
            widget.clear()
        except Exception:
            pass
