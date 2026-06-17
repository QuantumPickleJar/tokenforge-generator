from __future__ import annotations

from PIL import Image, ImageDraw

import tokenforge_local.tf_app_handlers as handlers
from tokenforge_local.app_state import state
from tokenforge_local.models import CropTransform, FilamentColor, LayerColorStop, ProjectState, StyleSettings, TextLayoutConfig


class CaptureImageWidget:
    def __init__(self) -> None:
        self.source: str | None = None
        self.cleared = False

    def set_source(self, source: str) -> None:
        self.source = source

    def clear(self) -> None:
        self.cleared = True


def _source_image() -> Image.Image:
    image = Image.new("RGB", (48, 48), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 23, 47), fill=(20, 20, 20))
    draw.rectangle((24, 0, 47, 47), fill=(230, 230, 230))
    return image


def _project() -> ProjectState:
    style = StyleSettings(
        border_enabled=False,
        title_text=TextLayoutConfig(enabled=False),
        bottom_text=TextLayoutConfig(enabled=False),
    )
    return ProjectState(
        project_name="ui-preview-flow",
        crop_transform=CropTransform(output_width_px=48, output_height_px=48),
        enabled_palette_colors=[
            FilamentColor("Black", "#000000", True),
            FilamentColor("White", "#ffffff", True),
        ],
        style_settings=style,
        layer_color_stops=[
            LayerColorStop(1, "Black", "#000000"),
            LayerColorStop(4, "White", "#ffffff"),
        ],
    )


def test_confirm_crop_populates_styled_and_layer_span_preview_widgets(monkeypatch) -> None:
    saved = {
        "project": state.project,
        "source_image": state.source_image,
        "prepared_image": state.prepared_image,
        "styled_preview_widget": state.styled_preview_widget,
        "reduced_preview_widget": state.reduced_preview_widget,
        "layer_editor_container": state.layer_editor_container,
        "status": state.status,
    }
    styled = CaptureImageWidget()
    reduced = CaptureImageWidget()

    monkeypatch.setattr(handlers, "set_status", lambda *args, **kwargs: None)

    try:
        state.project = _project()
        state.source_image = _source_image()
        state.prepared_image = None
        state.styled_preview_widget = styled
        state.reduced_preview_widget = reduced
        state.layer_editor_container = None
        state.status = None

        handlers.confirm_crop()

        assert state.prepared_image is not None
        assert styled.source is not None and styled.source.startswith("data:image/png;base64,")
        assert reduced.source is not None and reduced.source.startswith("data:image/png;base64,")
    finally:
        state.project = saved["project"]
        state.source_image = saved["source_image"]
        state.prepared_image = saved["prepared_image"]
        state.styled_preview_widget = saved["styled_preview_widget"]
        state.reduced_preview_widget = saved["reduced_preview_widget"]
        state.layer_editor_container = saved["layer_editor_container"]
        state.status = saved["status"]
