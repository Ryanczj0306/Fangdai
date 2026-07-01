"""Unit tests for selling-cost and closing-cost parameters."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from fangdai import Inputs, compute  # noqa: E402

BASE = dict(home_price=500_000, down_pct=20, apr=6.5, extra_pay=0,
            mcc_pct=0, tax_rate_pct=24)


class TransactionCostTests(unittest.TestCase):
    def test_default_selling_cost_is_6pct(self):
        r = compute(Inputs(**BASE))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.sale_proceeds, y1.home_value * 0.94, places=6)

    def test_selling_cost_zero_means_full_value(self):
        r = compute(Inputs(**BASE, selling_cost_pct=0))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.sale_proceeds, y1.home_value, places=6)

    def test_old_7pct_behavior_is_recoverable(self):
        r = compute(Inputs(**BASE, selling_cost_pct=7))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.sale_proceeds, y1.home_value * 0.93, places=6)

    def test_closing_costs_added_to_renter_initial(self):
        with_cc = compute(Inputs(**BASE, closing_cost_pct=3))
        no_cc = compute(Inputs(**BASE, closing_cost_pct=0))
        self.assertAlmostEqual(with_cc.closing_costs, 15_000, places=6)
        self.assertAlmostEqual(
            with_cc.renter_initial - no_cc.renter_initial, 15_000, places=6,
        )

    def test_closing_costs_hurt_the_buyer(self):
        # The renter invests the buyer's closing cash; higher closing costs
        # must reduce the buyer's advantage in every year.
        with_cc = compute(Inputs(**BASE, closing_cost_pct=4))
        no_cc = compute(Inputs(**BASE, closing_cost_pct=0))
        for a, b in zip(with_cc.years, no_cc.years):
            self.assertLess(a.advantage, b.advantage, f"year {a.y}")

    def test_credits_scenario_still_gets_closing_costs(self):
        # Even when the down payment is covered by credits, the buyer still
        # pays closing costs in cash — the renter invests them.
        r = compute(Inputs(home_price=400_000, down_pct=5, loan_credit_pct=5,
                           down_pay_by_credit=True, closing_cost_pct=3,
                           extra_pay=0))
        self.assertAlmostEqual(r.renter_initial, 12_000, places=6)


if __name__ == "__main__":
    unittest.main()
