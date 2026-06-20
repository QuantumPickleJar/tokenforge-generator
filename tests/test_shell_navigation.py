from __future__ import annotations

from tokenforge_local import shell
from tokenforge_local.app_state import state


def test_shell_mode_constants_make_img_default_and_card_3d_visible() -> None:
    assert shell.APP_BRAND == "Tokenforge"
    assert shell.APP_VERSION.startswith("0.2")
    assert shell.DEFAULT_MODE == shell.MODE_IMG
    assert shell.MODE_OPTIONS == ["IMG", "CARD", "3D"]


def test_card_mode_is_business_card_flat_relief_workflow() -> None:
    assert shell.MODE_CARD == "CARD"
    assert "Business Card / Flat Relief" in shell.CARD_WORKFLOW_TEXT
    assert "Fabric.js or Konva.js" in shell.CARD_EDITOR_PLACEHOLDER


def test_3d_mode_is_real_stl_workflow_for_v02() -> None:
    assert "STL layer-color preview" in shell.THREE_D_WORKFLOW_TEXT
    assert "3MF support" in shell.THREE_D_WORKFLOW_TEXT
    assert "estimated from model Z-height" in shell.THREE_D_PREVIEW_LABEL


def test_app_state_tracks_img_mode_by_default() -> None:
    assert state.ui_mode == "IMG"
