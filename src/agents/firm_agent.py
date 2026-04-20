"""FirmAgent: Non-financial corporation with carbon liability tracking."""

from __future__ import annotations

import random

from dataclasses import dataclass
from src.agents.base import BasePanaAgent, AgentType, BalanceSheet


@dataclass(eq=False)
class FirmAgent(BasePanaAgent):
    """
    Firm-specific behaviour:
    - Carbon emissions liability
    - Green transition capex planning
    - Revenue stress from carbon tax
    """

    carbon_liability: float = 0.0       # tonnes CO₂ outstanding
    green_capex: float = 0.0            # planned green investment
    revenue: float = 100.0

    def __init__(self, agent_id: str, jurisdiction: str, **kwargs):
        super().__init__(agent_id, AgentType.FIRM, jurisdiction, **kwargs)
        # Initialise balance sheet with realistic values
        self.balance_sheet = BalanceSheet(
            Cash=random.uniform(500.0, 3000.0),
            Green_Assets=random.uniform(200.0, 1500.0),
            Brown_Assets=random.uniform(300.0, 2000.0),
            Liabilities=random.uniform(200.0, 1500.0),
        )
        # Initialise carbon and revenue state
        self.carbon_liability = random.uniform(50.0, 500.0)   # tonnes CO₂
        self.green_capex = random.uniform(0.0, 100.0)
        self.revenue = random.uniform(500.0, 5000.0)
        # Update ESG score based on initial asset composition
        self._recalc_esg()

    def compute_carbon_tax_burden(self, carbon_tax_rate: float) -> float:
        """Annual carbon tax cost given current liability and tax rate."""
        return self.carbon_liability * carbon_tax_rate

    def assess_transition_readiness(self) -> float:
        """Score 0–1: how ready is this firm for green transition?"""
        total_assets = self.balance_sheet.Green_Assets + self.balance_sheet.Brown_Assets
        green_asset_ratio = (
            self.balance_sheet.Green_Assets / max(total_assets, 1e-9)
        )
        capex_ratio = self.green_capex / max(self.revenue, 1e-9)
        return 0.5 * green_asset_ratio + 0.5 * capex_ratio

    def execute_action(self, action: str, **kwargs) -> dict:
        """
        Override execute_action to handle carbon_liability reduction for HEDGE.
        Firms can use carbon offsets or green capex to reduce carbon liability.
        """
        result = {"agent_id": self.agent_id, "action": action, "status": "ok"}

        if action == "HOLD":
            # No state change
            pass

        elif action == "LIQUIDATE_BROWN":
            # Sell brown assets, convert to cash
            brown_value = self.balance_sheet.Brown_Assets
            self.balance_sheet.Cash += brown_value
            self.balance_sheet.Brown_Assets = 0.0
            result["brown_liquidated"] = brown_value

        elif action == "BUY_GREEN":
            # Use cash to purchase green assets
            amount = kwargs.get("amount", self.balance_sheet.Cash * 0.5)
            cost = min(amount, self.balance_sheet.Cash)
            self.balance_sheet.Green_Assets += cost
            self.balance_sheet.Cash -= cost
            result["green_purchased"] = cost

        elif action == "HEDGE":
            # Reduce carbon liability via offsets or green capex
            # Carbon offset amount (tonnes CO₂) funded by green investment
            offset_amount = kwargs.get("offset_amount", 0.0)
            green_spend = kwargs.get("green_spend", 0.0)
            reduction = min(offset_amount + green_spend * 0.1, self.carbon_liability)
            self.carbon_liability -= reduction
            self.balance_sheet.Cash -= green_spend
            self.balance_sheet.Green_Assets += green_spend * 0.9  # 90% to assets
            result["hedge_applied"] = reduction
            result["carbon_reduced"] = reduction

        elif action == "DELEVERAGE":
            # Pay down liabilities using cash
            payoff = min(self.balance_sheet.Cash, self.balance_sheet.Liabilities)
            self.balance_sheet.Cash -= payoff
            self.balance_sheet.Liabilities -= payoff
            result["debt_paid"] = payoff

        else:
            result["status"] = "unknown_action"

        # Recalculate ESG after structural changes
        self._recalc_esg()
        return result
