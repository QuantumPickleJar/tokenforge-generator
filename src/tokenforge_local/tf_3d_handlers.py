from __future__ import annotations

from pathlib import Path
import inspect
import traceback

from .app_state import set_status, state
from .stl_viewer import render_model_viewer
from .three_d_preview import ThreeDPreviewResult, build_layer_color_3d_preview
from .utils import safe_project_name

try:
    from nicegui import events
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


def _upload_filename(e: events.UploadEventArguments) -> str:
    upload_file = getattr(e, "file", None)
    raw_name = (
        getattr(e, "name", None)
        or getattr(e, "filename", None)
        or getattr(upload_file, "filename", None)
        or getattr(upload_file, "name", None)
        or "uploaded-model.stl"
    )
    return Path(str(raw_name)).name or "uploaded-model.stl"


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
        with target.open("wb") as handle:
            handle.write(data)
        return True

    return False


def _target_for_upload(filename: str) -> Path:
    suffix = Path(filename).suffix.lower()
    project_name = safe_project_name(Path(filename).stem) or "uploaded-model"
    upload_dir = Path("outputs/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / f"{project_name}{suffix or '.stl'}"
    counter = 1
    while target.exists():
        target = upload_dir / f"{project_name}-{counter}{suffix or '.stl'}"
        counter += 1
    return target


def _apply_preview_result(result: ThreeDPreviewResult) -> None:
    state.three_d_model_name = result.model_name
    state.three_d_bounds_summary = result.dimensions_summary
    state.three_d_face_count = result.face_count
    state.three_d_vertex_count = result.vertex_count
    state.three_d_preview_path = result.preview_glb_path
    state.three_d_last_error = None

    if state.three_d_model_label:
        state.three_d_model_label.set_text(f"Model: {result.model_name}")
    if state.three_d_bounds_label:
        state.three_d_bounds_label.set_text(
            f"{result.dimensions_summary} · {result.vertex_count:,} vertices · {result.face_count:,} faces"
        )
    render_model_viewer(state.three_d_viewer_container, result.preview_glb_path)


def refresh_3d_preview() -> None:
    if state.three_d_source_path is None:
        set_status("Upload an STL in 3D mode before refreshing the layer-color preview.", negative=True)
        return

    try:
        result = build_layer_color_3d_preview(state.three_d_source_path, state.project)
        _apply_preview_result(result)
        set_status(
            "Layer color preview updated — estimated from model Z-height and selected filament changes.",
            notify=True,
        )
    except Exception as exc:
        state.three_d_last_error = str(exc)
        traceback.print_exc()
        if state.three_d_bounds_label:
            state.three_d_bounds_label.set_text(f"3D preview failed: {exc}")
        render_model_viewer(state.three_d_viewer_container, None)
        set_status(f"3D preview failed: {exc}", negative=True)


async def handle_3d_upload(e: events.UploadEventArguments) -> None:
    filename = _upload_filename(e)
    suffix = Path(filename).suffix.lower()
    if suffix == ".3mf":
        set_status("3MF support is coming later in v0.2. Upload an STL for the first 3D preview workflow.", negative=True)
        return
    if suffix != ".stl":
        set_status("Unsupported 3D model type. Upload an STL file for this v0.2 MVP.", negative=True)
        return

    target = _target_for_upload(filename)
    saved = await _save_upload(e, target)
    if not saved:
        set_status("STL upload failed: unsupported NiceGUI upload payload.", negative=True)
        return

    state.three_d_source_path = target
    state.three_d_model_name = target.name
    state.three_d_preview_path = None
    if state.three_d_model_label:
        state.three_d_model_label.set_text(f"Model: {target.name}")
    if state.three_d_bounds_label:
        state.three_d_bounds_label.set_text("Loading STL bounds and layer-color preview...")

    refresh_3d_preview()
