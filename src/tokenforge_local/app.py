from __future__ import annotations

from .shell import build_ui, main

__all__ = ["build_ui", "main"]

if __name__ in {"__main__", "__mp_main__"}:
    main()
