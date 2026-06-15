from __future__ import annotations

from pathlib import Path
import inspect
import traceback
from typing import Any, Callable

from PIL import Image

from .composition import build_styled_composition
from .export_package import export_print_package
from .image_editor import apply_crop_transform, default_crop_transform, preview_with_stencil, reset_transform, rotate_transform_90
from .image_pipeline import run_token_pipeline
from .models import FilamentColor, Preferences, ProjectState
from .palette import enabled_colors, map_image_to_palette, sort_colors_for_layering