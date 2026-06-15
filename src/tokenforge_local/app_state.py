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
        self.prepared_image: