from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

try:
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("NiceGUI is not installed. Run `pip install -e .` or `pip install -r requirements.txt` first.") from exc


def output_static_url(path: Path | str) -> str:
    path = Path(path)
    outputs_root = Path("outputs").resolve()
    try:
        rel = path.resolve().relative_to(outputs_root)
    except ValueError:
        return ""
    return "/outputs/" + quote(str(rel).replace("\\", "/"))


def render_model_viewer(container, glb_path: Path | str | None, *, empty_message: str = "Generate a package to populate the 3D model viewer.") -> None:
    if container is None:
        return
    container.clear()
    with container:
        if glb_path is None:
            ui.label(empty_message).classes("text-sm text-gray-600")
            return

        path = Path(glb_path)
        if not path.exists():
            ui.label(f"3D viewer model was not found: {path}").classes("text-sm text-red-700")
            return

        url = output_static_url(path)
        if not url:
            ui.label(f"3D viewer model exists but is outside the served outputs folder: {path}").classes("text-sm text-red-700")
            return

        cache_buster = int(path.stat().st_mtime)
        model_url = f"{url}?v={cache_buster}"
        safe_path = escape(str(path))
        safe_url = escape(model_url, quote=True)
        ui.html(
            f"""
            <div style="width:100%; min-height:360px; border:1px solid #d0d0d0; border-radius:10px; overflow:hidden; background:#f7f7f7;">
              <model-viewer
                src="{safe_url}"
                camera-controls
                auto-rotate
                auto-rotate-delay="1200"
                rotation-per-second="18deg"
                shadow-intensity="0.65"
                exposure="1.0"
                ar="false"
                style="width:100%; height:360px; background:linear-gradient(180deg,#fafafa,#e8e8e8);">
                <div slot="poster" style="padding:16px; font-size:13px; color:#555;">Loading generated 3D preview...</div>
              </model-viewer>
            </div>
            <div style="font-size:12px; color:#555; margin-top:4px;">
              Viewer artifact: <code>{safe_path}</code><br>
              If the viewer stays blank, open the GLB from the print package; the STL was still generated normally.
            </div>
            """
        )
