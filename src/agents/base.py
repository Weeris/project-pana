"""BasePanaAgent: Financial State Machine with LLM Reasoning Hook."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class AgentType(Enum):
    BANK = "bank"
    FIRM = "firm"


class ESG_Rating(Enum):
    AAA = "AAA"
    AA  = "AA"
    A   = "A"
    BBB = "BBB"
    BB  = "BB"
    B   = "B"
    CCC = "CCC"
    D   = "D"


@dataclass
class BalanceSheet:
    Cash: float = 0.0
    Green_Assets: float = 0.0   # Low-carbon, ESG-positive
    Brown_Assets: float = 0.0   # High-carbon, stranded-asset risk
    Liabilities: float = 0.0    # Total debt obligations


@dataclass(eq=False)
class BasePanaAgent:
    """
    Each agent maintains:
    - balance_sheet: BalanceSheet
    - esg_score: float 0–100
    - risk_threshold: float 0–1 (probability of panic-selling / default)
    - agent_type: AgentType
    - jurisdiction: str
    - thought_log: list[str] — LLM reasoning trace for Streamlit "Thought Stream"
    """

    agent_id: str
    agent_type: AgentType
    jurisdiction: str
    balance_sheet: BalanceSheet = field(default_factory=BalanceSheet)
    esg_score: float = 75.0          # Start at BBB/BB boundary
    risk_threshold: float = 0.05     # 5% default
    thought_log: list[str] = field(default_factory=list)

    # Make agents hashable by agent_id only so they work in Mesa's AgentSet
    def __hash__(self) -> int:
        return hash(self.agent_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BasePanaAgent):
            return self.agent_id == other.agent_id
        return False

    def compute_tier1_capital(self) -> float:
        """Tier 1 Capital = Cash + Green_Assets − Liabilities (simplified)."""
        return (
            self.balance_sheet.Cash
            + self.balance_sheet.Green_Assets
            - self.balance_sheet.Liabilities
        )

    def update_esg_score(self, green_ratio: float) -> None:
        """ESG score driven by asset composition."""
        self.esg_score = 40.0 + 60.0 * green_ratio  # 40–100 range

    def _recalc_esg(self) -> None:
        """Recalculate ESG score from current balance sheet composition."""
        total = self.balance_sheet.Green_Assets + self.balance_sheet.Brown_Assets
        green_ratio = self.balance_sheet.Green_Assets / max(total, 1e-9)
        self.update_esg_score(green_ratio)

    def log_thought(self, thought: str) -> None:
        self.thought_log.append(thought)

    def perceive_policy(self, policy_string: str) -> str:
        """
        Hook for LLM — receives global policy string.
        Returns the perceived policy impact summary.
        """
        return policy_string

    def reason(self, perception: str) -> str:
        """
        Hook for LLM — decides action given perception + internal state.
        Returns a reasoning trace string.
        """
        return f"[{self.agent_id}] Reasoning on: {perception}"

    def act(self, action: str) -> dict:
        """
        Execute action, update internal state.
        Returns dict of changes for Market Bridge.
        """
        return {"agent_id": self.agent_id, "action": action, "status": "ok"}

    def execute_action(self, action: str, **kwargs) -> dict:
        """
        Execute a named action and update internal state accordingly.
        Actions: HOLD, LIQUIDATE_BROWN, BUY_GREEN, HEDGE, DELEVERAGE
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
            # Placeholder: derivatives / carbon offsets to reduce risk
            hedge_amount = kwargs.get("hedge_amount", 0.0)
            result["hedge_applied"] = hedge_amount

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

    def step(self) -> None:
        """
        Mesa-required step method.
        Called by schedule each tick; agents read policy, reason, and act.
        The actual reasoning is invoked externally by the orchestrator.
        """
        policy = self.perceive_policy("")
        self.reason(policy)
