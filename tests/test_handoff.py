import base64
import json

from tokenforge_local.handoff import (
    HANDOFF_SCHEMA,
    PRINT_REQUEST_SCHEMA,
    build_print_request,
    decode_handoff_param,
    serialize_print_request,
)
from tokenforge_local.models import FilamentColor, ProjectState


def _encoded_handoff(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")


def _payload() -> dict:
    return {
        "schema": HANDOFF_SCHEMA,
        "source": "portfolio-gallery",
        "intent": "request-print",
        "item": {
            "id": "dragon-01",
            "name": "Pocket Dragon",
            "description": "A small dragon token.",
            "galleryUrl": "https://gallery.example/items/dragon-01",
            "imageUrl": "https://gallery.example/dragon.png",
            "modelUrl": "https://gallery.example/dragon.stl",
            "previewUrl": "https://gallery.example/dragon-preview.png",
        },
        "print": {
            "category": "token",
            "material": "PLA",
            "nozzleMm": 0.4,
            "layerHeightMm": 0.2,
            "colors": ["Black", "Gold"],
            "estimatedGrams": 14,
            "estimatedTimeMinutes": 45,
            "notes": "Keep the raised details crisp.",
        },
        "generator": {"mode": "3D", "projectName": "pocket-dragon", "allowCustomization": True},
    }


def test_decodes_valid_url_safe_handoff():
    result = decode_handoff_param(_encoded_handoff(_payload()))

    assert result.error is None
    assert result.handoff is not None
    assert result.handoff.item.name == "Pocket Dragon"
    assert result.handoff.print.colors == ("Black", "Gold")
    assert result.handoff.generator.mode == "3D"


def test_invalid_handoffs_return_clear_errors_without_raising():
    malformed = decode_handoff_param("this-is-not-base64%")
    wrong_schema = decode_handoff_param(_encoded_handoff({"schema": "other.v1"}))
    non_json = decode_handoff_param(base64.urlsafe_b64encode(b"not json").decode("ascii"))

    assert malformed.handoff is None and malformed.error
    assert wrong_schema.handoff is None and "Unsupported handoff schema" in wrong_schema.error
    assert non_json.handoff is None and non_json.error


def test_print_request_includes_handoff_project_settings_and_paths(tmp_path):
    handoff = decode_handoff_param(_encoded_handoff(_payload())).handoff
    assert handoff is not None
    project = ProjectState(project_name="pocket-dragon", enabled_palette_colors=[FilamentColor("Gold", "#c7a34a")])

    request = build_print_request(
        handoff,
        project,
        mode="3D",
        package_paths={"zip": tmp_path / "pocket-dragon-print-package.zip"},
        workflow_paths={"source_model": tmp_path / "dragon.stl"},
        notes="Customer asked for two copies.",
    )

    assert request["schema"] == PRINT_REQUEST_SCHEMA
    assert request["sourceHandoff"]["item"]["id"] == "dragon-01"
    assert request["tokenforge"]["projectMetadata"]["project_name"] == "pocket-dragon"
    assert request["tokenforge"]["generatedPackagePaths"]["zip"].endswith("pocket-dragon-print-package.zip")
    assert request["print"]["notes"] == "Customer asked for two copies."
    assert json.loads(serialize_print_request(request))["tokenforge"]["mode"] == "3D"
