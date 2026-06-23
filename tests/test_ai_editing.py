from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

from PIL import Image

from tokenforge_local.ai_comfyui import ComfyUIBackend
from tokenforge_local.ai_composition import apply_protected_overlay
from tokenforge_local.ai_models import AIBackendError
from tokenforge_local.app_state import state
import tokenforge_local.tf_ai_handlers as handlers


def _image(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (12, 10), color)


def test_shell_state_exposes_local_ai_defaults() -> None:
    assert state.ai_backend == "comfyui"
    assert state.ai_endpoint == "http://127.0.0.1:8188"
    assert isinstance(state.ai_enabled, bool)


def test_selected_iteration_source_prefers_candidate_when_requested() -> None:
    saved = state.prepared_image, state.source_image, state.ai_candidate_image, state.ai_iteration_source
    try:
        state.prepared_image = _image((10, 20, 30))
        state.source_image = _image((40, 50, 60))
        state.ai_candidate_image = _image((70, 80, 90))
        state.ai_iteration_source = "current"
        assert handlers.selected_ai_source().getpixel((0, 0)) == (10, 20, 30)
        state.ai_iteration_source = "candidate"
        assert handlers.selected_ai_source().getpixel((0, 0)) == (70, 80, 90)
    finally:
        state.prepared_image, state.source_image, state.ai_candidate_image, state.ai_iteration_source = saved


def test_reject_preserves_working_image(monkeypatch) -> None:
    saved = state.prepared_image, state.ai_candidate_image, state.ai_candidate_path
    monkeypatch.setattr(handlers, "set_status", lambda *args, **kwargs: None)
    try:
        state.prepared_image = _image((1, 2, 3))
        state.ai_candidate_image = _image((9, 8, 7))
        state.ai_candidate_path = Path("candidate.png")
        assert handlers.reject_ai_candidate()
        assert state.prepared_image.getpixel((0, 0)) == (1, 2, 3)
        assert state.ai_candidate_image is None
    finally:
        state.prepared_image, state.ai_candidate_image, state.ai_candidate_path = saved


def test_accept_replaces_working_image(monkeypatch) -> None:
    saved = state.source_image, state.prepared_image, state.source_path, state.ai_candidate_image, state.ai_candidate_path, state.project.source_image
    monkeypatch.setattr(handlers, "set_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(handlers, "refresh_layer_controls", lambda: None)
    monkeypatch.setattr(handlers, "refresh_crop_preview", lambda: None)
    monkeypatch.setattr(handlers, "refresh_visual_previews", lambda: None)
    try:
        state.source_image = _image((1, 2, 3))
        state.prepared_image = _image((1, 2, 3))
        state.ai_candidate_image = _image((9, 8, 7))
        state.ai_candidate_path = Path("candidate.png")
        assert handlers.accept_ai_candidate()
        assert state.prepared_image.getpixel((0, 0)) == (9, 8, 7)
        assert state.source_image.getpixel((0, 0)) == (9, 8, 7)
        assert state.ai_candidate_image is None
    finally:
        state.source_image, state.prepared_image, state.source_path, state.ai_candidate_image, state.ai_candidate_path, state.project.source_image = saved


def test_protected_rgba_overlay_is_reapplied() -> None:
    base = _image((20, 30, 40))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.putpixel((4, 3), (255, 0, 0, 255))
    result = apply_protected_overlay(base, overlay)
    assert result.getpixel((4, 3)) == (255, 0, 0)
    assert result.getpixel((0, 0)) == (20, 30, 40)


def test_backend_unavailable_is_a_clear_safe_error(monkeypatch) -> None:
    backend = ComfyUIBackend("http://127.0.0.1:9")
    monkeypatch.setattr("tokenforge_local.ai_comfyui.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(URLError("refused")))
    try:
        backend.test_connection()
    except AIBackendError as exc:
        assert "unreachable" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing ComfyUI must fail gracefully")
