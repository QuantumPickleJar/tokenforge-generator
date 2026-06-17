# Tokenforge Local

`tokenforge-local` is a local-first Python/NiceGUI app for converting a user-provided image into a thin 2.5D embossed STL token for single-nozzle, manual-filament-swap 3D printing.

The v0.1 target is a Magic-card-style token generator, not a general lithophane maker and not a slicer.

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

## What v0.1 intentionally does not do

- It does **not** slice models.
- It does **not** generate G-code.
- It does **not** implement 3MF export.
- It does **not** implement Ollama or AI critique.
- It does **not** download card art, fonts, sample images, or copyrighted assets.
- It does **not** require Photoshop, GIMP, cloud APIs, paid AI credits, AMS, or dual extrusion.

## Requirements

- Python 3.11+
- A local browser
- A slicer such as PrusaSlicer, Cura, OrcaSlicer, or similar for the final G-code handoff

## Setup

```bash
git clone <your-repo-url> tokenforge-local
cd tokenforge-local
git checkout feat/v0.1
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

## Basic workflow

1. Upload your own image.
2. Use the in-app crop preparation controls:
   - pan X/Y
   - zoom/scale
   - rotate in 90-degree increments
   - reset transform
   - confirm crop
3. Configure printer/profile preferences:
   - nozzle size
   - initial layer height
   - standard layer height
   - finished model thickness
   - minimum feature size
4. Configure style options:
   - border enabled/disabled
   - border style
   - border thickness
   - title and bottom text
   - banner toggles
   - emboss/engrave toggle for title text
   - simple badge placeholder
5. Enable/disable filament colors and edit hex values.
6. Generate the STL and print package.
7. Import the STL into your slicer.
8. Add manual color changes or pauses at the Z heights listed in the swap plan.
9. Preview in the slicer before printing.
10. Export G-code from the slicer.

## Output package

The generated ZIP package contains:

- `<project-name>.stl`
- `<project-name>-preview.png`
- `<project-name>-layer-preview.png`
- `<project-name>-swap-plan.csv`
- `<project-name>-print-notes.txt`
- `<project-name>.tokenforge.json`

The package ZIP itself is written next to these files as `<project-name>-print-package.zip`. A ZIP cannot contain itself without recursive packaging, so it is not embedded inside itself.

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

## Default Magic-card-style token profile

- Width: `63.0 mm`
- Height: `87.9 mm`
- Corner radius: `2.5 mm`

The height is intentionally 0.1 mm shorter than a typical 88 mm card height to leave practical room for print expansion and tolerance.

## Preferences and project JSON

Preferences are stored locally in:

```text
~/.tokenforge-local/preferences.json
```

Each generated project JSON stores:

- source image reference
- crop/transform settings
- printer preferences
- token dimensions
- enabled palette colors
- style/layout settings
- text content
- font selections
- banner/border choices
- generated layer plan metadata

## Font architecture

v0.1 does not include full font import. The data model already supports local imported font metadata so v0.2 can add:

- `.ttf` and `.otf` import
- user labels for imported font families
- font previewing
- removing imported fonts from preferences
- project-specific font references
- missing-font warnings and fallback behavior

Font import should remain local-only. Users are responsible for font licensing.

## Border/style architecture

v0.1 implements these basic presets:

- Thin line
- Double line
- Inset panel
- Simple plaque frame
- Wood frame
- Riveted metal frame
- Diamond plate frame
- Stone frame
- Marble frame

The style preset registry already includes grouped future categories for:

- Material Themes
- Simple Frames
- Fantasy / Decorative
- Cultural / Regional Inspiration
- Genre / Setting Themes

Cultural/regional styles are intended as respectful motif-inspired options. The code must not auto-generate fake real-world script. Any real script/text style should require user-provided text.

## Tests

```bash
pytest
```

Covered areas:

- preference loading/saving
- layer thickness calculation
- palette nearest-color mapping
- crop/transform metadata serialization
- style preset serialization/deserialization
- text layout configuration serialization
- swap plan generation
- ZIP package creation
- STL export smoke test

## Known limitations in v0.1

- The mesh is a blocky 2.5D height-map STL, not a production-grade relief sculpt.
- The browser crop UI uses sliders and preview regeneration, not a polished drag-handle canvas.
- The generated STL can become heavy if the working resolution is increased too much.
- Color mapping uses deterministic nearest RGB, not perceptual color matching.
- Tiny-island repair is automatic only; no brush/merge/thicken tools yet.
- The NiceGUI palette list is intentionally simple; after adding a new color, refreshing the page is the easiest way to see the new row.
- Style presets are proof-of-pipeline implementations, not final art direction.

## Recommended next development step

The next best step is v0.1.1 polish: replace the slider-based crop UI with a draggable canvas-style crop editor and add a small layer/Z preview table before export. That improves usability without changing the core pipeline.
