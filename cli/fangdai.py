#!/usr/bin/env python3
"""Fangdai CLI — Buy vs Rent investment calculator.

Mirrors the calculation in index.html so terminal output matches the web app.

Run with the README's default scenario:

    python fangdai.py

Override any input from the command line:

    python fangdai.py --home-price 500000 --down-pct 20 --apr 6.5 --horizon 15

JSON output (for scripts/dashboards):

    python fangdai.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional

# OBBBA (2026, MFJ): non-itemizers may deduct up to $2,000/yr of cash charity
# above the line. Itemizers include charity in itemized deductions instead.
CHARITY_ATL_CAP = 2_000.0


# -------- inputs --------
@dataclass
class Inputs:
    home_price: float = 400_000
    down_pct: float = 5.0          # >= 3
    loan_credit_pct: float = 5.0   # 0-100
    down_pay_by_credit: bool = True
    apr: float = 5.0
    loan_years: int = 30
    extra_pay: float = 3_500       # custom monthly payment (>= mp_min); 0 disables
    prop_tax_pct: float = 2.2
    homestead: float = 140_000
    hoa: float = 400               # $/mo
    pmi: float = 315               # $/mo when LTV < 80%
    insurance: float = 4_800       # $/yr
    maintenance: float = 3_500     # $/yr
    tax_rate_pct: float = 20.0     # marginal federal
    mcc_pct: float = 0.0           # MCC rate; default 0 — most buyers don't qualify
    std_deduction: float = 32_200  # standard deduction $/yr (2026 MFJ); inflates yearly
    salt_cap: float = 40_400       # SALT deduction cap $/yr (OBBBA, 2026)
    charity: float = 0.0           # charitable cash giving $/yr
    inflation_pct: float = 2.5     # general inflation; grows the standard deduction
    selling_cost_pct: float = 6.0  # sale transaction cost % of home value
    closing_cost_pct: float = 3.0  # purchase closing costs % of home price
    ltcg_rate_pct: float = 15.0    # long-term cap-gains rate (18.8 with NIIT)
    sec121_cap: float = 500_000    # §121 primary-home exclusion (MFJ; 250k single)
    rent: float = 2_000            # $/mo, year 1
    rent_growth_pct: float = 3.0
    stock_return_pct: float = 8.0
    house_return_pct: float = 4.0
    horizon: int = 20              # 1..30
    lang: str = "en"               # zh|en

    def normalize(self) -> "Inputs":
        self.down_pct = max(3.0, self.down_pct)
        self.pmi = max(0.0, self.pmi)
        self.mcc_pct = max(0.0, min(100.0, self.mcc_pct))
        self.loan_credit_pct = max(0.0, min(100.0, self.loan_credit_pct))
        self.std_deduction = max(0.0, self.std_deduction)
        self.salt_cap = max(0.0, self.salt_cap)
        self.charity = max(0.0, self.charity)
        self.selling_cost_pct = max(0.0, min(100.0, self.selling_cost_pct))
        self.closing_cost_pct = max(0.0, min(100.0, self.closing_cost_pct))
        self.ltcg_rate_pct = max(0.0, min(100.0, self.ltcg_rate_pct))
        self.sec121_cap = max(0.0, self.sec121_cap)
        self.horizon = max(1, min(30, self.horizon))
        return self


# -------- per-year output --------
@dataclass
class YearRow:
    y: int
    home_value: float
    loan_balance: float
    sale_proceeds: float           # home value net of selling_cost_pct
    buyer_after_sale: float        # cash + buyerStk (pre-tax)
    renter_value: float            # stk (pre-tax)
    advantage: float               # buyer_after_sale - renter_value (pre-tax)
    buyer_exit_tax: float          # LTCG on (§121-excess home gain + buyer stock gain)
    renter_exit_tax: float         # LTCG on renter's stock gain if liquidated
    buyer_after_tax: float         # buyer_after_sale - buyer_exit_tax
    renter_after_tax: float        # renter_value - renter_exit_tax
    advantage_after_tax: float     # buyer_after_tax - renter_after_tax
    y_principal: float
    y_interest: float
    y_property_tax: float
    y_other: float                 # HOA + ins + mnt + PMI
    y_mcc: float
    y_itemized: float              # interest-after-MCC + SALT-capped prop tax + charity
    y_baseline_deduction: float    # inflated standard deduction (+ non-itemizer charity)
    itemizing: bool                # True if itemizing beats the standard deduction
    y_tax_deduction_savings: float # (itemized - baseline, floored at 0) x marginal rate
    y_benefit: float
    y_net_cost: float              # int + PT + other - benefit
    y_rent_total: float
    cum_principal: float
    cum_interest: float
    cum_property_tax: float
    cum_other: float
    cum_mcc: float
    cum_tax_dedn: float
    cum_benefit: float
    cum_net_cost: float
    cum_rent: float
    cum_invested_renter: float
    cum_invested_buyer: float
    renter_stk: float              # stk
    buyer_stk: float


@dataclass
class Result:
    inputs: dict
    monthly_payment: float
    monthly_payment_min: float
    down_payment: float
    loan: float
    credit_amount: float
    closing_costs: float
    renter_initial: float          # buyer's upfront cash (incl. closing costs)
    payoff_year: Optional[int]
    breakeven_year: Optional[int]            # pre-tax
    breakeven_year_after_tax: Optional[int]  # with §121 + LTCG at exit
    years: list[YearRow] = field(default_factory=list)


# -------- core calculation (mirrors index.html calculate()) --------
def compute(I: Inputs) -> Result:
    I = I.normalize()
    total_down_pct = max(3.0, I.down_pct)
    down_pay = I.home_price * total_down_pct / 100.0
    loan = max(0.0, I.home_price - down_pay)
    credit_amount = I.home_price * min(I.loan_credit_pct, total_down_pct) / 100.0
    # Closing costs are cash the buyer pays at purchase on top of the down
    # payment; the renter invests the same total upfront cash instead.
    closing_costs = I.home_price * I.closing_cost_pct / 100.0
    renter_initial = (
        I.home_price * max(0.0, total_down_pct / 100.0 - I.loan_credit_pct / 100.0)
        if I.down_pay_by_credit else down_pay
    ) + closing_costs

    mr = I.apr / 100.0 / 12.0
    np_months = I.loan_years * 12

    if loan > 0 and mr > 0:
        p = (1 + mr) ** np_months
        mp_min = loan * mr * p / (p - 1)
    elif loan > 0:
        mp_min = loan / np_months
    else:
        mp_min = 0.0

    mp = I.extra_pay if (I.extra_pay > 0 and I.extra_pay >= mp_min) else mp_min

    smr = (1 + I.stock_return_pct / 100.0) ** (1.0 / 12.0) - 1.0
    tx_r = I.tax_rate_pct / 100.0
    mcc_rate = I.mcc_pct / 100.0

    bal = loan
    stk = renter_initial
    buyer_stk = 0.0
    cP = cInt = cPT = cOth = cMCC = cTxDed = cRent = 0.0
    c_invested = renter_initial
    c_buyer_invested = 0.0
    cum_prin = 0.0
    years: list[YearRow] = []

    for y in range(1, 31):
        infl = (1 + I.inflation_pct / 100.0) ** (y - 1)
        hvs = I.home_price * (1 + I.house_return_pct / 100.0) ** (y - 1)
        hve = I.home_price * (1 + I.house_return_pct / 100.0) ** y
        taxable = max(0.0, hvs - I.homestead)
        y_pt = taxable * I.prop_tax_pct / 100.0
        m_pt = y_pt / 12.0
        cur_rent = I.rent * (1 + I.rent_growth_pct / 100.0) ** (y - 1)
        y_rent = cur_rent * 12.0
        # Holding costs grow with inflation (rent already grows; keeping these
        # flat silently favored buying on long horizons). PMI stays nominal.
        hoa_m = I.hoa * infl
        ins_y = I.insurance * infl
        mnt_y = I.maintenance * infl

        # Pass 1 — this year's amortization schedule, side-effect free, so the
        # tax benefit can be computed on ANNUAL totals (deductions are annual
        # constructs: the standard-deduction floor and SALT cap don't decompose
        # into months).
        tb = bal
        sched: list[tuple[float, float]] = []
        y_int = 0.0
        for _ in range(12):
            m_int_s = m_prin_s = 0.0
            if tb > 0.01:
                m_int_s = tb * mr
                pay_s = min(mp, tb + m_int_s)
                m_prin_s = min(pay_s - m_int_s, tb)
                tb = max(0.0, tb - m_prin_s)
            sched.append((m_int_s, m_prin_s))
            y_int += m_int_s

        # Annual tax math. MCC (if any) is a credit on a share of interest;
        # only the remainder is deductible. Itemizing only helps by the amount
        # it EXCEEDS the taxpayer's baseline: the (inflating) standard
        # deduction plus the OBBBA non-itemizer charity deduction.
        y_mcc = y_int * mcc_rate
        ded_int = max(0.0, y_int - y_mcc)
        salt_ded = min(y_pt, I.salt_cap)
        y_itemized = ded_int + salt_ded + I.charity
        std_y = I.std_deduction * infl
        y_baseline = std_y + min(I.charity, CHARITY_ATL_CAP)
        itemizing = y_itemized > y_baseline
        y_tx_ded = max(0.0, y_itemized - y_baseline) * tx_r
        m_benefit = (y_mcc + y_tx_ded) / 12.0  # smoothed into monthly cash flow

        # Pass 2 — replay the 12 months applying real cash flows.
        y_prin = y_pmi = 0.0
        for m_int, m_prin in sched:
            m_pay = m_int + m_prin
            bal = max(0.0, bal - m_prin)
            cum_prin += m_prin
            y_prin += m_prin

            pmi = I.pmi if (down_pay + cum_prin < 0.2 * I.home_price) else 0.0
            y_pmi += pmi

            total_buy = m_pay + m_pt + hoa_m + ins_y / 12.0 + mnt_y / 12.0 + pmi
            net_buy = total_buy - m_benefit

            stk *= (1 + smr)
            buyer_stk *= (1 + smr)

            if m_pay > 0:
                diff = net_buy - cur_rent
                c_invested += diff
                stk += diff
            else:
                buyer_diff = max(0.0, cur_rent - net_buy)
                c_buyer_invested += buyer_diff
                buyer_stk += buyer_diff

        y_other = hoa_m * 12 + ins_y + mnt_y + y_pmi
        cP += y_prin
        cInt += y_int
        cPT += y_pt
        cOth += y_other
        cMCC += y_mcc
        cTxDed += y_tx_ded
        cRent += y_rent
        y_benefit = y_mcc + y_tx_ded
        c_benefit = cMCC + cTxDed
        y_net_cost = y_int + y_pt + y_other - y_benefit
        c_net_cost = cInt + cPT + cOth - c_benefit

        sale = hve * (1 - I.selling_cost_pct / 100.0)
        bw = sale - max(0.0, bal)
        bt = bw + buyer_stk
        adv = bt - stk

        # After-tax exit if both parties liquidate at end of year y:
        # the buyer's primary-home gain is §121-exempt up to sec121_cap
        # (2-of-5-years ownership+use, so no exclusion in year 1); stock
        # gains on BOTH sides are taxed at the LTCG rate. Contribution
        # totals are used as basis (approximation; withdrawals ignored).
        ltcg = I.ltcg_rate_pct / 100.0
        home_gain = sale - (I.home_price + closing_costs)
        excl = I.sec121_cap if y >= 2 else 0.0
        taxable_home_gain = max(0.0, home_gain - excl)
        buyer_stk_gain = max(0.0, buyer_stk - c_buyer_invested)
        buyer_exit_tax = (taxable_home_gain + buyer_stk_gain) * ltcg
        renter_exit_tax = max(0.0, stk - c_invested) * ltcg
        bt_at = bt - buyer_exit_tax
        rw_at = stk - renter_exit_tax
        adv_at = bt_at - rw_at

        years.append(YearRow(
            y=y,
            home_value=hve,
            loan_balance=max(0.0, bal),
            sale_proceeds=sale,
            buyer_after_sale=bt,
            renter_value=stk,
            advantage=adv,
            buyer_exit_tax=buyer_exit_tax,
            renter_exit_tax=renter_exit_tax,
            buyer_after_tax=bt_at,
            renter_after_tax=rw_at,
            advantage_after_tax=adv_at,
            y_principal=y_prin,
            y_interest=y_int,
            y_property_tax=y_pt,
            y_other=y_other,
            y_mcc=y_mcc,
            y_itemized=y_itemized,
            y_baseline_deduction=y_baseline,
            itemizing=itemizing,
            y_tax_deduction_savings=y_tx_ded,
            y_benefit=y_benefit,
            y_net_cost=y_net_cost,
            y_rent_total=y_rent,
            cum_principal=cP,
            cum_interest=cInt,
            cum_property_tax=cPT,
            cum_other=cOth,
            cum_mcc=cMCC,
            cum_tax_dedn=cTxDed,
            cum_benefit=c_benefit,
            cum_net_cost=c_net_cost,
            cum_rent=cRent,
            cum_invested_renter=c_invested,
            cum_invested_buyer=c_buyer_invested,
            renter_stk=stk,
            buyer_stk=buyer_stk,
        ))

    # Independent payoff year (un-affected by bal mutations above)
    payoff_year: Optional[int] = None
    if loan > 0:
        b = loan
        mo = 0
        while b > 0.01 and mo < 360:
            m_int_p = b * mr
            pay_p = min(mp, b + m_int_p)
            m_prin_p = min(pay_p - m_int_p, b)
            b -= m_prin_p
            mo += 1
        payoff_year = -(-mo // 12)  # ceil

    breakeven_year: Optional[int] = next((r.y for r in years if r.advantage >= 0), None)
    breakeven_year_after_tax: Optional[int] = next(
        (r.y for r in years if r.advantage_after_tax >= 0), None,
    )

    return Result(
        inputs=asdict(I),
        monthly_payment=mp,
        monthly_payment_min=mp_min,
        down_payment=down_pay,
        loan=loan,
        credit_amount=credit_amount,
        closing_costs=closing_costs,
        renter_initial=renter_initial,
        payoff_year=payoff_year,
        breakeven_year=breakeven_year,
        breakeven_year_after_tax=breakeven_year_after_tax,
        years=years,
    )


# -------- formatting --------
def _fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    return f"{sign}${x:,.0f}"


def _T(zh: str, en: str, lang: str) -> str:
    return zh if lang == "zh" else en


def render_text(r: Result, full_table: bool = False, after_tax: bool = False) -> str:
    I = r.inputs
    lang = I.get("lang", "en")
    py = I["horizon"]
    s = r.years[py - 1]
    y1 = r.years[0]

    eff_rate_pct = (y1.y_property_tax / I["home_price"] * 100) if I["home_price"] else 0.0
    sc_pct = I.get("selling_cost_pct", 6.0)
    sale_fee = s.home_value * sc_pct / 100.0
    sale_income = s.home_value - sale_fee
    cash_after_sale = sale_income - s.loan_balance
    buyer_total_asset = cash_after_sale + s.buyer_stk

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(_T("Fangdai 房贷买房 vs 租房+投资 计算器", "Fangdai — Buy vs Rent + Invest Calculator", lang))
    lines.append("=" * 72)
    lines.append(_T(
        f"房价 {_fmt_money(I['home_price'])} · 首付 {I['down_pct']:.1f}%"
        f" · 贷款 {_fmt_money(r.loan)} · APR {I['apr']:.2f}% · {I['loan_years']}年",
        f"Price {_fmt_money(I['home_price'])} · Down {I['down_pct']:.1f}%"
        f" · Loan {_fmt_money(r.loan)} · APR {I['apr']:.2f}% · {I['loan_years']}y",
        lang,
    ))
    if r.credit_amount > 0:
        lines.append(_T(
            f"  贷款 credit: {_fmt_money(r.credit_amount)}"
            + ("（首付由 credits 抵扣）" if I["down_pay_by_credit"] else ""),
            f"  Loan credit: {_fmt_money(r.credit_amount)}"
            + (" (down paid via credits)" if I["down_pay_by_credit"] else ""),
            lang,
        ))
    lines.append("")

    custom_pay = I["extra_pay"] > 0 and I["extra_pay"] >= r.monthly_payment_min
    payoff_str = (
        _T(f"约 {r.payoff_year} 年还清", f"payoff in ~{r.payoff_year}y", lang)
        if r.payoff_year is not None else "—"
    )
    pay_label = _T("实际月供" if custom_pay else "标准月供",
                   "Actual payment" if custom_pay else "Standard payment", lang)
    lines.append(f"{pay_label}: {_fmt_money(r.monthly_payment)} "
                 f"({_T('最低', 'min', lang)} {_fmt_money(r.monthly_payment_min)} · {payoff_str})")

    lines.append("")
    lines.append(_T("★ 盈亏平衡（买房从哪一年开始赢）",
                    "★ BREAKEVEN — the year buying starts to win", lang))
    if r.breakeven_year is not None:
        lines.append(_T(
            f"  税前:        第 {r.breakeven_year} 年起买房领先",
            f"  Pre-tax:     buying wins from Year {r.breakeven_year}",
            lang,
        ))
    else:
        lines.append(_T(
            "  税前:        30 年内买房未领先（租房+投资更划算）",
            "  Pre-tax:     never within 30 years (renting+investing wins)",
            lang,
        ))
    if r.breakeven_year_after_tax is not None:
        lines.append(_T(
            f"  税后(§121):  第 {r.breakeven_year_after_tax} 年起买房领先（双方清仓口径）",
            f"  After-tax:   buying wins from Year {r.breakeven_year_after_tax} "
            f"(§121; both liquidate)",
            lang,
        ))
    else:
        lines.append(_T(
            "  税后(§121):  30 年内买房未领先（双方清仓口径）",
            "  After-tax:   never within 30 years (§121; both liquidate)",
            lang,
        ))
    lines.append("")

    lines.append(_T(
        f"实际房产税率（年1）: {eff_rate_pct:.2f}% （减免后 {_fmt_money(y1.y_property_tax)}/年）",
        f"Effective property tax (yr 1): {eff_rate_pct:.2f}% (after exemption {_fmt_money(y1.y_property_tax)}/yr)",
        lang,
    ))
    if y1.itemizing:
        lines.append(_T(
            f"税务（年1）: 逐项扣除 {_fmt_money(y1.y_itemized)} > 基准 {_fmt_money(y1.y_baseline_deduction)}"
            f"，超出部分抵税 {_fmt_money(y1.y_tax_deduction_savings)}/年",
            f"Tax (yr 1): itemized {_fmt_money(y1.y_itemized)} > baseline {_fmt_money(y1.y_baseline_deduction)}"
            f" — saves {_fmt_money(y1.y_tax_deduction_savings)}/yr",
            lang,
        ))
    else:
        lines.append(_T(
            f"税务（年1）: 逐项扣除 {_fmt_money(y1.y_itemized)} ≤ 标准扣除基准 {_fmt_money(y1.y_baseline_deduction)}"
            f"，买房不带来额外抵税（$0）",
            f"Tax (yr 1): itemized {_fmt_money(y1.y_itemized)} ≤ standard baseline {_fmt_money(y1.y_baseline_deduction)}"
            f" — buying adds $0 in tax savings",
            lang,
        ))
    lines.append("")
    lines.append("-" * 72)
    lines.append(_T(
        f"住 {py} 年累计 / 卖房盈亏",
        f"Cumulative after {py} years / sale P&L",
        lang,
    ))
    lines.append("-" * 72)

    # Buying side
    stock_gain = s.renter_stk - s.cum_invested_renter
    buyer_stock_gain = s.buyer_stk - s.cum_invested_buyer

    rows = [
        (_T("还贷本金（→ 权益）", "Principal paid (equity)", lang), _fmt_money(s.cum_principal)),
        (_T("贷款利息", "Mortgage interest", lang), _fmt_money(s.cum_interest)),
        (_T("房产税（减免后）", "Property tax (after exemption)", lang), _fmt_money(s.cum_property_tax)),
        (_T("HOA + PMI + 保险 + 维修", "HOA + PMI + Ins + Maint", lang), _fmt_money(s.cum_other)),
        (_T("MCC 抵免（credit）", "MCC tax credit", lang), "-" + _fmt_money(s.cum_mcc).lstrip("-")),
        (_T("逐项扣除超出标准部分的抵税", "Itemized-over-standard tax savings", lang),
            "-" + _fmt_money(s.cum_tax_dedn).lstrip("-")),
        (_T("还清后买房方差额累计投入", "Buyer post-payoff diff invested", lang),
            _fmt_money(s.cum_invested_buyer)),
        (_T("买房方差额投资收益", "Buyer diff investment gain", lang), _fmt_money(buyer_stock_gain)),
        (_T("买房方差额投资净值", "Buyer diff investment value", lang), _fmt_money(s.buyer_stk)),
        (_T("净成本（不含还本金）", "Net cost (excl. principal)", lang), _fmt_money(s.cum_net_cost)),
    ]
    lines.append(_T("买房 N 年累计:", "Buying — cumulative:", lang))
    for k, v in rows:
        lines.append(f"  {k:<46s} {v:>16s}")
    lines.append("")

    lines.append(_T("租房 + 投资 N 年:", "Renting + investing:", lang))
    rent_rows = [
        (_T(f"{py} 年累计租金", f"{py}-yr total rent", lang), _fmt_money(s.cum_rent)),
        (_T("买房净成本比租房多花", "Buy-net-cost minus rent", lang), _fmt_money(s.cum_net_cost - s.cum_rent)),
        (_T("初始投入股市（首付自付 + 过户费）",
             "Initial investment (out-of-pocket down + closing)", lang), _fmt_money(r.renter_initial)),
        (_T("每月差额累计投入", "Cumulative monthly diff invested", lang),
            _fmt_money(s.cum_invested_renter - r.renter_initial)),
        (_T(f"股市投资收益 ({I['stock_return_pct']:.1f}%/yr)",
             f"Stock gain ({I['stock_return_pct']:.1f}%/yr)", lang), _fmt_money(stock_gain)),
        (_T("股市投资总值", "Stock portfolio value", lang), _fmt_money(s.renter_stk)),
    ]
    for k, v in rent_rows:
        lines.append(f"  {k:<46s} {v:>16s}")
    lines.append("")

    lines.append(_T(f"卖房盈亏（按 {sc_pct:g}% 交易费）:", f"Sell P&L ({sc_pct:g}% selling cost):", lang))
    sell_rows = [
        (_T(f"房屋市值（第 {py} 年末）", f"Home value (end of yr {py})", lang), _fmt_money(s.home_value)),
        (_T(f"− 卖房交易费用 ({sc_pct:g}%)", f"− Selling cost ({sc_pct:g}%)", lang), "-" + _fmt_money(sale_fee).lstrip("-")),
        (_T("= 卖房收入", "= Sale proceeds", lang), _fmt_money(sale_income)),
        (_T("− 剩余贷款余额", "− Remaining loan balance", lang), "-" + _fmt_money(s.loan_balance).lstrip("-")),
        (_T("= 卖房现金到手", "= Cash after sale", lang), _fmt_money(cash_after_sale)),
        (_T("+ 买房方投资净值", "+ Buyer investment value", lang), _fmt_money(s.buyer_stk)),
        (_T("= 买房方总净值 (A)", "= Buyer total net asset (A)", lang), _fmt_money(buyer_total_asset)),
        (_T("租房+投资净值 (B)", "Renter net value (B)", lang), _fmt_money(s.renter_stk)),
        (_T("买房盈亏 = A − B", "Buy P&L = A − B", lang), _fmt_money(s.advantage)),
    ]
    for k, v in sell_rows:
        lines.append(f"  {k:<46s} {v:>16s}")
    lines.append("")

    ltcg_pct = I.get("ltcg_rate_pct", 15.0)
    lines.append(_T(
        f"税后退出（§121 主房免税 ≤ {_fmt_money(I.get('sec121_cap', 500_000))}，股票增值按 {ltcg_pct:g}% 缴税）:",
        f"After-tax exit (§121 home exclusion ≤ {_fmt_money(I.get('sec121_cap', 500_000))}; "
        f"stock gains taxed {ltcg_pct:g}%):",
        lang,
    ))
    at_rows = [
        (_T("− 买房方退出税（房+股）", "− Buyer exit tax (home + stocks)", lang),
            "-" + _fmt_money(s.buyer_exit_tax).lstrip("-")),
        (_T("= 买房方税后净值 (A′)", "= Buyer after-tax value (A′)", lang), _fmt_money(s.buyer_after_tax)),
        (_T("− 租房方资本利得税", "− Renter capital-gains tax", lang),
            "-" + _fmt_money(s.renter_exit_tax).lstrip("-")),
        (_T("= 租房方税后净值 (B′)", "= Renter after-tax value (B′)", lang), _fmt_money(s.renter_after_tax)),
        (_T("税后买房盈亏 = A′ − B′", "After-tax buy P&L = A′ − B′", lang), _fmt_money(s.advantage_after_tax)),
    ]
    for k, v in at_rows:
        lines.append(f"  {k:<46s} {v:>16s}")
    lines.append(_T(
        "  注：仅当双方在该年清仓时成立；租房方不卖股票则可无限期递延税负。",
        "  Note: assumes both parties liquidate that year; a renter who keeps "
        "holding defers the tax indefinitely.",
        lang,
    ))
    lines.append("")

    # Year-by-year table
    lines.append("-" * 72)
    lines.append(_T("逐年 (1-30):", "Year-by-year (1-30):", lang))
    lines.append("-" * 72)
    if not full_table:
        # show 1, 2, 3, 5, 10, 15, 20, 25, 30 + horizon
        keep = sorted({1, 2, 3, 5, 10, 15, 20, 25, 30, py})
        rows_show = [r.years[i - 1] for i in keep]
    else:
        rows_show = r.years

    if after_tax:
        hdr = (
            f"{'yr':>3s} {_T('房价','home',lang):>10s} {_T('贷款余额','balance',lang):>11s}"
            f" {_T('买房A′','buyer A′',lang):>11s}"
            f" {_T('租房B′','renter B′',lang):>11s} {_T('A′-B′','A′-B′',lang):>10s}"
        )
    else:
        hdr = (
            f"{'yr':>3s} {_T('房价','home',lang):>10s} {_T('贷款余额','balance',lang):>11s}"
            f" {_T('卖房现金','cash',lang):>10s} {_T('买房A','buyer A',lang):>11s}"
            f" {_T('租房B','renter B',lang):>11s} {_T('A-B','A-B',lang):>10s}"
        )
    lines.append(hdr)
    for yr in rows_show:
        marker = " *" if yr.y == py else ""
        if after_tax:
            lines.append(
                f"{yr.y:>3d} {_fmt_money(yr.home_value):>10s} "
                f"{_fmt_money(yr.loan_balance):>11s} "
                f"{_fmt_money(yr.buyer_after_tax):>11s} {_fmt_money(yr.renter_after_tax):>11s} "
                f"{_fmt_money(yr.advantage_after_tax):>10s}{marker}"
            )
        else:
            cash_y = yr.sale_proceeds - yr.loan_balance
            a = cash_y + yr.buyer_stk
            b = yr.renter_value
            lines.append(
                f"{yr.y:>3d} {_fmt_money(yr.home_value):>10s} "
                f"{_fmt_money(yr.loan_balance):>11s} {_fmt_money(cash_y):>10s} "
                f"{_fmt_money(a):>11s} {_fmt_money(b):>11s} {_fmt_money(a - b):>10s}{marker}"
            )

    lines.append("")
    lines.append(_T(
        "* 标记的年份是你设定的居住年限。",
        "* marks your selected horizon.",
        lang,
    ))
    return "\n".join(lines)


# -------- CLI --------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fangdai CLI — Buy vs Rent investment calculator (mirror of index.html).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    d = Inputs()
    p.add_argument("--home-price",          type=float, default=d.home_price)
    p.add_argument("--down-pct",            type=float, default=d.down_pct, help="Down payment percent (>=3)")
    p.add_argument("--loan-credit-pct",     type=float, default=d.loan_credit_pct, help="Loan credit percent (FTHB/builder)")
    p.add_argument("--down-pay-by-credit",  action=argparse.BooleanOptionalAction, default=d.down_pay_by_credit)
    p.add_argument("--apr",                 type=float, default=d.apr)
    p.add_argument("--loan-years",          type=int,   default=d.loan_years)
    p.add_argument("--extra-pay",           type=float, default=d.extra_pay, help="Custom monthly payment; 0 disables")
    p.add_argument("--prop-tax-pct",        type=float, default=d.prop_tax_pct)
    p.add_argument("--homestead",           type=float, default=d.homestead, help="Homestead exemption $")
    p.add_argument("--hoa",                 type=float, default=d.hoa,       help="HOA $/mo")
    p.add_argument("--pmi",                 type=float, default=d.pmi,       help="PMI $/mo while LTV<80%%")
    p.add_argument("--insurance",           type=float, default=d.insurance, help="$/yr")
    p.add_argument("--maintenance",         type=float, default=d.maintenance, help="$/yr")
    p.add_argument("--tax-rate-pct",        type=float, default=d.tax_rate_pct, help="Marginal tax rate %%")
    p.add_argument("--mcc-pct",             type=float, default=d.mcc_pct,
                   help="MCC certificate rate (0-100); default 0 — MCC programs have income "
                        "limits most buyers exceed")
    p.add_argument("--std-deduction",       type=float, default=d.std_deduction,
                   help="Standard deduction $/yr (2026 MFJ default; single ~$16,100); "
                        "grows with --inflation-pct")
    p.add_argument("--salt-cap",            type=float, default=d.salt_cap,
                   help="SALT deduction cap $/yr (OBBBA 2026; phases down above ~$505k MAGI)")
    p.add_argument("--charity",             type=float, default=d.charity,
                   help="Charitable cash giving $/yr (itemized when itemizing; otherwise "
                        "above-the-line up to $2,000 MFJ)")
    p.add_argument("--inflation-pct",       type=float, default=d.inflation_pct,
                   help="General inflation %%/yr — grows the standard deduction, HOA, "
                        "insurance, and maintenance")
    p.add_argument("--selling-cost-pct",    type=float, default=d.selling_cost_pct,
                   help="Sale transaction cost %% of home value (agent fees, etc.)")
    p.add_argument("--closing-cost-pct",    type=float, default=d.closing_cost_pct,
                   help="Purchase closing costs %% of price (title, origination, escrow)")
    p.add_argument("--ltcg-rate-pct",       type=float, default=d.ltcg_rate_pct,
                   help="Long-term capital-gains rate %% at exit (18.8 with NIIT; 0 disables)")
    p.add_argument("--sec121-cap",          type=float, default=d.sec121_cap,
                   help="§121 primary-home gain exclusion $ (500k MFJ / 250k single; "
                        "applies from year 2 — requires 2 years of ownership+use)")
    p.add_argument("--rent",                type=float, default=d.rent,      help="$/mo, year 1")
    p.add_argument("--rent-growth-pct",     type=float, default=d.rent_growth_pct)
    p.add_argument("--stock-return-pct",    type=float, default=d.stock_return_pct)
    p.add_argument("--house-return-pct",    type=float, default=d.house_return_pct)
    p.add_argument("--horizon",             type=int,   default=d.horizon, help="Years 1..30")
    p.add_argument("--lang",                choices=["zh", "en"], default=d.lang)
    p.add_argument("--json",  dest="as_json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument("--full",  action="store_true", help="Print all 30 yearly rows in text mode")
    p.add_argument("--after-tax", action="store_true",
                   help="Year-by-year table shows after-tax values (§121 + LTCG at exit)")
    return p


def args_to_inputs(args: argparse.Namespace) -> Inputs:
    return Inputs(
        home_price=args.home_price,
        down_pct=args.down_pct,
        loan_credit_pct=args.loan_credit_pct,
        down_pay_by_credit=args.down_pay_by_credit,
        apr=args.apr,
        loan_years=args.loan_years,
        extra_pay=args.extra_pay,
        prop_tax_pct=args.prop_tax_pct,
        homestead=args.homestead,
        hoa=args.hoa,
        pmi=args.pmi,
        insurance=args.insurance,
        maintenance=args.maintenance,
        tax_rate_pct=args.tax_rate_pct,
        mcc_pct=args.mcc_pct,
        std_deduction=args.std_deduction,
        salt_cap=args.salt_cap,
        charity=args.charity,
        inflation_pct=args.inflation_pct,
        selling_cost_pct=args.selling_cost_pct,
        closing_cost_pct=args.closing_cost_pct,
        ltcg_rate_pct=args.ltcg_rate_pct,
        sec121_cap=args.sec121_cap,
        rent=args.rent,
        rent_growth_pct=args.rent_growth_pct,
        stock_return_pct=args.stock_return_pct,
        house_return_pct=args.house_return_pct,
        horizon=args.horizon,
        lang=args.lang,
    )


def main(argv: Optional[list[str]] = None) -> int:
    # Windows consoles default to cp1252; force utf-8 so Chinese / unicode dashes work.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    args = build_parser().parse_args(argv)
    I = args_to_inputs(args)
    r = compute(I)
    if args.as_json:
        out = asdict(r)
        out["years"] = [asdict(y) for y in r.years]
        print(json.dumps(out, indent=2))
    else:
        print(render_text(r, full_table=args.full, after_tax=args.after_tax))
    return 0


if __name__ == "__main__":
    sys.exit(main())
