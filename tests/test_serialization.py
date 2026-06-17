from tokenforge_local.models import CropTransform, StyleSettings, TextLayoutConfig, crop_from_dict, dataclass_to_dict, style_from_dict, text_layout_from_dict
from tokenforge_local.style_presets import StylePreset


def test_crop_transform_metadata_serialization():
    transform = CropTransform(source_image="source.png", pan_x_px=12.5, scale=1.4, rotation_degrees=90)
    loaded = crop_from_dict(dataclass_to_dict(transform))
    assert loaded.source_image == "source.png"
    assert loaded.pan_x_px == 12.5
    assert loaded.scale == 1.4
    assert loaded.rotation_degrees == 90


def test_style_preset_serialization_deserialization():
    preset = StylePreset("wood_frame", "Wood frame", "Material Themes", notes="implemented")
    loaded = StylePreset.from_dict(preset.to_dict())
    assert loaded == preset


def test_text_layout_configuration_serialization():
    config = TextLayoutConfig(enabled=True, content="Goblin", size_px=36, uppercase=True, emboss_mode="engrave")
    loaded = text_layout_from_dict(dataclass_to_dict(config))
    assert loaded.enabled is True
    assert loaded.content == "Goblin"
    assert loaded.uppercase is True
    assert loaded.emboss_mode == "engrave"


def test_style_settings_round_trip():
    style = StyleSettings(border_style="riveted_metal")
    style.title_text.content = "Knight"
    loaded = style_from_dict(dataclass_to_dict(style))
    assert loaded.border_style == "riveted_metal"
    assert loaded.title_text.content == "Knight"
