"""Golden-output regression tests for the CLI.

Runs ``cli/fangdai.py --json`` for each scenario in ``scenarios.py`` and
compares the parsed result against the checked-in golden file, with a small
float tolerance. Any intentional model change must regenerate the goldens
(``python3 tests/update_goldens.py``) in the same commit, so the numeric
impact of the change is visible in the diff.

Stdlib only — run with ``python3 -m unittest discover -s tests``.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import CLI, GOLDEN_DIR, SCENARIOS  # noqa: E402

REL_TOL = 1e-9
ABS_TOL = 1e-6


def run_cli(args: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, str(CLI), *args, "--json"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError(f"CLI failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def assert_deep_close(test: unittest.TestCase, got, want, path: str = "$") -> None:
    if isinstance(want, dict):
        test.assertIsInstance(got, dict, path)
        test.assertEqual(sorted(got.keys()), sorted(want.keys()),
                         f"{path}: key mismatch")
        for k in want:
            assert_deep_close(test, got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        test.assertIsInstance(got, list, path)
        test.assertEqual(len(got), len(want), f"{path}: length mismatch")
        for i, (g, w) in enumerate(zip(got, want)):
            assert_deep_close(test, g, w, f"{path}[{i}]")
    elif isinstance(want, bool) or want is None or isinstance(want, str):
        test.assertEqual(got, want, path)
    elif isinstance(want, (int, float)):
        test.assertTrue(
            isinstance(got, (int, float)) and not isinstance(got, bool),
            f"{path}: expected number, got {type(got).__name__}",
        )
        test.assertTrue(
            math.isclose(got, want, rel_tol=REL_TOL, abs_tol=ABS_TOL),
            f"{path}: {got!r} != {want!r}",
        )
    else:  # pragma: no cover
        test.fail(f"{path}: unhandled golden type {type(want).__name__}")


class GoldenTests(unittest.TestCase):
    maxDiff = None


def _make_test(name: str, args: list[str]):
    def test(self: GoldenTests) -> None:
        golden_path = GOLDEN_DIR / f"{name}.json"
        self.assertTrue(
            golden_path.exists(),
            f"missing golden {golden_path} — run: python3 tests/update_goldens.py",
        )
        want = json.loads(golden_path.read_text())
        got = run_cli(args)
        assert_deep_close(self, got, want)
    return test


for _name, _args in SCENARIOS.items():
    setattr(GoldenTests, f"test_golden_{_name}", _make_test(_name, _args))


if __name__ == "__main__":
    unittest.main()
