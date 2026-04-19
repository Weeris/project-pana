"""BankAgent: Inherits BasePanaAgent, adds Basel-style constraints."""

from __future__ import annotations
from dataclasses import dataclass
from src.agents.base import BasePanaAgent, AgentType, BalanceSheet


@dataclass(eq=False)
class BankAgent(BasePanaAgent):
    """
    Bank-specific behaviour:
    - Leverage ratio checks
    - Margin call triggers
    - Wholesale funding risk
    """

    leverage_ratio: float = 12.0   # Basel III max ≈ 12× for Tier 1
    wholesale_funding_ratio: float = 0.0

    def __init__(self, agent_id: str, jurisdiction: str, **kwargs):
        super().__init__(agent_id, AgentType.BANK, jurisdiction, **kwargs)

    def check_leverage_constraint(self) -> bool:
        total_exposure = (
            self.balance_sheet.Green_Assets
            + self.balance_sheet.Brown_Assets
        )
        tier1 = self.compute_tier1_capital()
        if tier1 <= 0:
            return False
        return (total_exposure / tier1) <= self.leverage_ratio

    def assess_panic_sell_risk(self) -> float:
        """
        Probability of panic-selling based on:
        - ESG score deterioration
        - Liability coverage ratio
        - Cross-border exposure (simplified)
        """
        liability_coverage = (
            self.balance_sheet.Cash / max(self.balance_sheet.Liabilities, 1e-9)
        )
        esg_factor = max(0.0, (100.0 - self.esg_score) / 100.0)
        risk = self.risk_threshold + (1 - liability_coverage) * 0.1 + esg_factor * 0.15
        return min(risk, 1.0)
