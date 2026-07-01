"""Shared scenario definitions for the golden-output regression tests.

Each scenario is a list of CLI flags passed to ``cli/fangdai.py --json``.
Golden files live in ``tests/golden/<name>.json`` and are regenerated with
``python3 tests/update_goldens.py``.

Guidelines:
- Pin flags explicitly where a default is expected to change (e.g. ``--mcc-pct``)
  so a default change and an engine change show up as separate golden diffs.
- Scenario "default" intentionally passes no flags: it is the canary that makes
  any default change visible in the golden diff.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "fangdai.py"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

SCENARIOS: dict[str, list[str]] = {
    # Canary: pure defaults. Changes whenever any default changes.
    "default": [],
    # Real-world case A: $600k, 1/3 down, no MCC, 24% bracket, standard payment.
    "real_600k": [
        "--home-price", "600000", "--down-pct", "33.333", "--apr", "6.5",
        "--house-return-pct", "5", "--stock-return-pct", "8",
        "--rent", "2000", "--rent-growth-pct", "3",
        "--extra-pay", "0", "--hoa", "100",
        "--insurance", "4800", "--maintenance", "3500",
        "--mcc-pct", "0", "--tax-rate-pct", "24", "--horizon", "10",
    ],
    # Real-world case B: $400k, 20% down — itemized deductions never clear the
    # standard deduction, so the true incremental tax benefit is $0.
    "real_400k_20down": [
        "--home-price", "400000", "--down-pct", "20", "--apr", "6.5",
        "--house-return-pct", "5", "--stock-return-pct", "8",
        "--rent", "2000", "--rent-growth-pct", "3",
        "--extra-pay", "0", "--hoa", "100",
        "--insurance", "3200", "--maintenance", "2300",
        "--mcc-pct", "0", "--tax-rate-pct", "24", "--horizon", "10",
    ],
    # Credits + MCC + default extra payment: exercises loan-credit handling,
    # a nonzero MCC, and the custom-payment branch.
    "credits_mcc": [
        "--home-price", "480000", "--down-pct", "5", "--loan-credit-pct", "5",
        "--apr", "6.25", "--rent", "2200", "--horizon", "5",
        "--mcc-pct", "15", "--tax-rate-pct", "20",
    ],
    # All-cash purchase: loan == 0 branch, buyer invests the rent difference.
    "all_cash": [
        "--home-price", "300000", "--down-pct", "100", "--extra-pay", "0",
        "--mcc-pct", "0",
    ],
    # Aggressive extra payment: early-payoff branch and buyer-side investing.
    "fast_payoff": [
        "--home-price", "400000", "--down-pct", "20", "--apr", "6.5",
        "--extra-pay", "5000", "--mcc-pct", "0", "--tax-rate-pct", "24",
    ],
}
