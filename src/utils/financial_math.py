"""Financial math utilities for Project PANA.

Provides pure-functions for balance-sheet analysis, ESG scoring,
risk metrics, and portfolio carbon intensity — used by both agents
and the dashboard.
"""

from __future__ import annotations
from typing import Optional


# ── Asset Composition ──────────────────────────────────────────────────────────

def green_ratio(green_assets: float, brown_assets: float) -> float:
    """Share of green assets in total portfolio (0–1)."""
    total = green_assets + brown_assets
    if total <= 0:
        return 0.0
    return green_assets / total


def brown_ratio(green_assets: float, brown_assets: float) -> float:
    """Share of brown assets in total portfolio (0–1)."""
    total = green_assets + brown_assets
    if total <= 0:
        return 0.0
    return brown_assets / total


def total_assets(green_assets: float, brown_assets: float) -> float:
    """Total portfolio asset value."""
    return green_assets + brown_assets


# ── Capital & Leverage ───────────────────────────────────────────────────────

def tier1_capital(cash: float, green_assets: float, liabilities: float) -> float:
    """Tier 1 Capital = Cash + Green_Assets − Liabilities (simplified Basel)."""
    return cash + green_assets - liabilities


def leverage_ratio_exposure(
    green_assets: float, brown_assets: float, tier1_capital: float
) -> float:
    """
    Leverage ratio = Total exposure / Tier 1 Capital.
    Basel III maximum ≈ 12× for Tier 1.
    """
    if tier1_capital <= 0:
        return float("inf")
    return (green_assets + brown_assets) / tier1_capital


def is_levied_constraint(
    green_assets: float, brown_assets: float, tier1_capital: float, max_ratio: float = 12.0
) -> bool:
    """True when leverage is within the Basel III limit."""
    return leverage_ratio_exposure(green_assets, brown_assets, tier1_capital) <= max_ratio


# ── Liquidity ─────────────────────────────────────────────────────────────────

def liquidity_gap(cash: float, liabilities: float, asset_value: float) -> float:
    """
    Liquidity gap = Liabilities − (Cash + 0.5 × AssetValue).
    Positive → net illiquid; negative → net liquid.
    """
    return liabilities - (cash + 0.5 * asset_value)


def liability_coverage_ratio(cash: float, liabilities: float) -> float:
    """Cash / Liabilities — how much immediate coverage exists."""
    if liabilities <= 0:
        return float("inf")
    return cash / liabilities


def cash_runway_months(cash: float, monthly_burn: float) -> float:
    """Months until cash exhausted at current burn rate."""
    if monthly_burn <= 0:
        return float("inf")
    return cash / monthly_burn


# ── ESG Score Helpers ─────────────────────────────────────────────────────────

def esg_from_green_ratio(green_assets: float, brown_assets: float) -> float:
    """
    Map green-asset ratio to an ESG score 40–100.
    Matches BasePanaAgent.update_esg_score logic as a pure function.
    """
    return 40.0 + 60.0 * green_ratio(green_assets, brown_assets)


def esg_to_rating(esg_score: float) -> str:
    """Convert numeric ESG score (0–100) to a letter rating."""
    if esg_score >= 90:
        return "AAA"
    elif esg_score >= 80:
        return "AA"
    elif esg_score >= 70:
        return "A"
    elif esg_score >= 60:
        return "BBB"
    elif esg_score >= 50:
        return "BB"
    elif esg_score >= 40:
        return "B"
    elif esg_score >= 20:
        return "CCC"
    else:
        return "D"


# ── Risk Metrics ─────────────────────────────────────────────────────────────

def panic_sell_probability(
    esg_score: float,
    cash: float,
    liabilities: float,
    base_risk_threshold: float = 0.05,
) -> float:
    """
    Probability of panic-selling based on:
    - ESG score deterioration (penalty up to +0.15)
    - Liability coverage deficit (penalty up to +0.10)
    """
    liability_coverage = liability_coverage_ratio(cash, liabilities)
    esg_factor = max(0.0, (100.0 - esg_score) / 100.0)
    risk = (
        base_risk_threshold
        + (1 - liability_coverage) * 0.1
        + esg_factor * 0.15
    )
    return min(max(risk, 0.0), 1.0)


def value_at_risk(
    portfolio_value: float,
    volatility: float,
    confidence_level: float = 0.95,
) -> float:
    """
    Parametric VaR under normal distribution.
    Default 95% confidence, daily-ish horizon.
    """
    import math
    z = {
        0.90: 1.282,
        0.95: 1.645,
        0.99: 2.326,
    }.get(confidence_level, 1.645)
    return portfolio_value * volatility * z


# ── Carbon ───────────────────────────────────────────────────────────────────

def carbon_tax_burden(
    carbon_liability: float, carbon_tax_rate: float
) -> float:
    """Annual carbon tax cost = tonnes CO₂ × rate (USD/tonne)."""
    return carbon_liability * carbon_tax_rate


def portfolio_carbon_intensity(
    green_assets: float, brown_assets: float, carbon_liability: float
) -> float:
    """
    Carbon intensity = carbon_liability / total_assets.
    Higher → more carbon-exposed per unit of assets.
    """
    ta = total_assets(green_assets, brown_assets)
    if ta <= 0:
        return 0.0
    return carbon_liability / ta


def transition_readiness_score(
    green_assets: float,
    brown_assets: float,
    green_capex: float,
    revenue: float,
) -> float:
    """
    Score 0–1: how ready is this firm for green transition?
    = 0.5 × green_asset_ratio + 0.5 × capex_ratio
    Matches FirmAgent.assess_transition_readiness.
    """
    ta = total_assets(green_assets, brown_assets)
    green_asset_ratio = green_assets / max(ta, 1e-9)
    capex_ratio = green_capex / max(revenue, 1e-9)
    return 0.5 * green_asset_ratio + 0.5 * capex_ratio


# ── Shock & Contagion ─────────────────────────────────────────────────────────

def brown_asset_shock(
    brown_assets: float, shock_intensity: float
) -> float:
    """Apply an exogenous brown-asset price drop."""
    return brown_assets * (1.0 - max(0.0, min(1.0, shock_intensity)))


def cascade_probability(
    price_shock: float, liquidation_threshold: float, base_prob: float = 0.35
) -> float:
    """
    Probability that a neighbour gets caught in a cascade,
    given the size of the price shock relative to the threshold.
    """
    if price_shock < liquidation_threshold:
        return 0.0
    return min(base_prob + (price_shock - liquidation_threshold), 1.0)


# ── Green Bond Pricing ───────────────────────────────────────────────────────

def green_bond_spread(
    esg_score: float,
    base_spread: float = 0.02,
    max_spread: float = 0.10,
) -> float:
    """
    Green bond spread over risk-free rate.
    Better ESG → lower spread.  Pure function for dashboard use.
    """
    penalty = (100.0 - esg_score) / 100.0
    spread = base_spread + penalty * (max_spread - base_spread)
    return min(spread, max_spread)
