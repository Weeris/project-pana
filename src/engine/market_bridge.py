"""Market Bridge: Global Order Book for Carbon Credits and Green Bonds."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class AssetType(Enum):
    CARBON_CREDIT = "carbon_credit"
    GREEN_BOND     = "green_bond"


@dataclass
class Order:
    agent_id: str
    asset: AssetType
    side: str          # "buy" or "sell"
    quantity: float
    price: float
    jurisdiction: str


@dataclass
class GlobalOrderBook:
    """
    Simplified central limit order book (CLOB).
    Tracks bid/ask for CARBON_CREDIT and GREEN_BOND.
    """

    carbon_bids: list[tuple[float, float]] = field(default_factory=list)   # (price, qty)
    carbon_asks: list[tuple[float, float]] = field(default_factory=list)
    bond_bids:   list[tuple[float, float]] = field(default_factory=list)
    bond_asks:   list[tuple[float, float]] = field(default_factory=list)

    def add_order(self, order: Order) -> dict:
        """Add order to book; match against all contra-side orders at qualifying prices."""
        if order.asset == AssetType.CARBON_CREDIT:
            bids, asks = self.carbon_bids, self.carbon_asks
        else:
            bids, asks = self.bond_bids, self.bond_asks

        if order.side == "buy":
            # Walk the book: collect all asks at or below our bid price
            fills = [(p, q) for p, q in asks if p <= order.price]
            if fills:
                # Sort by price ascending (best ask first)
                fills.sort(key=lambda x: x[0])
                total_qty = 0.0
                total_cost = 0.0
                remaining_qty = order.quantity
                new_asks = []
                for fill_price, fill_qty in fills:
                    if remaining_qty <= 0:
                        new_asks.append((fill_price, fill_qty))
                        continue
                    taken = min(fill_qty, remaining_qty)
                    total_qty += taken
                    total_cost += taken * fill_price
                    remaining_qty -= taken
                    if fill_qty > taken:
                        new_asks.append((fill_price, fill_qty - taken))
                # Update book: remaining unmatched asks
                unmatched_asks = [(p, q) for p, q in asks if p > order.price]
                if order.side == "buy":
                    self.carbon_bids if order.asset == AssetType.CARBON_CREDIT else self.bond_bids
                    if order.asset == AssetType.CARBON_CREDIT:
                        self.carbon_asks = unmatched_asks + new_asks
                    else:
                        self.bond_asks = unmatched_asks + new_asks
                avg_price = total_cost / total_qty if total_qty > 0 else 0
                return {
                    "matched": True,
                    "price": avg_price,
                    "qty": total_qty,
                }
            bids.append((order.price, order.quantity))
        else:
            # Sell: walk up the book against bids at or above our ask price
            fills = [(p, q) for p, q in bids if p >= order.price]
            if fills:
                fills.sort(key=lambda x: -x[0])  # best bid (highest) first
                total_qty = 0.0
                total_revenue = 0.0
                remaining_qty = order.quantity
                new_bids = []
                for fill_price, fill_qty in fills:
                    if remaining_qty <= 0:
                        new_bids.append((fill_price, fill_qty))
                        continue
                    taken = min(fill_qty, remaining_qty)
                    total_qty += taken
                    total_revenue += taken * fill_price
                    remaining_qty -= taken
                    if fill_qty > taken:
                        new_bids.append((fill_price, fill_qty - taken))
                unmatched_bids = [(p, q) for p, q in bids if p < order.price]
                if order.asset == AssetType.CARBON_CREDIT:
                    self.carbon_bids = unmatched_bids + new_bids
                else:
                    self.bond_bids = unmatched_bids + new_bids
                avg_price = total_revenue / total_qty if total_qty > 0 else 0
                return {
                    "matched": True,
                    "price": avg_price,
                    "qty": total_qty,
                }
            asks.append((order.price, order.quantity))

        return {"matched": False}

    def best_bid_ask(self, asset: AssetType) -> tuple[Optional[float], Optional[float]]:
        if asset == AssetType.CARBON_CREDIT:
            bids, asks = self.carbon_bids, self.carbon_asks
        else:
            bids, asks = self.bond_bids, self.bond_asks
        best_bid = max((p for p, _ in bids), default=None)
        best_ask = min((p for p, _ in asks), default=None)
        return best_bid, best_ask


@dataclass
class ContagionEngine:
    """
    Detects and propagates shocks:
    - Liquidation cascade detection
    - Margin call trigger propagation
    """

    liquidation_threshold: float = 0.20   # 20% asset price drop → margin call
    cascade_probability: float = 0.35      # probability a neighbour gets affected

    def detect_liquidation_cascade(
        self,
        agent_id: str,
        price_shock: float,
        connected_agent_ids: list[str],
    ) -> list[str]:
        """
        Given an agent's large liquidation and the resulting price shock,
        return list of agent_ids predicted to be caught in the cascade.
        """
        affected = []
        if price_shock >= self.liquidation_threshold:
            for aid in connected_agent_ids:
                if np.random.rand() < self.cascade_probability:
                    affected.append(aid)
        return affected

    def compute_liquidity_gap(
        self, cash: float, liabilities: float, asset_value: float
    ) -> float:
        """Liquidity gap = Liabilities − (Cash + 0.5 × AssetValue)."""
        return liabilities - (cash + 0.5 * asset_value)
