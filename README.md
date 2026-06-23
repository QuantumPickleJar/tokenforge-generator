# Tokenforge Local

`tokenforge-local` is a local-first Python/NiceGUI app for turning image art, business-card references, or STL geometry into manual-filament-swap 2.5D/3D preview workflows.

The v0.1 line focuses on image-driven token art: upload image → crop → style → reduced-color filament preview → generate STL/package.

The v0.2 feature branch adds mode-based workflows:

- `IMG` — existing art-token workflow.
- `CARD` — Business Card / Flat Relief wizard for QR-first printable plaques.
- `3D` — STL layer-color preview by model Z height.

## What v0.1 does

- Upload a user-provided image.
- Prepare it in the browser with pan, zoom, 90-degree rotation, reset, and confirm-crop controls.
- Show a rounded-rectangle Magic-card-style stencil using the default 63.0 mm × 87.9 mm token profile.
- Configure printer preferences and token defaults.
- Define and enable/disable filament palette colors.
- Add simple style options: border, text, banners, and a placeholder badge/emblem.
- Posterize the styled composition to enabled filament colors.
- Generate masks and automatically remove tiny islands below the configured minimum printable feature size.
- Assign enabled colors to Z/layer bands for manual filament changes.
- Export a 2.5D STL and a ZIP print package.

## What v0.2 starts

- Keeps the existing IMG workflow as the default mode.
- Adds a `CARD` mode for business-card-style flat relief output.
- Adds a real `3D` mode behind the top `IMG | CARD | 3D` toggle.
- Accepts uploaded `.stl` files as uncolored geometry.
- Loads STL geometry with `trimesh` and reports model bounds/dimensions.
- Applies Tokenforge palette/layer-band logic by model Z height.
- Colors each triangle by its face-centroid Z height for the first MVP preview.
- Exports temporary `.glb` viewer artifacts and displays them in the browser with orbit/zoom controls.
- Shows a clear 3MF placeholder/error: 3MF support is planned for a later v0.2 pass.

## CARD workflow MVP

The CARD workflow is intentionally not a grayscale-heightmap converter. It starts with business-card-friendly printable structure:

- rectangular card/plaque base
- regenerated QR code as crisp raised module geometry
- 2D card preview
- browser 3D GLB preview
- STL output for printing
- manual-filament-change-friendly base/raised feature design

Current CARD steps:

1. Select `CARD` in the toolbar.
2. Upload a business card image as reference.
3. Tokenforge attempts QR detection using OpenCV.
4. Confirm the decoded QR value, or enter QR content/URL manually.
5. Generate and validate a clean QR preview using `qrcode[pil]` with high error correction.
6. Choose layout cleanup mode:
   - source image as reference only
   - simple threshold/vector extraction placeholder
   - regenerated QR + simple relief blocks
7. Set print-oriented dimensions:
   - card width/height
   - base thickness
   - raised QR/text height
   - optional accent height
   - corner radius
   - QR physical size
   - QR quiet zone modules
8. Review nozzle/min-feature warnings.
9. Generate STL + GLB browser preview.

The CARD MVP outputs a clean regenerated QR on a rectangular base. Future passes can add real text/logo vector extraction, rounded-base meshing, SVG imports, and a Fabric.js/Konva.js-style 2D editor.

## What v0.2 intentionally does not do yet

- It does **not** parse slicer-specific color painting from 3MF.
- It does **not** split triangles at exact layer/color boundaries.
- It does **not** generate G-code.
- It does **not** integrate with a slicer.
- It does **not** provide slicer-grade print simulation.
- It does **not** build a full Canva/Figma-like editor inside Tokenforge.
- It does **not** perform robust OCR/text/logo vector extraction from business card images yet.

## Requirements

- Python 3.11+
- A local browser
- A slicer such as PrusaSlicer, Cura, OrcaSlicer, or similar for final G-code handoff

## Setup

```bash
git clone <your-repo-url> tokenforge-local
cd tokenforge-local
git checkout v0.2
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -e .[dev]
```

Alternative dependency install:

```bash
pip install -r requirements.txt
```

## Run the app

```bash
tokenforge-local
```

or:

```bash
python -m tokenforge_local.app
```

NiceGUI will start a local web app and open it in your browser.

## IMG workflow

1. Select `IMG` in the toolbar.
2. Upload your own image.
3. Use the in-app crop preparation controls:
   - pan X/Y
   - zoom/scale
   - rotate in 90-degree increments
   - reset transform
   - confirm crop
4. Configure printer/profile preferences:
   - nozzle size
   - initial layer height
   - standard layer height
   - finished model thickness
   - minimum feature size
5. Configure style options:
   - border enabled/disabled
   - border style
   - border thickness
   - title and bottom text
   - banner toggles
   - emboss/engrave toggle for title text
   - simple badge placeholder
6. Enable/disable filament colors and edit hex values.
7. Generate the STL and print package.
8. Import the STL into your slicer.
9. Add manual color changes or pauses at the Z heights listed in the swap plan.
10. Preview in the slicer before printing.
11. Export G-code from the slicer.

## 3D workflow MVP

1. Select `3D` in the toolbar.
2. Upload an STL file.
3. Check the model name, bounds, dimensions, vertex count, and face count.
4. Enable or edit Tokenforge filament colors.
5. Use the layer rail to adjust color order and layer spans.
6. Click **Refresh 3D layer preview**.
7. Orbit/zoom the browser preview.

The 3D preview is labeled:

> Layer color preview — estimated from model Z-height and selected filament changes.

For this MVP, each triangle is colored by its face centroid Z height. This is good enough for orientation and color-band planning, but it is not slicer-grade. A later pass can split triangles that cross color-change boundaries.

## Output package

The IMG-generated ZIP package contains:

- `<project-name>.stl`
- `<project-name>-preview.png`
- `<project-name>-layer-preview.png`
- `<project-name>-swap-plan.csv`
- `<project-name>-print-notes.txt`
- `<project-name>.tokenforge.json`

The package ZIP itself is written next to these files as `<project-name>-print-package.zip`. A ZIP cannot contain itself without recursive packaging, so it is not embedded inside itself.

The 3D preview workflow writes temporary GLB artifacts under `outputs/3d-previews/` for browser display.

The CARD workflow writes STL/GLB/PNG artifacts under `outputs/business-cards/`.

## Portfolio gallery → Tokenforge handoff

Portfolio/gallery pages can open Tokenforge with a URL-safe base64 JSON query parameter:

```text
http://localhost:8080/?handoff=<url-safe-base64-json>
```

The decoded JSON must use `"schema": "tokenforge.handoff.v1"` and has this shape:

```json
{
  "schema": "tokenforge.handoff.v1",
  "source": "portfolio-gallery",
  "intent": "request-print",
  "item": {
    "id": "",
    "name": "",
    "description": "",
    "galleryUrl": "",
    "imageUrl": "",
    "modelUrl": "",
    "previewUrl": ""
  },
  "print": {
    "category": "",
    "material": "",
    "nozzleMm": null,
    "layerHeightMm": null,
    "colors": [],
    "estimatedGrams": null,
    "estimatedTimeMinutes": null,
    "notes": ""
  },
  "generator": {
    "mode": "IMG",
    "projectName": "",
    "allowCustomization": true
  }
}
```

Tokenforge validates the schema and safely ignores invalid or missing handoffs; normal workflows remain available. A valid handoff preselects a supported mode (`IMG`, `CARD`, or `3D`), pre-fills the project name and supplied nozzle/layer height, and shows the gallery item, links, and print notes. Gallery image/model URLs are shown in copyable fields. The first MVP does not fetch them remotely: download the file yourself and upload it into Tokenforge.

Use **Prepare print request** to create a `printdesk.request.v1` JSON document, then **Download print request JSON**. The request contains the original handoff, current editable Tokenforge project metadata/settings, available generated package/workflow paths, and the Printdesk notes. It is a local handoff artifact only; Printdesk does not need to be installed or running.

## Test and smoke commands

```bash
python scripts/run_tests.py
python scripts/run_preview_smoke.py
python scripts/run_3d_smoke.py
python scripts/run_card_smoke.py
```

For environments that start with npm, this Python project includes compatibility commands:

```bash
npm run build # compiles src/ as a fast syntax check
npm test      # runs the Python pytest suite through .venv
```

Installed script equivalents:

```bash
tokenforge-preview-smoke
tokenforge-3d-smoke
tokenforge-card-smoke
```

The 3D smoke runner creates a tiny STL fixture and a colored GLB preview under `outputs/test-runs/3d-smoke/`.

The CARD smoke runner creates a QR business-card STL, GLB, card preview PNG, and QR preview PNG under `outputs/test-runs/card-smoke/`.

## Print notes

The print notes include:

- nozzle size
- initial layer height
- standard layer height
- finished model thickness
- expected layer count
- token dimensions
- enabled style options summary
- filament order
- manual filament swap Z heights
- slicer checklist

The most important slicer warning is: **do not scale Z** after importing the STL.
