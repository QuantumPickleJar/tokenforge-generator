from __future__ import annotations

from PIL import Image

from tokenforge_local.business_card import (
    BusinessCardSettings,
    build_business_card_mesh,
    detect_qr_content,
    generate_business_card_artifacts,
    generate_qr_preview,
)
from tokenforge_local.models import FilamentColor, ProjectState


def _project() -> ProjectState:
    return ProjectState(
        project_name="card-test",
        enabled_palette_colors=[
            FilamentColor("Black", "#111111", True),
            FilamentColor("Ivory White", "#f2ead7", True),
            FilamentColor("PLA Gold", "#c7a34a", True),
        ],
    )


def test_generate_qr_preview_decodes_content() -> None:
    settings = BusinessCardSettings(qr_size_mm=28.0)
    content = "https://example.com/tokenforge-card"

    preview = generate_qr_preview(content, settings, _project())

    assert preview.decoded_content == content
    assert preview.module_count > 0
    assert preview.module_size_mm > 0


def test_qr_detection_fails_gracefully_on_blank_image() -> None:
    result = detect_qr_content(Image.new("RGB", (240, 140), "white"))

    assert result.found is False
    assert result.content is None
    assert "No QR code" in result.message or "failed safely" in result.message


def test_business_card_mesh_contains_base_and_raised_qr_modules() -> None:
    settings = BusinessCardSettings(qr_size_mm=24.0)
    mesh, module_size, warnings = build_business_card_mesh("https://example.com", settings, _project())

    assert not mesh.is_empty
    assert len(mesh.vertices) > 8
    assert len(mesh.faces) > 12
    assert module_size > 0
    assert any("Single-nozzle MVP" in warning for warning in warnings)


def test_generate_business_card_artifacts_exports_stl_glb_and_previews(tmp_path) -> None:
    settings = BusinessCardSettings(qr_size_mm=24.0)
    artifacts = generate_business_card_artifacts(
        "https://example.com/business-card",
        settings,
        _project(),
        output_dir=tmp_path,
        project_name="pytest-card",
    )

    assert artifacts.stl_path.exists()
    assert artifacts.glb_path.exists()
    assert artifacts.preview_path.exists()
    assert artifacts.qr_preview_path.exists()
    assert artifacts.decoded_generated_qr == "https://example.com/business-card"
