from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw
import trimesh

from .models import FilamentColor, ProjectState
from .palette import enabled_colors, sort_colors_for_layering
from .utils import ensure_rgb, hex_to_rgb, safe_project_name

try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    qrcode = None
    ERROR_CORRECT_H = None


@dataclass(slots=True)
class BusinessCardSettings:
    card_width_mm: float = 89.0
    card_height_mm: float = 51.0
    base_thickness_mm: float = 0.80
    raised_feature_height_mm: float = 0.40
    accent_height_mm: float = 0.70
    corner_radius_mm: float = 2.0
    qr_size_mm: float = 22.0
    qr_quiet_zone_modules: int = 4
    qr_margin_right_mm: float = 5.0
    qr_margin_bottom_mm: float = 5.0


@dataclass(slots=True)
class QRDetectionResult:
    content: str | None
    found: bool
    points: list[list[float]] | None
    message: str


@dataclass(slots=True)
class QRPreviewResult:
    image: Image.Image
    decoded_content: str | None
    module_count: int
    module_size_mm: float
    warnings: list[str]


@dataclass(slots=True)
class BusinessCardArtifacts:
    stl_path: Path
    glb_path: Path
    preview_path: Path
    qr_preview_path: Path
    module_size_mm: float
    decoded_generated_qr: str | None
    warnings: list[str]


@dataclass(slots=True)
class CardColorSet:
    base: FilamentColor
    raised: FilamentColor
    accent: FilamentColor


def _require_qrcode() -> None:
    if qrcode is None:
        raise RuntimeError("The qrcode package is not installed. Run `pip install -e .[dev]` after pulling this branch.")


def card_colors_for_project(project: ProjectState) -> CardColorSet:
    colors = sort_colors_for_layering(enabled_colors(project.enabled_palette_colors))
    if not colors:
        neutral = FilamentColor("Neutral Gray", "#888888", True)
        dark = FilamentColor("Black", "#111111", True)
        return CardColorSet(base=neutral, raised=dark, accent=dark)
    if len(colors) == 1:
        return CardColorSet(base=colors[0], raised=colors[0], accent=colors[0])
    base = colors[-1]
    raised = colors[0]
    accent = colors[-2] if len(colors) > 2 else raised
    return CardColorSet(base=base, raised=raised, accent=accent)


def detect_qr_content(image: Image.Image) -> QRDetectionResult:
    try:
        rgb = np.asarray(ensure_rgb(image), dtype=np.uint8)
        detector = cv2.QRCodeDetector()
        content, points, _straight = detector.detectAndDecode(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    except Exception as exc:
        return QRDetectionResult(None, False, None, f"QR detection failed safely: {exc}")

    cleaned = content.strip() if content else ""
    if cleaned:
        point_list = points.reshape(-1, 2).astype(float).tolist() if points is not None else None
        return QRDetectionResult(cleaned, True, point_list, "QR detected and decoded.")
    return QRDetectionResult(None, False, None, "No QR code was detected. Enter QR content manually.")


def _qr_matrix(content: str, quiet_zone_modules: int) -> list[list[bool]]:
    _require_qrcode()
    cleaned = str(content or "").strip()
    if not cleaned:
        raise ValueError("QR content is empty. Detect a QR code or enter content manually.")

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=max(0, int(quiet_zone_modules)),
    )
    qr.add_data(cleaned)
    qr.make(fit=True)
    return [[bool(cell) for cell in row] for row in qr.get_matrix()]


def qr_module_size_mm(content: str, settings: BusinessCardSettings) -> float:
    matrix = _qr_matrix(content, settings.qr_quiet_zone_modules)
    return settings.qr_size_mm / max(1, len(matrix))


def qr_feature_warnings(content: str, settings: BusinessCardSettings, project: ProjectState) -> list[str]:
    warnings: list[str] = []
    try:
        module_size = qr_module_size_mm(content or "https://example.com", settings)
    except Exception:
        module_size = settings.qr_size_mm / 29.0

    nozzle = project.printer_preferences.nozzle_size_mm
    min_feature = max(nozzle, project.printer_preferences.minimum_feature_size_mm)
    if module_size < nozzle:
        warnings.append(
            f"QR modules are about {module_size:.2f} mm, smaller than the {nozzle:.2f} mm nozzle. Increase QR size or use a smaller nozzle."
        )
    elif module_size < min_feature:
        warnings.append(
            f"QR modules are about {module_size:.2f} mm, below the configured {min_feature:.2f} mm minimum feature target."
        )

    if settings.raised_feature_height_mm < project.printer_preferences.standard_layer_height_mm:
        warnings.append(
            "Raised QR height is less than one standard layer; increase feature height for a clearer manual color-change band."
        )

    warnings.append(
        "Single-nozzle MVP uses base color plus one raised QR/text color. Multiple same-layer colors would require AMS/MMU or hand painting."
    )
    return warnings


def generate_qr_preview(content: str, settings: BusinessCardSettings, project: ProjectState, pixels: int = 640) -> QRPreviewResult:
    matrix = _qr_matrix(content, settings.qr_quiet_zone_modules)
    module_count = len(matrix)
    box = max(1, pixels // module_count)
    image_size = box * module_count
    image = Image.new("RGB", (image_size, image_size), "white")
    draw = ImageDraw.Draw(image)
    for row_index, row in enumerate(matrix):
        for col_index, is_dark in enumerate(row):
            if is_dark:
                x0 = col_index * box
                y0 = row_index * box
                draw.rectangle((x0, y0, x0 + box - 1, y0 + box - 1), fill="black")

    decoded = detect_qr_content(image).content
    module_size = settings.qr_size_mm / module_count
    return QRPreviewResult(
        image=image,
        decoded_content=decoded,
        module_count=module_count,
        module_size_mm=module_size,
        warnings=qr_feature_warnings(content, settings, project),
    )


def _color_rgba(hex_color: str) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, 255)


def _colored_box(extents: tuple[float, float, float], translation: tuple[float, float, float], rgba: tuple[int, int, int, int]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(translation)
    mesh.visual.face_colors = np.tile(np.asarray(rgba, dtype=np.uint8), (len(mesh.faces), 1))
    return mesh


def _qr_module_meshes(matrix: Sequence[Sequence[bool]], settings: BusinessCardSettings, raised_hex: str) -> list[trimesh.Trimesh]:
    module_count = len(matrix)
    if module_count < 1:
        return []
    module_size = settings.qr_size_mm / module_count
    qr_left = settings.card_width_mm / 2.0 - settings.qr_margin_right_mm - settings.qr_size_mm
    qr_bottom = -settings.card_height_mm / 2.0 + settings.qr_margin_bottom_mm
    meshes: list[trimesh.Trimesh] = []
    rgba = _color_rgba(raised_hex)
    for row_index, row in enumerate(matrix):
        for col_index, is_dark in enumerate(row):
            if not is_dark:
                continue
            x = qr_left + (col_index + 0.5) * module_size
            y = qr_bottom + settings.qr_size_mm - (row_index + 0.5) * module_size
            z = settings.base_thickness_mm + settings.raised_feature_height_mm / 2.0
            # Slight overlap keeps adjacent dark modules connected in most slicers.
            overlap = min(module_size * 0.04, 0.04)
            meshes.append(
                _colored_box(
                    (module_size + overlap, module_size + overlap, settings.raised_feature_height_mm),
                    (x, y, z),
                    rgba,
                )
            )
    return meshes


def build_card_preview_image(content: str, settings: BusinessCardSettings, project: ProjectState, pixels_wide: int = 1100) -> Image.Image:
    colors = card_colors_for_project(project)
    matrix = _qr_matrix(content, settings.qr_quiet_zone_modules)
    aspect = settings.card_height_mm / settings.card_width_mm
    width = max(320, int(pixels_wide))
    height = max(180, int(round(width * aspect)))
    scale = width / settings.card_width_mm
    image = Image.new("RGB", (width, height), colors.base.hex)
    draw = ImageDraw.Draw(image)

    margin_r = settings.qr_margin_right_mm * scale
    margin_b = settings.qr_margin_bottom_mm * scale
    qr_size_px = settings.qr_size_mm * scale
    module_px = qr_size_px / len(matrix)
    qr_left = width - margin_r - qr_size_px
    qr_top = height - margin_b - qr_size_px

    # Subtle outline makes the generated card preview distinct from the source image.
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=max(2, int(settings.corner_radius_mm * scale)), outline=colors.accent.hex, width=max(1, int(0.35 * scale)))
    draw.rectangle((qr_left, qr_top, qr_left + qr_size_px, qr_top + qr_size_px), fill=colors.base.hex)
    for row_index, row in enumerate(matrix):
        for col_index, is_dark in enumerate(row):
            if is_dark:
                x0 = qr_left + col_index * module_px
                y0 = qr_top + row_index * module_px
                draw.rectangle((x0, y0, x0 + module_px + 0.75, y0 + module_px + 0.75), fill=colors.raised.hex)

    return image


def build_business_card_mesh(content: str, settings: BusinessCardSettings, project: ProjectState) -> tuple[trimesh.Trimesh, float, list[str]]:
    matrix = _qr_matrix(content, settings.qr_quiet_zone_modules)
    colors = card_colors_for_project(project)
    base = _colored_box(
        (settings.card_width_mm, settings.card_height_mm, settings.base_thickness_mm),
        (0.0, 0.0, settings.base_thickness_mm / 2.0),
        _color_rgba(colors.base.hex),
    )
    meshes = [base, *_qr_module_meshes(matrix, settings, colors.raised.hex)]
    mesh = trimesh.util.concatenate(meshes)
    mesh.merge_vertices()
    module_size = settings.qr_size_mm / len(matrix)
    return mesh, module_size, qr_feature_warnings(content, settings, project)


def generate_business_card_artifacts(
    content: str,
    settings: BusinessCardSettings,
    project: ProjectState,
    output_dir: Path | str = Path("outputs/business-cards"),
    project_name: str = "business-card",
) -> BusinessCardArtifacts:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    safe_name = safe_project_name(project_name or "business-card")

    qr_preview = generate_qr_preview(content, settings, project)
    card_preview = build_card_preview_image(content, settings, project)
    mesh, module_size, warnings = build_business_card_mesh(content, settings, project)

    stl_path = output_path / f"{safe_name}-card-relief.stl"
    glb_path = output_path / f"{safe_name}-card-relief.glb"
    preview_path = output_path / f"{safe_name}-card-preview.png"
    qr_preview_path = output_path / f"{safe_name}-qr-preview.png"

    mesh.export(stl_path)
    mesh.export(glb_path)
    card_preview.save(preview_path)
    qr_preview.image.save(qr_preview_path)

    warnings = list(dict.fromkeys([*qr_preview.warnings, *warnings]))
    if qr_preview.decoded_content != str(content or "").strip():
        warnings.append("Generated QR preview did not decode back to the exact supplied content; verify before printing.")

    return BusinessCardArtifacts(
        stl_path=stl_path,
        glb_path=glb_path,
        preview_path=preview_path,
        qr_preview_path=qr_preview_path,
        module_size_mm=module_size,
        decoded_generated_qr=qr_preview.decoded_content,
        warnings=warnings,
    )
