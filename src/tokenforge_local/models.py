from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal


EmbossMode = Literal["emboss", "engrave"]


@dataclass(slots=True)
class PrinterPreferences:
    nozzle_size_mm: float = 0.4
    initial_layer_height_mm: float = 0.20
    standard_layer_height_mm: float = 0.20
    finished_model_thickness_mm: float = 1.20
    minimum_feature_size_mm: float = 0.60


@dataclass(slots=True)
class TokenDefaults:
    width_mm: float = 63.0
    height_mm: float = 87.9
    corner_radius_mm: float = 2.5


@dataclass(slots=True)
class FilamentColor:
    name: str
    hex: str
    enabled: bool = True


@dataclass(slots=True)
class FontReference:
    family: str = "DejaVu Sans"
    source: Literal["system", "imported"] = "system"
    path: str | None = None
    license_note: str | None = None


@dataclass(slots=True)
class CropTransform:
    source_image: str | None = None
    pan_x_px: float = 0.0
    pan_y_px: float = 0.0
    scale: float = 1.0
    rotation_degrees: int = 0
    output_width_px: int = 630
    output_height_px: int = 879


@dataclass(slots=True)
class TextLayoutConfig:
    enabled: bool = False
    content: str = ""
    font_family: str = "DejaVu Sans"
    size_px: int = 42
    offset_x_px: int = 0
    offset_y_px: int = 0
    uppercase: bool = False
    banner_enabled: bool = True
    emboss_mode: EmbossMode = "emboss"


@dataclass(slots=True)
class StyleSettings:
    border_enabled: bool = True
    border_style: str = "thin_line"
    border_thickness_px: int = 16
    title_text: TextLayoutConfig = field(default_factory=lambda: TextLayoutConfig(enabled=True, content="TOKEN", size_px=44))
    bottom_text: TextLayoutConfig = field(default_factory=lambda: TextLayoutConfig(enabled=False, content="", size_px=28))
    simple_badge_enabled: bool = False
    background_panel_enabled: bool = False


@dataclass(slots=True)
class LayerBand:
    layer_number: int
    z_height_mm: float
    color_name: str
    color_hex: str
    action: str


@dataclass(slots=True)
class LayerPlan:
    base_layers: int
    color_layers: list[LayerBand]
    total_layers: int
    finished_thickness_mm: float
    snapped_from_mm: float | None = None
    snap_warning: str | None = None


@dataclass(slots=True)
class ProjectState:
    project_name: str = "tokenforge-token"
    source_image: str | None = None
    crop_transform: CropTransform = field(default_factory=CropTransform)
    printer_preferences: PrinterPreferences = field(default_factory=PrinterPreferences)
    token_defaults: TokenDefaults = field(default_factory=TokenDefaults)
    enabled_palette_colors: list[FilamentColor] = field(default_factory=list)
    style_settings: StyleSettings = field(default_factory=StyleSettings)
    imported_fonts: list[FontReference] = field(default_factory=list)
    generated_layer_plan: LayerPlan | None = None


@dataclass(slots=True)
class Preferences:
    printer: PrinterPreferences = field(default_factory=PrinterPreferences)
    token_defaults: TokenDefaults = field(default_factory=TokenDefaults)
    style_defaults: StyleSettings = field(default_factory=StyleSettings)
    palette: list[FilamentColor] = field(default_factory=lambda: [
        FilamentColor("Black", "#111111", True),
        FilamentColor("Light Gray", "#bbbbbb", True),
        FilamentColor("Ivory White", "#f2ead7", True),
        FilamentColor("PLA Gold", "#c7a34a", True),
        FilamentColor("Sky Blue", "#69b7ff", False),
        FilamentColor("Pink", "#ff75b5", False),
        FilamentColor("Green", "#49a95b", False),
        FilamentColor("Red", "#d23a35", False),
        FilamentColor("Dark Tan", "#7a5533", False),
    ])
    imported_fonts: list[FontReference] = field(default_factory=list)


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: dataclass_to_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def printer_from_dict(raw: dict[str, Any]) -> PrinterPreferences:
    return PrinterPreferences(**{k: raw[k] for k in raw if k in {f.name for f in fields(PrinterPreferences)}})


def token_from_dict(raw: dict[str, Any]) -> TokenDefaults:
    return TokenDefaults(**{k: raw[k] for k in raw if k in {f.name for f in fields(TokenDefaults)}})


def filament_from_dict(raw: dict[str, Any]) -> FilamentColor:
    return FilamentColor(**{k: raw[k] for k in raw if k in {f.name for f in fields(FilamentColor)}})


def font_from_dict(raw: dict[str, Any]) -> FontReference:
    return FontReference(**{k: raw[k] for k in raw if k in {f.name for f in fields(FontReference)}})


def crop_from_dict(raw: dict[str, Any]) -> CropTransform:
    return CropTransform(**{k: raw[k] for k in raw if k in {f.name for f in fields(CropTransform)}})


def text_layout_from_dict(raw: dict[str, Any]) -> TextLayoutConfig:
    return TextLayoutConfig(**{k: raw[k] for k in raw if k in {f.name for f in fields(TextLayoutConfig)}})


def style_from_dict(raw: dict[str, Any]) -> StyleSettings:
    data = {k: raw[k] for k in raw if k in {f.name for f in fields(StyleSettings)}}
    if isinstance(data.get("title_text"), dict):
        data["title_text"] = text_layout_from_dict(data["title_text"])
    if isinstance(data.get("bottom_text"), dict):
        data["bottom_text"] = text_layout_from_dict(data["bottom_text"])
    return StyleSettings(**data)


def layer_band_from_dict(raw: dict[str, Any]) -> LayerBand:
    return LayerBand(**{k: raw[k] for k in raw if k in {f.name for f in fields(LayerBand)}})


def layer_plan_from_dict(raw: dict[str, Any]) -> LayerPlan:
    data = {k: raw[k] for k in raw if k in {f.name for f in fields(LayerPlan)}}
    if isinstance(data.get("color_layers"), list):
        data["color_layers"] = [layer_band_from_dict(item) for item in data["color_layers"]]
    return LayerPlan(**data)


def preferences_from_dict(raw: dict[str, Any]) -> Preferences:
    return Preferences(
        printer=printer_from_dict(raw.get("printer", {})),
        token_defaults=token_from_dict(raw.get("token_defaults", {})),
        style_defaults=style_from_dict(raw.get("style_defaults", {})),
        palette=[filament_from_dict(item) for item in raw.get("palette", [])],
        imported_fonts=[font_from_dict(item) for item in raw.get("imported_fonts", [])],
    )


def project_from_dict(raw: dict[str, Any]) -> ProjectState:
    return ProjectState(
        project_name=raw.get("project_name", "tokenforge-token"),
        source_image=raw.get("source_image"),
        crop_transform=crop_from_dict(raw.get("crop_transform", {})),
        printer_preferences=printer_from_dict(raw.get("printer_preferences", {})),
        token_defaults=token_from_dict(raw.get("token_defaults", {})),
        enabled_palette_colors=[filament_from_dict(item) for item in raw.get("enabled_palette_colors", [])],
        style_settings=style_from_dict(raw.get("style_settings", {})),
        imported_fonts=[font_from_dict(item) for item in raw.get("imported_fonts", [])],
        generated_layer_plan=layer_plan_from_dict(raw["generated_layer_plan"]) if raw.get("generated_layer_plan") else None,
    )
