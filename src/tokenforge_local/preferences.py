from __future__ import annotations

import json
from pathlib import Path

from .models import Preferences, dataclass_to_dict, preferences_from_dict

APP_DIR = Path.home() / ".tokenforge-local"
PREFERENCES_PATH = APP_DIR / "preferences.json"


def load_preferences(path: Path | str = PREFERENCES_PATH) -> Preferences:
    path = Path(path)
    if not path.exists():
        prefs = Preferences()
        save_preferences(prefs, path)
        return prefs
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return preferences_from_dict(raw)


def save_preferences(preferences: Preferences, path: Path | str = PREFERENCES_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(dataclass_to_dict(preferences), handle, indent=2)
    return path
