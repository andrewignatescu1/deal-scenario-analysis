

from dataclasses import dataclass
from typing import Dict, Tuple
import pandas as pd
import yfinance as yf


@dataclass
class Company:
    name: str
    ticker: str
    net_income: float 
    shares_out: float       
    price_per_share: float  


@dataclass
class Deal:
    target_equity_value: float     
    cash_pct: float
    stock_pct: float
    debt_pct: float
    acquirer_tax_rate: float
    debt_interest_rate: float
    one_time_costs: float
    one_time_costs_after_tax: bool
    annual_synergies_pretax: float
    synergy_realization: float
    amortization_pretax: float
    offer_premium: float          


def fetch_company(ticker: str) -> Company:
    t = yf.Ticker(ticker)
    info = t.info

    price = float(info.get("currentPrice") or info.get("regularMarketPrice"))


    shares = info.get("sharesOutstanding")
    if shares is None:
        raise ValueError(f"sharesOutstanding missing for {ticker}. Choose another ticker or use SEC method.")


    net_income = None
    try:
        fin = t.financials 
        for key in ["Net Income", "Net Income Common Stockholders", "Net Income Applicable To Common Shares"]:
            if key in fin.index:
                net_income = float(fin.loc[key].iloc[0])
                break
    except Exception:
        pass

    if net_income is None:
        # fallback
        net_income = info.get("netIncomeToCommon")
        if net_income is None:
            raise ValueError(f"Net income missing for {ticker}. Try SEC approach.")

    name = info.get("shortName") or ticker
    return Company(name=name, ticker=ticker, net_income=float(net_income), shares_out=float(shares), price_per_share=price)


def standalone_eps(acquirer: Company) -> float:
    return acquirer.net_income / acquirer.shares_out


def proforma_eps(acquirer: Company, target: Company, deal: Deal) -> Tuple[float, Dict[str, float]]:
    mix_sum = deal.cash_pct + deal.stock_pct + deal.debt_pct
    if abs(mix_sum - 1.0) > 1e-6:
        raise ValueError(f"Financing mix must sum to 1. Currently {mix_sum:.4f}")

    purchase_equity_value = deal.target_equity_value * (1.0 + deal.offer_premium)

    cash_used = purchase_equity_value * deal.cash_pct
    debt_raised = purchase_equity_value * deal.debt_pct
    stock_value = purchase_equity_value * deal.stock_pct

    new_shares = stock_value / acquirer.price_per_share if stock_value > 0 else 0.0

    interest_pretax = debt_raised * deal.debt_interest_rate
    interest_after_tax = interest_pretax * (1.0 - deal.acquirer_tax_rate)

    synergies_pretax_realized = deal.annual_synergies_pretax * deal.synergy_realization
    synergies_after_tax = synergies_pretax_realized * (1.0 - deal.acquirer_tax_rate)

    amort_after_tax = deal.amortization_pretax * (1.0 - deal.acquirer_tax_rate)

    one_time_after_tax = deal.one_time_costs if deal.one_time_costs_after_tax else deal.one_time_costs * (1.0 - deal.acquirer_tax_rate)

    proforma_net_income = (
        acquirer.net_income
        + target.net_income
        + synergies_after_tax
        - interest_after_tax
        - amort_after_tax
        - one_time_after_tax
    )

    proforma_shares = acquirer.shares_out + new_shares
    eps_pf = proforma_net_income / proforma_shares

    detail = {
        "purchase_equity_value": purchase_equity_value,
        "cash_used": cash_used,
        "debt_raised": debt_raised,
        "stock_value": stock_value,
        "new_shares": new_shares,
        "interest_after_tax": interest_after_tax,
        "synergies_after_tax": synergies_after_tax,
        "amort_after_tax": amort_after_tax,
        "one_time_after_tax": one_time_after_tax,
        "proforma_net_income": proforma_net_income,
        "proforma_shares": proforma_shares,
        "eps_proforma": eps_pf,
    }
    return eps_pf, detail


def accretion_dilution_pct(acquirer: Company, eps_pf: float) -> float:
    return (eps_pf / standalone_eps(acquirer) - 1.0) * 100.0


def run_scenarios(acquirer: Company, target: Company, deal: Deal) -> pd.DataFrame:
    scenarios = {
        "Base": deal,
        "Upside": Deal(**{**deal.__dict__,
            "synergy_realization": min(1.0, deal.synergy_realization + 0.20),
            "one_time_costs": deal.one_time_costs * 0.80,
            "debt_interest_rate": max(0.0, deal.debt_interest_rate - 0.01),
        }),
        "Downside": Deal(**{**deal.__dict__,
            "synergy_realization": max(0.0, deal.synergy_realization - 0.30),
            "one_time_costs": deal.one_time_costs * 1.50,
            "debt_interest_rate": deal.debt_interest_rate + 0.02,
        }),
    }

    rows = []
    for name, d in scenarios.items():
        eps_pf, det = proforma_eps(acquirer, target, d)
        acc = accretion_dilution_pct(acquirer, eps_pf)
        breaks = acc < -2.0  # example rule
        rows.append({
            "Scenario": name,
            "A Standalone EPS": standalone_eps(acquirer),
            "Pro Forma EPS": eps_pf,
            "Acc/Dil %": acc,
            "Breaks (< -2% dilutive)": breaks,
            "Synergies (AT)": det["synergies_after_tax"],
            "Interest (AT)": det["interest_after_tax"],
            "New Shares": det["new_shares"],
        })

    return pd.DataFrame(rows).set_index("Scenario")

def prompt_ticker(label: str, default: str) -> str:
    raw = input(f"{label} ticker (default {default}): ").strip().upper()
    return raw if raw else default

def prompt_float(label: str, default: float) -> float:
    raw = input(f"{label} (default {default}): ").strip()
    return float(raw) if raw else float(default)

def prompt_pct(label: str, default: float) -> float:
    """
    Accepts either:
      - 0.25 (already a fraction)
      - 25   (interpreted as percent)
    """
    raw = input(f"{label} (default {default}): ").strip()
    if not raw:
        return float(default)
    x = float(raw)
    return x / 100.0 if x > 1.0 else x

if __name__ == "__main__":
    print("\n=== Interactive Deal Scenario Analysis ===")
    acq = prompt_ticker("Acquirer", "JPM")
    tgt = prompt_ticker("Target", "CFG")

    print("\nPulling real market + financial data (yfinance)...")
    A = fetch_company(acq)
    B = fetch_company(tgt)

    premium = prompt_pct("Acquisition premium (e.g., 25 or 0.25)", 0.25)
    target_market_cap = B.shares_out * B.price_per_share
    target_equity_value = target_market_cap * (1.0 + premium)

    cash_pct = prompt_pct("Cash % of purchase price", 0.30)
    stock_pct = prompt_pct("Stock % of purchase price", 0.40)
    debt_pct = 1.0 - cash_pct - stock_pct 
    if debt_pct < 0:
        raise ValueError("Cash% + Stock% cannot exceed 100%.")

    tax_rate = prompt_pct("Acquirer tax rate", 0.24)
    debt_rate = prompt_pct("Debt interest rate (pre-tax)", 0.065)
    synergies = prompt_float("Annual synergies (pre-tax) $", 1_200_000_000)
    synergy_real = prompt_pct("Synergy realization (e.g., 60 or 0.60)", 0.60)
    one_time = prompt_float("One-time integration costs (pre-tax) $", 500_000_000)
    amort = prompt_float("Annual amortization (pre-tax) $", 400_000_000)

    deal = Deal(
        target_equity_value=target_equity_value,
        cash_pct=cash_pct,
        stock_pct=stock_pct,
        debt_pct=debt_pct,
        acquirer_tax_rate=tax_rate,
        debt_interest_rate=debt_rate,
        one_time_costs=one_time,
        one_time_costs_after_tax=False,
        annual_synergies_pretax=synergies,
        synergy_realization=synergy_real,
        amortization_pretax=amort,
        offer_premium=0.00,
    )

    print(f"\nAcquirer: {A.name} ({A.ticker}) | Price ${A.price_per_share:.2f} | Shares {A.shares_out:,.0f} | NI ${A.net_income:,.0f}")
    print(f"Target:   {B.name} ({B.ticker}) | Price ${B.price_per_share:.2f} | Shares {B.shares_out:,.0f} | NI ${B.net_income:,.0f}")
    print(f"Assumed purchase equity value: ${deal.target_equity_value:,.0f} (includes premium)\n")

    df = run_scenarios(A, B, deal)
    print(df.to_string(float_format=lambda x: f"{x:,.3f}" if abs(x) < 1e6 else f"{x:,.0f}"))