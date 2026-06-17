from __future__ import annotations

import subprocess
import sys


def main() -> int:
    args = sys.argv[1:] or ["tests"]
    return subprocess.call([sys.executable, "-m", "pytest", *args])


if __name__ == "__main__":
    raise SystemExit(main())
