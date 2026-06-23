"""UI-safe AI candidate lifecycle; no model inference runs in this process."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from PIL import Image

from .ai_comfyui import ComfyUIBackend
from .ai_composition import apply_protected_overlay
from .ai_models import AIBackendError, AIEditRequest, AIImageBackend
from .app_state import mark_dirty, set_status, state
from .image_editor import default_crop_transform
from .tf_layer_ui import refresh_layer_controls
from .tf_preview_helpers import refresh_crop_preview, refresh_visual_previews
from .utils import image_to_data_url, safe_project_name


MAX_AI_HISTORY = 5


def _set_ai_status(message: str, *, error: bool = False) -> None:
    state.ai_status = message
    state.ai_last_error = message if error else None
    if state.ai_status_label is not None:
        state.ai_status_label.set_text(message)


def make_ai_backend() -> AIImageBackend:
    if state.ai_backend != "comfyui":
        raise AIBackendError(f"Unsupported local AI backend: {state.ai_backend}")
    return ComfyUIBackend(state.ai_endpoint, state.ai_workflow_path or None)


def selected_ai_source() -> Image.Image | None:
    if state.ai_iteration_source == "candidate" and state.ai_candidate_image is not None:
        return state.ai_candidate_image.copy()
    if state.prepared_image is not None:
        return state.prepared_image.copy()
    if state.source_image is not None:
        return state.source_image.copy()
    return None


def _save_ai_input(image: Image.Image) -> Path:
    directory = Path("outputs/ai_candidates")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"{safe_project_name(state.project.project_name) or 'tokenforge'}-ai-input-{stamp}.png"
    image.convert("RGB").save(path)
    return path


def _save_candidate(image: Image.Image) -> Path:
    directory = Path("outputs/ai_candidates")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"{safe_project_name(state.project.project_name) or 'tokenforge'}-ai-candidate-{stamp}.png"
    image.convert("RGB").save(path)
    return path


def _show_candidate() -> None:
    if state.ai_candidate_preview_widget is not None:
        state.ai_candidate_preview_widget.set_source(image_to_data_url(state.ai_candidate_image) if state.ai_candidate_image is not None else "")


async def check_ai_backend() -> bool:
    try:
        message = await asyncio.to_thread(make_ai_backend().test_connection)
        _set_ai_status(message)
        return True
    except AIBackendError as exc:
        _set_ai_status(str(exc), error=True)
        set_status(f"AI Assist: {exc}", negative=True)
        return False


async def generate_ai_candidate() -> None:
    if not state.ai_enabled:
        _set_ai_status("Enable AI Assist from View before generating an edit.", error=True)
        return
    if state.ai_job_running:
        _set_ai_status("An AI edit is already running.", error=True)
        return
    prompt = state.ai_prompt.strip()
    if not prompt:
        _set_ai_status("Enter an edit prompt before generating.", error=True)
        return
    source = selected_ai_source()
    if source is None:
        _set_ai_status("Upload and prepare an image before requesting an AI edit.", error=True)
        return
    state.ai_job_running = True
    _set_ai_status(f"Submitting {state.ai_iteration_source} image to local ComfyUI…")
    try:
        source_path = _save_ai_input(source)
        result = await asyncio.to_thread(
            make_ai_backend().edit_image,
            AIEditRequest(source_path, prompt, state.ai_negative_prompt, state.ai_preset),
        )
        candidate = result.image
        if state.ai_protect_text_qr:
            candidate = apply_protected_overlay(candidate, state.ai_protected_overlay)
        if state.ai_candidate_image is not None:
            state.ai_previous_candidate_image = state.ai_candidate_image.copy()
        state.ai_candidate_image = candidate
        state.ai_candidate_path = _save_candidate(candidate)
        state.ai_candidate_history.append(state.ai_candidate_path)
        state.ai_candidate_history[:] = state.ai_candidate_history[-MAX_AI_HISTORY:]
        state.ai_prompt_history.append(prompt)
        state.ai_prompt_history[:] = state.ai_prompt_history[-MAX_AI_HISTORY:]
        protected = " Protected overlay reapplied." if state.ai_protected_overlay is not None and state.ai_protect_text_qr else ""
        if state.ai_protect_text_qr and state.ai_protected_overlay is None:
            protected += " No text/QR overlay is currently available; this is safe in IMG mode."
        _set_ai_status(f"Candidate ready. Review it before committing it to Tokenforge.{protected}")
        _show_candidate()
    except AIBackendError as exc:
        _set_ai_status(str(exc), error=True)
        set_status(f"AI edit failed safely: {exc}", negative=True)
    except Exception as exc:  # pragma: no cover - defensive UI boundary
        _set_ai_status(f"AI edit failed safely: {exc}", error=True)
        set_status(f"AI edit failed safely: {exc}", negative=True)
    finally:
        state.ai_job_running = False


def accept_ai_candidate() -> bool:
    if state.ai_candidate_image is None:
        _set_ai_status("There is no AI candidate to accept.", error=True)
        return False
    accepted = state.ai_candidate_image.convert("RGB").copy()
    state.source_image = accepted.copy()
    state.source_path = state.ai_candidate_path
    state.project.source_image = str(state.ai_candidate_path) if state.ai_candidate_path else state.project.source_image
    state.project.crop_transform = default_crop_transform(state.project.source_image, state.project.token_defaults)
    state.prepared_image = accepted
    state.ai_candidate_image = None
    state.ai_candidate_path = None
    mark_dirty()
    refresh_layer_controls()
    refresh_crop_preview()
    refresh_visual_previews()
    _show_candidate()
    _set_ai_status("Accepted: the candidate is now the working image. The original upload remains in this session.")
    set_status("AI candidate accepted into the IMG workflow. Previews refreshed.")
    return True


def reject_ai_candidate() -> bool:
    if state.ai_candidate_image is None:
        _set_ai_status("There is no AI candidate to reject.", error=True)
        return False
    state.ai_previous_candidate_image = state.ai_candidate_image.copy()
    state.ai_candidate_image = None
    state.ai_candidate_path = None
    _show_candidate()
    _set_ai_status("Rejected: the candidate was discarded; the current Tokenforge image is unchanged.")
    set_status("AI candidate rejected. Current working image was preserved.")
    return True


def reset_ai_session_for_upload() -> None:
    state.ai_original_image = state.source_image.copy() if state.source_image is not None else None
    state.ai_original_path = state.source_path
    state.ai_candidate_image = None
    state.ai_candidate_path = None
    state.ai_previous_candidate_image = None
    state.ai_prompt_history.clear()
    state.ai_candidate_history.clear()
    state.ai_iteration_source = "current"
    state.ai_protected_overlay = None
    _set_ai_status("AI session ready. AI edits are optional and non-destructive until accepted.")
