from __future__ import annotations

from tokenforge_local import shell
from tokenforge_local.app_state import state


def test_shell_mode_constants_make_img_default_and_3d_visible() -> None:
    assert shell.APP_BRAND == "Tokenforge"
    assert shell.DEFAULT_MODE == shell.MODE_IMG
    assert shell.MODE_OPTIONS == ["IMG", "3D"]


def test_3d_mode_is_placeholder_gated_for_v01x() -> None:
    text = shell.THREE_D_PLACEHOLDER_TEXT

    assert "planned for v0.2" in text
    assert "STL/3MF" in text
    assert "layer-color preview" in text


def test_app_state_tracks_img_mode_by_default() -> None:
    assert state.ui_mode == "IMG"


def test_img_workflow_uses_responsive_grid_instead_of_half_width_flex_row() -> None:
    layout = shell.IMG_WORKFLOW_LAYOUT_CLASSES

    assert "grid" in layout
    assert "grid-cols-1" in layout
    assert "lg:grid-cols-2" in layout
    assert "lg:w-1/2" not in shell.IMG_WORKFLOW_EDITOR_CLASSES
    assert "lg:w-1/2" not in shell.IMG_WORKFLOW_PREVIEW_CLASSES
