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
