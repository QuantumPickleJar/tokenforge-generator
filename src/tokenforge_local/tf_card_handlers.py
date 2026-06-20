from __future__ import annotations

from pathlib import Path
import asyncio
import inspect
import traceback

from .app_state import set_status, state
from .business_card import (
    BusinessCardArtifacts,
    build_card_preview_image,
    detect_qr_content,
    generate_business_card_artifacts,
    generate_qr_preview,
    qr_feature_warnings,
)
from .stl_viewer import render_model_viewer
from .utils import ensure_rgb, image_to_data_url, safe_project_name

try:
    from nicegui import events
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc

from PIL import Image


def _upload_filename(e: events.UploadEventArguments) -> str:
    upload_file = getattr(e, "file", None)
    raw_name = (
        getattr(e, "name", None)
        or getattr(e, "filename", None)
        or getattr(upload_file, "filename", None)
        or getattr(upload_file, "name", None)
        or "business-card.png"
    )
    return Path(str(raw_name)).name or "business-card.png"


async def _save_upload(e: events.UploadEventArguments, target: Path) -> bool:
    upload_file = getattr(e, "file", None)
    if upload_file is not None and hasattr(upload_file, "save"):
        saved = upload_file.save(target)
        if inspect.isawaitable(saved):
            await saved
        return True

    if hasattr(e, "content"):
        content = e.content
        data = content.read() if hasattr(content, "read") else content
        if inspect.isawaitable(data):
            data = await data
        if isinstance(data, str):
            data = data.encode()
        target.write_bytes(data)
        return True

    return False


def _target_for_upload(filename: str) -> Path:
    suffix = Path(filename).suffix.lower()
    project_name = safe_project_name(Path(filename).stem) or "business-card"
    upload_dir = Path("outputs/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{project_name}{suffix or '.png'}"
    counter = 1
    while target.exists():
        target = upload_dir / f"{project_name}-{counter}{suffix or '.png'}"
        counter += 1
    return target


def _update_card_warnings(content: str | None = None) -> None:
    content = content if content is not None else state.card_qr_content
    if not state.card_feature_warning_label:
        return
    if not content:
        state.card_feature_warning_label.set_text("QR feature warning: enter or detect QR content to estimate module size.")
        return
    try:
        warnings = qr_feature_warnings(content, state.card_settings, state.project)
        state.card_feature_warning_label.set_text("QR / print warnings: " + " | ".join(warnings))
    except Exception as exc:
        state.card_feature_warning_label.set_text(f"QR feature warning unavailable: {exc}")


def refresh_card_qr_preview() -> None:
    content = (state.card_qr_content or "").strip()
    if not content:
        if state.card_qr_preview_widget:
            state.card_qr_preview_widget.set_source("")
        if state.card_qr_validation_label:
            state.card_qr_validation_label.set_text("QR validation: enter content or detect a QR code.")
        _update_card_warnings(None)
        return

    try:
        preview = generate_qr_preview(content, state.card_settings, state.project)
        if state.card_qr_preview_widget:
            state.card_qr_preview_widget.set_source(image_to_data_url(preview.image))
        if state.card_qr_validation_label:
            if preview.decoded_content == content:
                state.card_qr_validation_label.set_text(
                    f"QR validation: generated preview decodes successfully. Module size ≈ {preview.module_size_mm:.2f} mm."
                )
            else:
                state.card_qr_validation_label.set_text("QR validation: generated QR did not decode to the exact supplied content. Verify before printing.")
        _update_card_warnings(content)
    except Exception as exc:
        if state.card_qr_validation_label:
            state.card_qr_validation_label.set_text(f"QR validation failed safely: {exc}")
        _update_card_warnings(content)


def detect_card_qr() -> None:
    if state.card_source_image is None:
        set_status("Upload a business card image before detecting QR.", negative=True)
        return
    result = detect_qr_content(state.card_source_image)
    if state.card_qr_label:
        state.card_qr_label.set_text(result.message)
    if result.found and result.content:
        state.card_qr_content = result.content
        if state.card_qr_input:
            state.card_qr_input.value = result.content
        refresh_card_qr_preview()
        set_status("QR detected. Confirm the decoded value before generating relief output.", notify=True)
    else:
        set_status(result.message, negative=False)


async def handle_card_upload(e: events.UploadEventArguments) -> None:
    filename = _upload_filename(e)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        set_status("Unsupported card image type. Upload PNG, JPG, JPEG, or WebP.", negative=True)
        return

    target = _target_for_upload(filename)
    saved = await _save_upload(e, target)
    if not saved:
        set_status("Business card upload failed: unsupported NiceGUI upload payload.", negative=True)
        return

    try:
        image = ensure_rgb(Image.open(target))
    except Exception as exc:
        set_status(f"Could not open uploaded business card image: {exc}", negative=True)
        return

    state.card_source_path = target
    state.card_source_image = image
    state.card_output_preview_path = None
    state.card_stl_path = None
    state.card_glb_path = None
    if state.card_source_preview_widget:
        state.card_source_preview_widget.set_source(image_to_data_url(image))

    detection = detect_qr_content(image)
    if state.card_qr_label:
        state.card_qr_label.set_text(detection.message)
    if detection.found and detection.content:
        state.card_qr_content = detection.content
        if state.card_qr_input:
            state.card_qr_input.value = detection.content
        refresh_card_qr_preview()
        set_status("Business card image loaded and QR decoded. Confirm the value before generating output.", notify=True)
    else:
        refresh_card_qr_preview()
        set_status("Business card image loaded. QR was not detected; enter QR content manually if needed.", notify=True)


def refresh_card_layout_preview() -> None:
    content = (state.card_qr_content or "").strip()
    if not content:
        set_status("Enter QR content before refreshing the card layout preview.", negative=True)
        return
    try:
        preview = build_card_preview_image(content, state.card_settings, state.project)
        if state.card_output_preview_widget:
            state.card_output_preview_widget.set_source(image_to_data_url(preview))
        refresh_card_qr_preview()
        set_status("Business card relief preview refreshed.", notify=False)
    except Exception as exc:
        set_status(f"Business card preview failed: {exc}", negative=True)


def _apply_card_artifacts(artifacts: BusinessCardArtifacts) -> None:
    state.card_stl_path = artifacts.stl_path
    state.card_glb_path = artifacts.glb_path
    state.card_output_preview_path = artifacts.preview_path
    if state.card_output_preview_widget and artifacts.preview_path.exists():
        state.card_output_preview_widget.set_source(image_to_data_url(Image.open(artifacts.preview_path)))
    if state.card_output_label:
        state.card_output_label.set_text(
            f"Generated STL: {artifacts.stl_path} · GLB preview: {artifacts.glb_path} · QR module ≈ {artifacts.module_size_mm:.2f} mm"
        )
    if state.card_feature_warning_label:
        state.card_feature_warning_label.set_text("QR / print warnings: " + " | ".join(artifacts.warnings))
    render_model_viewer(state.card_viewer_container, artifacts.glb_path, empty_message="Generate card relief output to populate the 3D preview.")


async def generate_card_output() -> None:
    content = (state.card_qr_content or "").strip()
    if not content:
        set_status("Enter or detect QR content before generating a business card relief STL.", negative=True)
        return

    project_name = "business-card"
    if state.card_source_path:
        project_name = safe_project_name(state.card_source_path.stem)
    set_status("Generating business card relief STL/GLB preview...", notify=True)
    try:
        artifacts = await asyncio.to_thread(
            generate_business_card_artifacts,
            content,
            state.card_settings,
            state.project,
            Path("outputs/business-cards"),
            project_name,
        )
        _apply_card_artifacts(artifacts)
        set_status("Business card relief STL and browser preview generated.", notify=True)
    except Exception as exc:
        traceback.print_exc()
        if state.card_output_label:
            state.card_output_label.set_text(f"Business card generation failed: {exc}")
        render_model_viewer(state.card_viewer_container, None, empty_message="Fix the card settings or QR content, then generate again.")
        set_status(f"Business card generation failed: {exc}", negative=True)
