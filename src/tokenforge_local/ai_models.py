"""Small, backend-neutral contracts for optional local AI image editing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image


class AIBackendError(RuntimeError):
    """An expected local-backend failure that is safe to present in the UI."""


@dataclass(frozen=True)
class AIEditRequest:
    image_path: Path
    prompt: str
    negative_prompt: str = ""
    preset: str = "Cleanup"
    mask_path: Path | None = None


@dataclass(frozen=True)
class AIEditResult:
    image: Image.Image
    backend_image_name: str | None = None


class AIImageBackend(Protocol):
    endpoint: str

    def test_connection(self) -> str: ...

    def edit_image(self, request: AIEditRequest) -> AIEditResult: ...
