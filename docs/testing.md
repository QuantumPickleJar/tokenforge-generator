# Tokenforge test runners

Use these commands from the repository root after installing the dev dependencies:

```bash
pip install -e .[dev]
```

## Full automated tests

```bash
python scripts/run_tests.py
```

Equivalent direct command:

```bash
python -m pytest
```

The preview regression tests cover:

- pure styled-preview and layer-span preview artifact generation
- layer-span preview changes when a color consumes more layers
- confirm-crop populates both styled and layer-span preview widgets with image data URLs
- preview smoke artifacts are written as PNG files

## Visual preview smoke test

```bash
python scripts/run_preview_smoke.py
```

or, after editable install:

```bash
tokenforge-preview-smoke
```

This writes deterministic PNG previews under:

```text
outputs/test-runs/preview-smoke/
```

Open those PNGs directly if the web UI is blank. If the PNGs are correct but the app is blank, the problem is likely UI/widget wiring. If the PNGs are missing or wrong, the problem is in the preview pipeline itself.

## CI

GitHub Actions runs the same pytest suite and uploads the preview smoke PNGs as workflow artifacts on pushes to `main` and `feat/**`.
