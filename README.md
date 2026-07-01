# Fangdai — Buy vs Rent + DFW house-hunt toolkit

Two related tools for thinking through buying a home in the Dallas / Fort Worth area:

1. **Buy vs Rent investment calculator** — bilingual (中文 / English) single-page web app, plus a Python CLI of the same model. Texas-style inputs (homestead exemption, MCC, builder/FTHB credits, PMI). Compares mortgage amortization + sale proceeds against rent + invest-the-difference in stocks.
2. **`house-hunt/`** — a scripted Redfin scraper + interactive Folium map of active listings inside [TSAHC](https://www.tsahc.org/) Targeted Areas within a configurable DFW commute corridor.

## Buy vs Rent calculator

**Web (no install):** [https://ryanczj0306.github.io/Fangdai/](https://ryanczj0306.github.io/Fangdai/)

Or open [`index.html`](./index.html) directly in your browser.

**CLI:** see [`cli/`](./cli/). Pure Python 3.10+, no dependencies.

```bash
python cli/fangdai.py                                # default Texas-style scenario
python cli/fangdai.py --home-price 500000 --apr 6.5  # override any input
python cli/fangdai.py --lang zh --full               # Chinese, full 30-year table
python cli/fangdai.py --json > scenario.json         # machine-readable output
```

Both versions use the same model (mortgage amortized monthly, MCC adjusts deductible interest, PMI dropped at 80% LTV, sale assumes 7% selling cost). See [`cli/README.md`](./cli/README.md) for all flags.

### Defaults (current scenario)

| Input | Value | | Input | Value |
| --- | --- | --- | --- | --- |
| Home price | `400000` | | Property tax | `2.2%` |
| Down payment | `5%` | | Homestead exemption | `140000` |
| Loan credit | `5%` | | HOA | `400/month` |
| APR | `5.0%` | | Insurance | `4800/year` |
| Loan term | `30 years` | | Maintenance | `3500/year` |
| Extra monthly | `3500` | | Tax rate | `20%` |
| Down paid by credits | `yes` | | MCC | `0%` |
| Standard deduction | `32200/yr` (2026 MFJ) | | SALT cap | `40400/yr` (OBBBA 2026) |
| Charity | `0/yr` | | Inflation | `2.5%` |
| Rent | `2000/month` | | Rent growth | `3%` |
| Stock return | `8%` | | Home appreciation | `4%` |
| Horizon | `20 years` | | | |

### Model notes

- Monthly amortization: `interest = remaining_principal × monthly_rate`.
- PMI applies until equity (down payment + cumulative principal) ≥ 20% of home price.
- **Tax benefit is incremental over the standard deduction.** Itemized
  deductions = interest-after-MCC + `min(property_tax, SALT cap)` + charity.
  They only save tax on the portion above the baseline (the standard
  deduction, inflating yearly, plus the OBBBA non-itemizer charity deduction
  of up to $2,000 MFJ): `savings = max(0, itemized − baseline) × marginal_rate`.
  A buyer whose itemized total never clears the standard deduction gets **$0**
  from the mortgage-interest deduction.
- MCC (default **0%** — programs have income limits most buyers exceed) credits
  a share of interest dollar-for-dollar and removes it from deductible interest.
- After payoff: only holding costs remain. If rent exceeds holding cost, the difference is invested by the buyer.
- Sale assumes 7% selling cost.

## DFW house-hunt tool

See [`house-hunt/README.md`](./house-hunt/README.md). Scoped to DFW + TSAHC Targeted Areas. Ships with a sample CSV and pre-built interactive map; refreshing requires hitting Redfin's (undocumented) GIS endpoint.

```bash
cd house-hunt
pip install -r requirements.txt
python build_map.py        # regenerate the map from the committed sample CSV
open output/listings_map.html
```

## Repo layout

```
Fangdai/
├── index.html              # web Buy vs Rent calculator
├── cli/
│   ├── fangdai.py          # Python CLI mirror of the web calculator
│   └── README.md
└── house-hunt/             # DFW listings → TSAHC targeted-area map
    ├── corridor_pipeline_v4.py
    ├── analyze_v4.py
    ├── build_map.py
    ├── tsahc_official.py
    ├── data/               # cached TSAHC polygons + tract→city map
    └── output/             # sample CSV + pre-built map
```

## Deploying the web calculator to GitHub Pages

The web calculator is a single file at the repo root. Settings → Pages → deploy from `main` branch, folder `/ (root)`.

## License

[MIT](./LICENSE) — © 2026 Zijian Chen. Use, modify, redistribute freely; no warranty.

## Disclaimer

- The Buy vs Rent calculator is a planning aid, **not financial advice**. Verify any scenario against your lender's actual numbers and your own tax situation before making a decision.
- The `house-hunt/` tool scrapes Redfin's undocumented `gis-csv` endpoint. Read [`house-hunt/README.md → Acceptable use & TOS notice`](./house-hunt/README.md#acceptable-use--tos-notice) before running it. The committed sample CSV/HTML let you explore the map without scraping anything.
- This repo is not affiliated with Redfin, TSAHC, or any other entity.
