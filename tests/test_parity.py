"""JS <-> Python parity tests.

The web app's calculation engine lives between the FANGDAI-ENGINE-BEGIN /
FANGDAI-ENGINE-END markers in index.html as a pure, DOM-free function
``computeModel(I)``. This test extracts that block verbatim, runs it under
Node.js, and asserts it produces the same numbers as ``cli/fangdai.py``'s
``compute()`` across a battery of scenarios.

This is the guard against the two implementations drifting apart.
Skipped when Node.js is not installed.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))
import fangdai  # noqa: E402
from fangdai import Inputs, compute  # noqa: E402

NODE = shutil.which("node")
REL_TOL = 1e-9
ABS_TOL = 1e-6

# Python Inputs field -> JS I key
FIELD_MAP = {
    "home_price": "hp", "down_pct": "dp", "apr": "apr", "loan_years": "ly",
    "prop_tax_pct": "ptr", "homestead": "hs", "hoa": "hoa", "pmi": "pmi",
    "insurance": "ins", "maintenance": "mnt", "tax_rate_pct": "tr",
    "mcc_pct": "mccPct", "std_deduction": "stdDed", "salt_cap": "saltCap",
    "charity": "charity", "inflation_pct": "inflPct",
    "selling_cost_pct": "sellCostPct", "closing_cost_pct": "closeCostPct",
    "ltcg_rate_pct": "ltcgPct", "sec121_cap": "sec121Cap",
    "rent": "rent", "rent_growth_pct": "rg", "stock_return_pct": "sr",
    "house_return_pct": "hr", "horizon": "py", "extra_pay": "customPay",
    "loan_credit_pct": "creditsPct", "down_pay_by_credit": "downPayByCredit",
}

# (python Result attr, JS M key) top-level comparisons
TOP_MAP = [
    ("monthly_payment", "mp"), ("monthly_payment_min", "mpMin"),
    ("down_payment", "downPay"), ("loan", "loan"),
    ("credit_amount", "creditAmount"), ("closing_costs", "closingCosts"),
    ("renter_initial", "renterInitial"),
    ("payoff_year", "payoffY"), ("breakeven_year", "bkY"),
    ("breakeven_year_after_tax", "bkYAT"),
]

# (python YearRow attr, JS yd key) per-year comparisons
YEAR_MAP = [
    ("advantage", "adv"), ("loan_balance", "bal"),
    ("buyer_after_sale", "bt"), ("renter_value", "rw"),
    ("buyer_exit_tax", "buyerExitTax"), ("renter_exit_tax", "renterExitTax"),
    ("buyer_after_tax", "btAT"), ("renter_after_tax", "rwAT"),
    ("advantage_after_tax", "advAT"),
    ("home_value", "hve"), ("sale_proceeds", "sale"),
    ("y_interest", "yInt"), ("y_principal", "yPrin"),
    ("y_property_tax", "yPT"), ("y_other", "yOth"),
    ("y_mcc", "yMCC"), ("y_itemized", "yItemized"),
    ("y_baseline_deduction", "yBaseline"), ("itemizing", "itemizing"),
    ("y_tax_deduction_savings", "yTxDed"), ("y_benefit", "yBenefit"),
    ("y_net_cost", "yNetCost"), ("y_rent_total", "yRent"),
    ("cum_invested_renter", "cInvested"), ("cum_invested_buyer", "cBuyerInvested"),
    ("buyer_stk", "buyerStk"),
]

SCENARIOS: dict[str, dict] = {
    "defaults": {},
    "real_600k": dict(home_price=600_000, down_pct=33.333, apr=6.5,
                      house_return_pct=5, stock_return_pct=8, rent=2_000,
                      rent_growth_pct=3, extra_pay=0, hoa=100,
                      insurance=4_800, maintenance=3_500,
                      mcc_pct=0, tax_rate_pct=24, horizon=10),
    "real_400k_20down": dict(home_price=400_000, down_pct=20, apr=6.5,
                             extra_pay=0, mcc_pct=0, tax_rate_pct=24,
                             insurance=3_200, maintenance=2_300, hoa=100),
    "credits_mcc": dict(home_price=480_000, down_pct=5, loan_credit_pct=5,
                        apr=6.25, rent=2_200, horizon=5,
                        mcc_pct=15, tax_rate_pct=20),
    "salt_cap_binds": dict(home_price=2_000_000, down_pct=50, apr=6.5,
                           extra_pay=0, prop_tax_pct=4, homestead=0,
                           mcc_pct=0, tax_rate_pct=35),
    "charity": dict(home_price=600_000, down_pct=25, apr=7.0, extra_pay=0,
                    charity=10_000, tax_rate_pct=32),
    "all_cash": dict(home_price=300_000, down_pct=100, extra_pay=0, mcc_pct=0),
    "fast_payoff": dict(home_price=400_000, down_pct=20, apr=6.5,
                        extra_pay=5_000, mcc_pct=0, tax_rate_pct=24),
    "zero_apr": dict(home_price=400_000, down_pct=20, apr=0, extra_pay=0),
    "high_inflation": dict(home_price=600_000, down_pct=30, apr=6.5,
                           extra_pay=0, inflation_pct=6, tax_rate_pct=24),
    "txn_costs": dict(home_price=500_000, down_pct=20, apr=6.5, extra_pay=0,
                      selling_cost_pct=8, closing_cost_pct=4, tax_rate_pct=24),
    "free_transactions": dict(home_price=500_000, down_pct=20, apr=6.5,
                              extra_pay=0, selling_cost_pct=0, closing_cost_pct=0),
    "after_tax_niit": dict(home_price=400_000, down_pct=50, apr=6.5, extra_pay=0,
                           house_return_pct=5, stock_return_pct=8, rent=2_000,
                           ltcg_rate_pct=18.8, tax_rate_pct=24),
    "sec121_cap_exceeded": dict(home_price=1_000_000, down_pct=30, apr=6.5,
                                extra_pay=0, house_return_pct=12,
                                ltcg_rate_pct=15, sec121_cap=500_000),
    "no_exit_tax": dict(home_price=400_000, down_pct=20, apr=6.5, extra_pay=0,
                        ltcg_rate_pct=0),
}


def extract_js_engine() -> str:
    html = (REPO_ROOT / "index.html").read_text()
    begin = html.index("FANGDAI-ENGINE-BEGIN")
    begin = html.index("\n", begin) + 1
    end = html.rindex("FANGDAI-ENGINE-END")
    end = html.rindex("\n", 0, end)
    return html[begin:end]


def run_js(inputs_js: dict) -> dict:
    engine = extract_js_engine()
    script = (
        engine
        + "\nconst I = JSON.parse(process.argv[2]);"
        + "\nconsole.log(JSON.stringify(computeModel(I)));\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        path = f.name
    try:
        proc = subprocess.run(
            [NODE, path, json.dumps(inputs_js)],
            capture_output=True, text=True, timeout=60,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


def to_js_inputs(I: Inputs) -> dict:
    return {js: getattr(I, py) for py, js in FIELD_MAP.items()}


def close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


@unittest.skipUnless(NODE, "node not installed — JS parity not checked")
class ParityTests(unittest.TestCase):
    maxDiff = None


def _make_test(name: str, kwargs: dict):
    def test(self: ParityTests) -> None:
        I = Inputs(**kwargs)
        py_res = compute(I)
        js_res = run_js(to_js_inputs(Inputs(**kwargs)))  # fresh, un-normalized copy

        for py_attr, js_key in TOP_MAP:
            self.assertTrue(
                close(getattr(py_res, py_attr), js_res[js_key]),
                f"{name}: top-level {py_attr} {getattr(py_res, py_attr)!r} "
                f"!= JS {js_key} {js_res[js_key]!r}",
            )

        self.assertEqual(len(py_res.years), len(js_res["yd"]))
        for row, js_row in zip(py_res.years, js_res["yd"]):
            for py_attr, js_key in YEAR_MAP:
                self.assertTrue(
                    close(getattr(row, py_attr), js_row[js_key]),
                    f"{name} year {row.y}: {py_attr} {getattr(row, py_attr)!r} "
                    f"!= JS {js_key} {js_row[js_key]!r}",
                )
    return test


for _name, _kwargs in SCENARIOS.items():
    setattr(ParityTests, f"test_parity_{_name}", _make_test(_name, _kwargs))


if __name__ == "__main__":
    unittest.main()
