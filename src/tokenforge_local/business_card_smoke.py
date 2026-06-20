from __future__ import annotations

from pathlib import Path

from .business_card import BusinessCardSettings, generate_business_card_artifacts
from .models import FilamentColor, ProjectState


DEFAULT_OUTPUT_DIR = Path("outputs/test-runs/card-smoke")


def smoke_project() -> ProjectState:
    return ProjectState(
        project_name="business-card-smoke",
        enabled_palette_colors=[
            FilamentColor("Black", "#111111", True),
            FilamentColor("Ivory White", "#f2ead7", True),
            FilamentColor("PLA Gold", "#c7a34a", True),
        ],
    )


def run_smoke(output_dir: Path = DEFAULT_OUTPUT_DIR):
    return generate_business_card_artifacts(
        "https://example.com/tokenforge-business-card",
        BusinessCardSettings(),
        smoke_project(),
        output_dir,
        "business-card-smoke",
    )


def main() -> int:
    artifacts = run_smoke()
    print("Business card relief smoke fixture generated")
    print(f"STL: {artifacts.stl_path}")
    print(f"GLB: {artifacts.glb_path}")
    print(f"Card preview: {artifacts.preview_path}")
    print(f"QR preview: {artifacts.qr_preview_path}")
    for warning in artifacts.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
