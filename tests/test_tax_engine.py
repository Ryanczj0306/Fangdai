"""Unit tests for the tax engine against hand-computed truths.

These encode the real-world verification session that motivated the fix:
a 2026 MFJ Texas household, 24% bracket, $32,200 standard deduction,
$40,400 SALT cap (OBBBA).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
import fangdai  # noqa: E402
from fangdai import CHARITY_ATL_CAP, Inputs, compute  # noqa: E402


def scenario_600k(**over) -> Inputs:
    base = dict(
        home_price=600_000, down_pct=33.333, apr=6.5,
        house_return_pct=5, stock_return_pct=8,
        rent=2_000, rent_growth_pct=3, extra_pay=0,
        hoa=100, insurance=4_800, maintenance=3_500,
        mcc_pct=0, tax_rate_pct=24, horizon=10,
    )
    base.update(over)
    return Inputs(**base)


class TaxEngineTests(unittest.TestCase):
    def test_mcc_defaults_to_zero(self):
        # Most buyers exceed MCC income limits; a nonzero default fabricates
        # a credit that doesn't exist.
        self.assertEqual(Inputs().mcc_pct, 0.0)

    def test_600k_year1_benefit_is_about_909(self):
        # Hand-computed: interest 25,868 + prop tax 10,120 = itemized 35,988;
        # over the 32,200 standard deduction by 3,788; x 24% = ~909.
        r = compute(scenario_600k())
        y1 = r.years[0]
        self.assertTrue(y1.itemizing)
        expected = (y1.y_interest + min(y1.y_property_tax, 40_400) - 32_200) * 0.24
        self.assertAlmostEqual(y1.y_benefit, expected, places=6)
        self.assertGreater(y1.y_benefit, 900)
        self.assertLess(y1.y_benefit, 920)

    def test_600k_benefit_erodes_to_zero_by_year_10(self):
        # Interest amortizes down while the standard deduction inflates 2.5%/yr;
        # the incremental benefit crosses zero around year 10.
        r = compute(scenario_600k())
        self.assertGreater(r.years[0].y_benefit, r.years[4].y_benefit)
        self.assertEqual(r.years[9].y_benefit, 0.0)
        self.assertFalse(r.years[9].itemizing)

    def test_400k_20down_never_itemizes(self):
        # Itemized ~26.4k never clears the 32.2k standard deduction: the
        # mortgage-interest deduction is worth exactly $0 to this buyer.
        r = compute(Inputs(
            home_price=400_000, down_pct=20, apr=6.5, extra_pay=0,
            mcc_pct=0, tax_rate_pct=24, hoa=100,
            insurance=3_200, maintenance=2_300,
        ))
        for row in r.years:
            self.assertEqual(row.y_benefit, 0.0, f"year {row.y}")
            self.assertFalse(row.itemizing, f"year {row.y}")

    def test_salt_cap_binds_on_expensive_property(self):
        # $2M home at 4% with no homestead: ~78k property tax in year 1,
        # far above the 40,400 cap — only the cap enters itemized deductions.
        r = compute(Inputs(
            home_price=2_000_000, down_pct=50, apr=6.5, extra_pay=0,
            prop_tax_pct=4, homestead=0, mcc_pct=0, tax_rate_pct=35,
        ))
        y1 = r.years[0]
        self.assertGreater(y1.y_property_tax, 40_400)
        ded_int = y1.y_interest  # mcc = 0
        self.assertAlmostEqual(y1.y_itemized, ded_int + 40_400, places=6)

    def test_charity_above_the_line_for_non_itemizer(self):
        # Non-itemizer: charity raises the baseline (capped at $2,000), so
        # giving does not create a phantom itemizing benefit.
        r = compute(Inputs(
            home_price=400_000, down_pct=20, apr=6.5, extra_pay=0,
            mcc_pct=0, tax_rate_pct=24, charity=10_000,
        ))
        y1 = r.years[0]
        self.assertAlmostEqual(
            y1.y_baseline_deduction, 32_200 + CHARITY_ATL_CAP, places=6,
        )
        # Charity is also inside itemized totals.
        self.assertGreater(y1.y_itemized, 10_000)

    def test_mcc_reduces_deductible_interest(self):
        # With a 15% MCC, only 85% of interest is deductible; the credit
        # itself is dollar-for-dollar.
        r = compute(scenario_600k(mcc_pct=15))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.y_mcc, y1.y_interest * 0.15, places=6)
        self.assertAlmostEqual(
            y1.y_itemized,
            y1.y_interest * 0.85 + min(y1.y_property_tax, 40_400),
            places=6,
        )

    def test_standard_deduction_inflates(self):
        r = compute(scenario_600k())
        self.assertAlmostEqual(
            r.years[9].y_baseline_deduction,
            32_200 * 1.025 ** 9,
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
