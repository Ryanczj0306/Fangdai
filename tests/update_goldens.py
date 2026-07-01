#!/usr/bin/env python3
"""Regenerate the golden files in tests/golden/ from the current CLI.

Usage: python3 tests/update_goldens.py

Only run this when a model change is *intended*; commit the regenerated
goldens together with the engine change so the numeric impact is reviewable.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import CLI, GOLDEN_DIR, SCENARIOS  # noqa: E402


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, args in SCENARIOS.items():
        proc = subprocess.run(
            [sys.executable, str(CLI), *args, "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            print(f"FAILED {name}: {proc.stderr}", file=sys.stderr)
            return 1
        data = json.loads(proc.stdout)
        out = GOLDEN_DIR / f"{name}.json"
        out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"wrote {out.relative_to(GOLDEN_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
