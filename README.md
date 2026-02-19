# Buy vs Rent Investment Calculator

A lightweight single-page calculator for comparing:

- **Buying a home** (mortgage amortization, tax/fees, sale proceeds)
- **Renting + investing** (monthly cash-flow differences invested in stocks)

It supports bilingual UI (**中文 / English**) and is designed for Texas-style scenarios (property tax, homestead exemption, MCC, builder/FTHB credits).

## Try it out!!! https://ryanczj0306.github.io/Fangdai/
## Features

- Interactive input panel (home price, down payment, APR, tax/fees, rent, stock return, home appreciation)
- Optional **loan credit** (e.g., builder/FTHB incentive reducing principal)
- Optional **extra monthly payment** (pay off early)
- Optional **down payment paid by credits** (exclude from renter investable cash)
- 1-30 year horizon slider
- Charts and milestone tables
- Sell-at-year-N P&L breakdown table
- Bilingual toggle button (top-right)

## Quick Start

No build tools required.

1. Clone or download this repo
2. Open `index.html` directly in your browser

```bash
open index.html
```

You can also serve it locally (optional):

```bash
python3 -m http.server 8080
# then open http://localhost:8080
```

## Deploy to GitHub Pages

### Option A: Deploy root as static site

1. Push repository to GitHub
2. Go to **Settings -> Pages**
3. Under **Build and deployment**:
   - Source: `Deploy from a branch`
   - Branch: `main` (or your default), folder: `/ (root)`
4. Save and wait for deployment

Your site URL will appear in the Pages section.

### Option B: Use `/docs`

If you prefer Pages from `/docs`:

1. Move `index.html` into `docs/`
2. In **Settings -> Pages**, set folder to `/docs`

## Input Defaults (Current)

The app is initialized with the values from the latest user scenario:

- Home price: `400000`
- Down payment: `5%`
- Loan credit: `5%`
- APR: `5.0%`
- Loan term: `30 years`
- Extra monthly payment: `3500`
- Down payment paid by credits: `checked`
- Property tax: `2.2%`
- Homestead exemption: `140000`
- HOA: `400/month`
- Insurance: `4800/year`
- Maintenance: `3500/year`
- Tax rate: `20%`
- MCC: `2000/year`
- Rent: `2000/month`
- Rent growth: `3%`
- Stock return: `8%`
- Home appreciation: `4%`
- Horizon slider: `20 years`

## Model Notes

- Mortgage is amortized monthly.
- Monthly interest is computed as:
  - `interest = remaining_principal * monthly_rate`
- Sale proceeds assume a **7% selling cost**.
- Tax benefit includes:
  - MCC credit
  - deductible mortgage interest (after MCC adjustment)
  - deductible property tax
- With early payoff:
  - no further mortgage payment/interest
  - only holding costs remain (property tax, HOA, insurance, maintenance)
- Post-payoff logic supports allocating rent-vs-holding-cost difference to buyer-side investing (as implemented in current version).

## Customize

Everything is in a single file:

- `index.html`

You can modify:

- Defaults in the input elements
- Text labels and translations
- Financial assumptions and formula details in script section

