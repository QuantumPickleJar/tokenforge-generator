from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from .models import FilamentColor, LayerColorStop, ProjectState, StyleSettings, TextLayoutConfig
from .preview_artifacts import build_preview_artifacts, save_preview_artifacts


def _make_smoke_image(size: tuple[int, int] = (180, 252)) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    width, height = size
    for x in range(width):
        shade = int(255 * (x / max(1, width - 1)))
        draw.line((x, 0, x, height), fill=(shade, shade, 255 - shade // 2))
    draw.ellipse((width * 0.18, height * 0.16, width * 0.82, height * 0.62), fill=(220, 70, 120), outline=(20, 20, 20), width=4)
    draw.rectangle((width * 0.24, height * 0.66, width * 0.76, height * 0.86), fill=(230, 190, 70), outline=(30, 30, 30), width=3)
    return image


def build_smoke_project() -> ProjectState:
    style = StyleSettings(
        border_enabled=True,
        border_thickness_px=10,
        title_text=TextLayoutConfig(enabled=True, content="SMOKE", size_px=28, banner_enabled=True),
        bottom_text=TextLayoutConfig(enabled=False, content="", size_px=20),
    )
    return ProjectState(
        project_name="preview-smoke",
        enabled_palette_colors=[
            FilamentColor("Black", "#111111", True),
            FilamentColor("Pink", "#ff75b5", True),
            FilamentColor("PLA Gold", "#c7a34a", True),
            FilamentColor("Ivory White", "#f2ead7", True),
        ],
        style_settings=style,
        layer_color_stops=[
            LayerColorStop(1, "Black", "#111111"),
            LayerColorStop(3, "Pink", "#ff75b5"),
            LayerColorStop(5, "PLA Gold", "#c7a34a"),
            LayerColorStop(6, "Ivory White", "#f2ead7"),
        ],
    )


def run_preview_smoke(output_dir: Path | str = Path("outputs/test-runs/preview-smoke")) -> dict[str, Path]:
    prepared = _make_smoke_image()
    project = build_smoke_project()
    artifacts = build_preview_artifacts(prepared, project, output_size=(180, 252), soften_boundaries=False)
    return save_preview_artifacts(artifacts, output_dir, project.project_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic Tokenforge preview smoke-test PNGs.")
    parser.add_argument("--output-dir", default="outputs/test-runs/preview-smoke", help="Directory for generated preview PNGs.")
    args = parser.parse_args(argv)

    paths = run_preview_smoke(Path(args.output_dir))
    print("Preview smoke artifacts written:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
