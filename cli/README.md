# Fangdai CLI

A Python CLI version of the [Buy vs Rent investment calculator](../index.html). Same model as the web app, runs in your terminal — useful for scripting, comparing scenarios, or piping JSON into other tools.

**No dependencies.** Pure Python 3.10+. No `pip install` required.

## Quick start

```bash
# default scenario (matches index.html defaults — Texas-style, 5% down with 5% credit, $3500/mo extra)
python fangdai.py

# any input from index.html is exposed as a flag
python fangdai.py --home-price 500000 --down-pct 20 --apr 6.5 --horizon 15

# Chinese output
python fangdai.py --lang zh

# print all 30 yearly rows instead of milestone-only
python fangdai.py --full

# emit JSON for scripting / dashboards
python fangdai.py --json > scenario.json
```

## Output

Text mode shows the same things as the web app's report:

- Monthly payment (standard + actual if you set `--extra-pay`)
- Estimated payoff year
- Breakeven year (when buying overtakes renting+investing)
- Cumulative buying-side costs & tax benefits at your horizon
- Renting + stock-investing portfolio at your horizon
- Sell-at-year-N P&L breakdown
- Year-by-year table at milestone years

JSON mode (`--json`) emits the full result including all 30 year rows.

## All flags

```
--home-price             Home price ($)
--down-pct               Down payment percent (>=3)
--loan-credit-pct        Loan credit percent (FTHB/builder)
--down-pay-by-credit     Treat credits as paying down payment (default: on)
--no-down-pay-by-credit  Treat credits as principal reduction
--apr                    Annual rate %
--loan-years             Loan term in years
--extra-pay              Custom monthly payment ($); 0 disables
--prop-tax-pct           Property tax %
--homestead              Homestead exemption $
--hoa                    HOA $/mo
--pmi                    PMI $/mo while LTV<80% (default 315)
--insurance              Insurance $/yr
--maintenance            Maintenance $/yr
--tax-rate-pct           Marginal federal tax rate %
--mcc-pct                MCC certificate rate (0-100); default 0
--std-deduction          Standard deduction $/yr (default 32200 — 2026 MFJ)
--salt-cap               SALT deduction cap $/yr (default 40400 — OBBBA 2026)
--charity                Charitable cash giving $/yr (default 0)
--inflation-pct          Inflation %/yr, grows the standard deduction (default 2.5)
--rent                   Rent $/mo year 1
--rent-growth-pct        Annual rent growth %
--stock-return-pct       Stock annualized return %
--house-return-pct       Home appreciation %/yr
--horizon                Selected horizon, 1..30
--lang                   zh | en
--json                   Emit JSON instead of text
--full                   Print all 30 yearly rows in text mode
```

## Model notes

Same as the web app:

- Mortgage amortized monthly: `interest = remaining_principal × monthly_rate`
- PMI applies until equity (down payment + cumulative principal) reaches 20% of home price
- **Tax benefit is incremental over the standard deduction**: itemized =
  interest-after-MCC + `min(property_tax, SALT cap)` + charity; savings =
  `max(0, itemized − baseline) × marginal_rate`, where the baseline is the
  (inflating) standard deduction plus the OBBBA non-itemizer charity deduction
  (≤ $2,000 MFJ). If itemized never clears the standard deduction, buying adds
  **$0** in tax savings.
- MCC (default 0% — income limits disqualify most buyers) credits a share of
  interest and removes it from deductible interest. Taxes are computed on
  annual totals, then smoothed into monthly cash flow as 1/12 per month.
- After payoff: only holding costs (PT + HOA + insurance + maintenance). If rent exceeds holding cost, the difference is invested by the buyer.
- Sale assumes 7% selling cost.

## Verifying parity with the web app

The CLI is a port of `computeModel()` in `index.html` (the block between the
`FANGDAI-ENGINE-BEGIN/END` markers). **If you change one, change the other.**
Parity is enforced by `tests/test_parity.py`, which extracts the JS engine,
runs it under Node.js, and compares every year row against the CLI within
1e-9. Run the whole suite from the repo root:

```bash
python3 -m unittest discover -s tests
```
