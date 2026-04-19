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
        """Add order to book; return fill dict if match found."""
        if order.asset == AssetType.CARBON_CREDIT:
            bids, asks = self.carbon_bids, self.carbon_asks
        else:
            bids, asks = self.bond_bids, self.bond_asks

        if order.side == "buy":
            # Check if a sell order exists at or below our bid
            fills = [(p, q) for p, q in asks if p <= order.price]
            if fills:
                fill_price, fill_qty = fills[0]
                execution_price = fill_price
                # Remove the filled ask
                asks[:] = [x for x in asks if x != (fill_price, fill_qty)]
                return {
                    "matched": True,
                    "price": execution_price,
                    "qty": min(fill_qty, order.quantity),
                }
            bids.append((order.price, order.quantity))
        else:
            fills = [(p, q) for p, q in bids if p >= order.price]
            if fills:
                fill_price, fill_qty = fills[0]
                execution_price = fill_price
                bids[:] = [x for x in bids if x != (fill_price, fill_qty)]
                return {
                    "matched": True,
                    "price": execution_price,
                    "qty": min(fill_qty, order.quantity),
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
