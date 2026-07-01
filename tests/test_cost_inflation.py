"""Unit tests for holding-cost inflation (HOA / insurance / maintenance)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from fangdai import Inputs, compute  # noqa: E402

BASE = dict(home_price=500_000, down_pct=25, apr=6.5, extra_pay=0,
            mcc_pct=0, tax_rate_pct=24, hoa=100,
            insurance=3_000, maintenance=2_400)


class CostInflationTests(unittest.TestCase):
    def test_year1_costs_are_nominal(self):
        r = compute(Inputs(**BASE, inflation_pct=2.5))
        # yr1: no inflation applied yet; no PMI at 25% down.
        self.assertAlmostEqual(r.years[0].y_other, 100 * 12 + 3_000 + 2_400, places=6)

    def test_costs_grow_with_inflation(self):
        r = compute(Inputs(**BASE, inflation_pct=2.5))
        base_other = 100 * 12 + 3_000 + 2_400
        self.assertAlmostEqual(
            r.years[9].y_other, base_other * 1.025 ** 9, places=4,
        )

    def test_zero_inflation_keeps_costs_flat(self):
        r = compute(Inputs(**BASE, inflation_pct=0))
        self.assertAlmostEqual(r.years[0].y_other, r.years[29].y_other, places=6)

    def test_inflation_hurts_the_buyer(self):
        hot = compute(Inputs(**BASE, inflation_pct=5))
        flat = compute(Inputs(**BASE, inflation_pct=0))
        # Higher cost inflation must reduce the buyer's advantage over time.
        self.assertLess(hot.years[19].advantage, flat.years[19].advantage)

    def test_pmi_not_inflated(self):
        # 5% down triggers PMI; PMI stays nominal while other costs inflate.
        r = compute(Inputs(home_price=500_000, down_pct=5, apr=6.5,
                           extra_pay=0, pmi=300, hoa=0, insurance=0,
                           maintenance=0, inflation_pct=10, mcc_pct=0))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.y_other, 300 * 12, places=6)


if __name__ == "__main__":
    unittest.main()
