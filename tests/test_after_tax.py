"""Unit tests for the §121 after-tax exit comparison."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from fangdai import Inputs, compute  # noqa: E402

BASE = dict(home_price=400_000, down_pct=50, apr=6.5, extra_pay=0,
            house_return_pct=5, stock_return_pct=8, rent=2_000,
            rent_growth_pct=3, hoa=100, insurance=3_200, maintenance=2_300,
            mcc_pct=0, tax_rate_pct=24, ltcg_rate_pct=18.8)


class AfterTaxTests(unittest.TestCase):
    def test_no_sec121_exclusion_in_year_1(self):
        # §121 needs 2 years of ownership+use. With 0% selling cost and
        # 12% appreciation, year 1 has a real gain — it must be taxed.
        r = compute(Inputs(home_price=500_000, down_pct=50, apr=6.5,
                           extra_pay=0, house_return_pct=12,
                           selling_cost_pct=0, closing_cost_pct=0,
                           ltcg_rate_pct=15))
        y1 = r.years[0]
        gain = y1.sale_proceeds - 500_000
        self.assertGreater(gain, 0)
        self.assertAlmostEqual(y1.buyer_exit_tax, gain * 0.15, places=6)

    def test_sec121_shelters_home_gain_from_year_2(self):
        # Same scenario at year 2: gain is far below the 500k cap -> home
        # portion untaxed (buyer had no stock gains yet either).
        r = compute(Inputs(home_price=500_000, down_pct=50, apr=6.5,
                           extra_pay=0, house_return_pct=12,
                           selling_cost_pct=0, closing_cost_pct=0,
                           ltcg_rate_pct=15))
        y2 = r.years[1]
        self.assertLess(y2.sale_proceeds - 500_000, 500_000)
        self.assertEqual(y2.buyer_exit_tax, 0.0)

    def test_gain_above_sec121_cap_is_taxed(self):
        # $1M home at 12%/yr blows through the 500k exclusion later on.
        r = compute(Inputs(home_price=1_000_000, down_pct=30, apr=6.5,
                           extra_pay=0, house_return_pct=12,
                           closing_cost_pct=0, selling_cost_pct=6,
                           ltcg_rate_pct=15, sec121_cap=500_000))
        row = r.years[14]
        gain = row.sale_proceeds - 1_000_000
        self.assertGreater(gain, 500_000)
        expected_home_tax = (gain - 500_000) * 0.15
        # Buyer has no stock gains in this scenario before payoff completes
        self.assertGreaterEqual(row.buyer_exit_tax, expected_home_tax - 1e-6)

    def test_renter_taxed_on_gains(self):
        r = compute(Inputs(**BASE))
        row = r.years[9]
        gain = row.renter_value - row.cum_invested_renter
        self.assertGreater(gain, 0)
        self.assertAlmostEqual(row.renter_exit_tax, gain * 0.188, places=6)
        self.assertAlmostEqual(
            row.renter_after_tax, row.renter_value - row.renter_exit_tax, places=6,
        )

    def test_ltcg_zero_matches_pretax(self):
        r = compute(Inputs(**{**BASE, "ltcg_rate_pct": 0}))
        for row in r.years:
            self.assertEqual(row.buyer_exit_tax, 0.0)
            self.assertEqual(row.renter_exit_tax, 0.0)
            self.assertAlmostEqual(row.advantage_after_tax, row.advantage, places=6)

    def test_sec121_favors_buyer_after_tax(self):
        # The real-world $400k/50%-down case: §121 shelters the buyer while
        # the renter's larger portfolio gain is taxed, so the after-tax
        # breakeven arrives earlier than the pre-tax one (which may not
        # exist at all within 30 years).
        r = compute(Inputs(**BASE))
        for row in r.years[1:]:  # from year 2, when §121 applies
            self.assertGreaterEqual(
                row.advantage_after_tax + 1e-9, row.advantage, f"year {row.y}",
            )
        if r.breakeven_year is not None:
            self.assertLessEqual(r.breakeven_year_after_tax, r.breakeven_year)
        else:
            self.assertIsNotNone(r.breakeven_year_after_tax)


if __name__ == "__main__":
    unittest.main()
