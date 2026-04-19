"""FirmAgent: Non-financial corporation with carbon liability tracking."""

from __future__ import annotations
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
