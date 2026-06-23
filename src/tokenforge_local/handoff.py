from __future__ import annotations

"""Portfolio-gallery handoff parsing and Printdesk request construction.

This module deliberately has no NiceGUI dependency so handoffs can be validated
before they touch app state and the request format remains easy to test or reuse.
"""

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .models import ProjectState, dataclass_to_dict


HANDOFF_SCHEMA = "tokenforge.handoff.v1"
PRINT_REQUEST_SCHEMA = "printdesk.request.v1"
_MAX_HANDOFF_BYTES = 96_000
_BASE64URL_PATTERN = re.compile(r"[A-Za-z0-9_-]*={0,2}\Z")


@dataclass(frozen=True, slots=True)
class HandoffItem:
    id: str = ""
    name: str = ""
    description: str = ""
    gallery_url: str = ""
    image_url: str = ""
    model_url: str = ""
    preview_url: str = ""


@dataclass(frozen=True, slots=True)
class HandoffPrint:
    category: str = ""
    material: str = ""
    nozzle_mm: float | None = None
    layer_height_mm: float | None = None
    colors: tuple[str, ...] = ()
    estimated_grams: float | None = None
    estimated_time_minutes: float | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class HandoffGenerator:
    mode: str = "IMG"
    project_name: str = ""
    allow_customization: bool = True


@dataclass(frozen=True, slots=True)
class TokenforgeHandoff:
    schema: str
    source: str
    intent: str
    item: HandoffItem = field(default_factory=HandoffItem)
    print: HandoffPrint = field(default_factory=HandoffPrint)
    generator: HandoffGenerator = field(default_factory=HandoffGenerator)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source": self.source,
            "intent": self.intent,
            "item": {
                "id": self.item.id,
                "name": self.item.name,
                "description": self.item.description,
                "galleryUrl": self.item.gallery_url,
                "imageUrl": self.item.image_url,
                "modelUrl": self.item.model_url,
                "previewUrl": self.item.preview_url,
            },
            "print": {
                "category": self.print.category,
                "material": self.print.material,
                "nozzleMm": self.print.nozzle_mm,
                "layerHeightMm": self.print.layer_height_mm,
                "colors": list(self.print.colors),
                "estimatedGrams": self.print.estimated_grams,
                "estimatedTimeMinutes": self.print.estimated_time_minutes,
                "notes": self.print.notes,
            },
            "generator": {
                "mode": self.generator.mode,
                "projectName": self.generator.project_name,
                "allowCustomization": self.generator.allow_customization,
            },
        }


@dataclass(frozen=True, slots=True)
class HandoffDecodeResult:
    handoff: TokenforgeHandoff | None = None
    error: str | None = None


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object.")
    return value


def _string(value: Mapping[str, Any], name: str, *, default: str = "") -> str:
    result = value.get(name, default)
    if result is None:
        return default
    if not isinstance(result, str):
        raise ValueError(f"{name} must be a string.")
    return result


def _number_or_none(value: Mapping[str, Any], name: str) -> float | None:
    result = value.get(name)
    if result is None:
        return None
    if isinstance(result, bool) or not isinstance(result, (int, float)):
        raise ValueError(f"{name} must be a number or null.")
    return float(result)


def _string_list(value: Mapping[str, Any], name: str) -> tuple[str, ...]:
    result = value.get(name, [])
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise ValueError(f"{name} must be a list of strings.")
    return tuple(result)


def handoff_from_dict(raw: Mapping[str, Any]) -> TokenforgeHandoff:
    """Validate a decoded handoff object and return its typed representation."""
    schema = _string(raw, "schema")
    if schema != HANDOFF_SCHEMA:
        raise ValueError(f"Unsupported handoff schema. Expected {HANDOFF_SCHEMA}.")

    item_raw = _object(raw.get("item", {}), "item")
    print_raw = _object(raw.get("print", {}), "print")
    generator_raw = _object(raw.get("generator", {}), "generator")
    allow_customization = generator_raw.get("allowCustomization", True)
    if not isinstance(allow_customization, bool):
        raise ValueError("allowCustomization must be true or false.")

    return TokenforgeHandoff(
        schema=schema,
        source=_string(raw, "source"),
        intent=_string(raw, "intent"),
        item=HandoffItem(
            id=_string(item_raw, "id"),
            name=_string(item_raw, "name"),
            description=_string(item_raw, "description"),
            gallery_url=_string(item_raw, "galleryUrl"),
            image_url=_string(item_raw, "imageUrl"),
            model_url=_string(item_raw, "modelUrl"),
            preview_url=_string(item_raw, "previewUrl"),
        ),
        print=HandoffPrint(
            category=_string(print_raw, "category"),
            material=_string(print_raw, "material"),
            nozzle_mm=_number_or_none(print_raw, "nozzleMm"),
            layer_height_mm=_number_or_none(print_raw, "layerHeightMm"),
            colors=_string_list(print_raw, "colors"),
            estimated_grams=_number_or_none(print_raw, "estimatedGrams"),
            estimated_time_minutes=_number_or_none(print_raw, "estimatedTimeMinutes"),
            notes=_string(print_raw, "notes"),
        ),
        generator=HandoffGenerator(
            mode=_string(generator_raw, "mode", default="IMG"),
            project_name=_string(generator_raw, "projectName"),
            allow_customization=allow_customization,
        ),
    )


def decode_handoff_param(encoded: str | None) -> HandoffDecodeResult:
    """Safely decode a URL-safe base64 JSON query value without raising to callers."""
    if not encoded:
        return HandoffDecodeResult()
    if not isinstance(encoded, str) or len(encoded) > _MAX_HANDOFF_BYTES:
        return HandoffDecodeResult(error="The gallery handoff is missing or too large to open safely.")
    normalized = encoded.strip()
    if not normalized or not _BASE64URL_PATTERN.fullmatch(normalized):
        return HandoffDecodeResult(error="The gallery handoff is not valid URL-safe base64 data.")
    try:
        padded = normalized + "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        raw = json.loads(decoded.decode("utf-8"))
        return HandoffDecodeResult(handoff=handoff_from_dict(_object(raw, "handoff")))
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError, ValueError) as exc:
        return HandoffDecodeResult(error=f"The gallery handoff could not be used: {exc}")


def is_safe_external_url(value: str) -> bool:
    """Only turn http(s) URLs into clickable links; all other values remain text."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _path_map(paths: Mapping[str, Path | str | None] | None) -> dict[str, str]:
    if not paths:
        return {}
    return {str(name): str(path) for name, path in paths.items() if path is not None}


def build_print_request(
    handoff: TokenforgeHandoff,
    project: ProjectState,
    *,
    mode: str,
    package_paths: Mapping[str, Path | str | None] | None = None,
    workflow_paths: Mapping[str, Path | str | None] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Create the MVP JSON document consumed by a future Printdesk integration."""
    return {
        "schema": PRINT_REQUEST_SCHEMA,
        "intent": handoff.intent or "request-print",
        "sourceHandoff": handoff.to_dict(),
        "tokenforge": {
            "mode": mode,
            "projectMetadata": dataclass_to_dict(project),
            "generatedPackagePaths": _path_map(package_paths),
            "workflowPaths": _path_map(workflow_paths),
        },
        "print": {
            "requested": handoff.to_dict()["print"],
            "notes": notes,
        },
    }


def serialize_print_request(request: Mapping[str, Any]) -> str:
    return json.dumps(request, indent=2, sort_keys=True) + "\n"
