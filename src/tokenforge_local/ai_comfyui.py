"""A dependency-free ComfyUI HTTP client for locally hosted image edit workflows.

The workflow is intentionally supplied as JSON rather than embedded in Tokenforge:
ComfyUI installations differ in node IDs, checkpoints, and custom nodes. Templates
may use ``{{input_image}}``, ``{{prompt}}``, ``{{negative_prompt}}``,
``{{preset}}``, and ``{{mask_image}}`` anywhere in their JSON values.
"""

from __future__ import annotations

import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

from .ai_models import AIBackendError, AIEditRequest, AIEditResult


def _replace_tokens(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for token, replacement in replacements.items():
            value = value.replace("{{" + token + "}}", replacement)
        return value
    if isinstance(value, list):
        return [_replace_tokens(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_tokens(item, replacements) for key, item in value.items()}
    return value


class ComfyUIBackend:
    def __init__(self, endpoint: str = "http://127.0.0.1:8188", workflow_path: str | Path | None = None, *, timeout_s: float = 120.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.workflow_path = Path(workflow_path) if workflow_path else None
        self.timeout_s = timeout_s

    def _request(self, path: str, *, data: bytes | None = None, headers: dict[str, str] | None = None, timeout_s: float = 10.0) -> bytes:
        request = Request(f"{self.endpoint}{path}", data=data, headers=headers or {}, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=timeout_s) as response:  # nosec B310 - endpoint is user-selected local ComfyUI
                return response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise AIBackendError(f"ComfyUI returned HTTP {exc.code}: {body or exc.reason}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise AIBackendError(f"ComfyUI is unreachable at {self.endpoint}: {exc}") from exc

    def test_connection(self) -> str:
        try:
            payload = json.loads(self._request("/system_stats").decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AIBackendError("ComfyUI returned an unexpected status response.") from exc
        device = payload.get("devices", [{}])[0].get("name") if isinstance(payload, dict) else None
        return f"Connected to ComfyUI{f' ({device})' if device else ''}."

    def _upload_image(self, path: Path, field_name: str = "image") -> str:
        if not path.exists():
            raise AIBackendError(f"AI input image was not found: {path}")
        boundary = f"----Tokenforge{uuid.uuid4().hex}"
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = b"".join((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode(),
        ))
        raw = self._request("/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            result = json.loads(raw.decode("utf-8"))
            name = result.get("name")
        except (json.JSONDecodeError, AttributeError) as exc:
            raise AIBackendError("ComfyUI returned an unexpected image-upload response.") from exc
        if not name:
            raise AIBackendError("ComfyUI did not return an uploaded image name.")
        return str(name)

    def _workflow(self, request: AIEditRequest, input_name: str, mask_name: str = "") -> dict[str, Any]:
        if self.workflow_path is None:
            raise AIBackendError("No ComfyUI workflow template is configured. Set a workflow JSON path in AI Backend Settings.")
        try:
            template = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AIBackendError(f"Could not read ComfyUI workflow template: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIBackendError(f"ComfyUI workflow template is invalid JSON: {exc}") from exc
        if not isinstance(template, dict):
            raise AIBackendError("ComfyUI workflow template must be a JSON object.")
        return _replace_tokens(template, {"input_image": input_name, "prompt": request.prompt, "negative_prompt": request.negative_prompt, "preset": request.preset, "mask_image": mask_name})

    def edit_image(self, request: AIEditRequest) -> AIEditResult:
        input_name = self._upload_image(request.image_path)
        mask_name = self._upload_image(request.mask_path, "image") if request.mask_path else ""
        workflow = self._workflow(request, input_name, mask_name)
        raw = self._request("/prompt", data=json.dumps({"prompt": workflow, "client_id": f"tokenforge-{uuid.uuid4()}"}).encode(), headers={"Content-Type": "application/json"})
        try:
            prompt_id = json.loads(raw.decode("utf-8")).get("prompt_id")
        except (json.JSONDecodeError, AttributeError) as exc:
            raise AIBackendError("ComfyUI returned an unexpected workflow-submission response.") from exc
        if not prompt_id:
            raise AIBackendError("ComfyUI did not return a prompt id for the edit job.")

        deadline = time.monotonic() + self.timeout_s
        history: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            raw = self._request(f"/history/{prompt_id}")
            try:
                response = json.loads(raw.decode("utf-8"))
                history = response.get(prompt_id) if isinstance(response, dict) else None
            except json.JSONDecodeError as exc:
                raise AIBackendError("ComfyUI returned an unexpected job-status response.") from exc
            if history and history.get("outputs"):
                break
            time.sleep(0.5)
        if not history or not history.get("outputs"):
            raise AIBackendError("ComfyUI edit job timed out before producing an output image.")

        image_meta: dict[str, Any] | None = None
        for node_output in history["outputs"].values():
            images = node_output.get("images", []) if isinstance(node_output, dict) else []
            if images:
                image_meta = images[0]
        if not image_meta or not image_meta.get("filename"):
            raise AIBackendError("ComfyUI completed the job but returned no output image.")
        query = urlencode({"filename": image_meta["filename"], "subfolder": image_meta.get("subfolder", ""), "type": image_meta.get("type", "output")})
        output = self._request(f"/view?{query}", timeout_s=30.0)
        try:
            from io import BytesIO
            with Image.open(BytesIO(output)) as image:
                return AIEditResult(image=image.convert("RGB").copy(), backend_image_name=str(image_meta["filename"]))
        except Exception as exc:
            raise AIBackendError(f"ComfyUI output image could not be decoded: {exc}") from exc
