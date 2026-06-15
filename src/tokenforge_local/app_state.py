from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from PIL import Image

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
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.prepared_image: Image.Image | None = None
        self.package_paths: dict[str, Path] | None = None
        self.reduced_preview_path: Path | None = None
        self.crop_image_widget = None
        self.styled_preview_widget = None
        self.reduced_preview_widget = None
        self.layer_preview_widget = None
        self.status = None
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
        pass
