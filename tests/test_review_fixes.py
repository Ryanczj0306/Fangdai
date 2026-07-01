"""Regression tests for defects confirmed by the adversarial review.

Each test names the finding it guards against.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
from fangdai import Inputs, compute  # noqa: E402


class CharityBaselineTests(unittest.TestCase):
    """A big giver itemizes even without the house — charity must not be
    credited to buying."""

    def test_charity_above_std_sets_baseline_to_charity(self):
        r = compute(Inputs(home_price=400_000, charity=100_000,
                           tax_rate_pct=24, extra_pay=0))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.y_baseline_deduction, 100_000, places=6)
        # Incremental benefit is only interest + SALT (the house's own
        # deductions), not the charity.
        expected = (y1.y_itemized - 100_000) * 0.24
        self.assertAlmostEqual(y1.y_benefit, expected, places=6)

    def test_small_charity_keeps_std_plus_atl_baseline(self):
        r = compute(Inputs(home_price=400_000, charity=10_000,
                           tax_rate_pct=24, extra_pay=0))
        self.assertAlmostEqual(
            r.years[0].y_baseline_deduction, 32_200 + 2_000, places=6,
        )

    def test_huge_charity_yields_only_house_deductions(self):
        # An already-itemizing taxpayer (charity $1M >> std deduction) gets
        # the FULL marginal value of the house's own deductions — but not a
        # penny of the charity credited to buying. The phantom benefit was
        # (charity - std - 2000) x rate ≈ $232k/yr; the correct benefit is
        # (interest + SALT) x rate ≈ $5.8k/yr.
        r = compute(Inputs(home_price=400_000, down_pct=20, apr=6.5,
                           extra_pay=0, tax_rate_pct=24, charity=1_000_000))
        y1 = r.years[0]
        self.assertAlmostEqual(y1.y_baseline_deduction, 1_000_000, places=6)
        house_deductions = y1.y_itemized - 1_000_000  # interest + capped SALT
        self.assertAlmostEqual(y1.y_benefit, house_deductions * 0.24, places=6)
        self.assertLess(y1.y_benefit, 7_000)  # ~5.8k, NOT ~232k


class CashFlowRoutingTests(unittest.TestCase):
    """One routing rule for all regimes: whoever pays less invests the diff."""

    ALL_CASH = dict(home_price=300_000, down_pct=100, extra_pay=0,
                    hoa=100, insurance=2_400, maintenance=2_000)

    def test_rent_level_affects_all_cash_verdict(self):
        low = compute(Inputs(**self.ALL_CASH, rent=300))
        high = compute(Inputs(**self.ALL_CASH, rent=1_300))
        # Low rent must favor the renter: advantage strictly lower.
        self.assertLess(
            low.years[19].advantage, high.years[19].advantage,
        )

    def test_renter_portfolio_never_negative(self):
        # Cheap house at 0% APR used to drive the renter to -$millions via
        # implicit margin borrowing.
        r = compute(Inputs(home_price=30_000, down_pct=20, apr=0,
                           extra_pay=0, rent=2_000, hoa=0,
                           insurance=600, maintenance=400))
        for row in r.years:
            self.assertGreaterEqual(row.renter_value, 0, f"year {row.y}")
            self.assertGreaterEqual(row.buyer_stk, 0, f"year {row.y}")

    def test_buyer_surplus_is_taxed_at_exit(self):
        # Pre-payoff buyer surplus now accrues to buyer_stk and pays LTCG.
        r = compute(Inputs(home_price=120_000, down_pct=20, apr=5.0,
                           extra_pay=0, rent=2_500, hoa=0, insurance=1_200,
                           maintenance=800, ltcg_rate_pct=15,
                           tax_rate_pct=24))
        row = r.years[9]
        self.assertGreater(row.buyer_stk, 0)
        self.assertGreater(row.buyer_exit_tax, 0)


class InputValidationTests(unittest.TestCase):
    def test_loan_years_zero_does_not_crash(self):
        r = compute(Inputs(loan_years=0))
        self.assertEqual(r.inputs["loan_years"], 1)

    def test_negative_costs_clamped_to_zero(self):
        neg = compute(Inputs(home_price=400_000, down_pct=20, apr=6.5,
                             extra_pay=0, hoa=-100, insurance=-5_000,
                             maintenance=-1_000))
        zero = compute(Inputs(home_price=400_000, down_pct=20, apr=6.5,
                              extra_pay=0, hoa=0, insurance=0, maintenance=0))
        self.assertAlmostEqual(
            neg.years[9].advantage, zero.years[9].advantage, places=6,
        )

    def test_all_cash_reports_zero_monthly_payment(self):
        r = compute(Inputs(home_price=300_000, down_pct=100))
        self.assertEqual(r.monthly_payment, 0.0)
        self.assertIsNone(r.payoff_year)

    def test_forty_year_loan_payoff_reported_honestly(self):
        r = compute(Inputs(home_price=400_000, down_pct=20, apr=6.5,
                           loan_years=40, extra_pay=0))
        # Standard 40y amortization pays off in year 40 — not a fake "30".
        self.assertEqual(r.payoff_year, 40)


if __name__ == "__main__":
    unittest.main()
