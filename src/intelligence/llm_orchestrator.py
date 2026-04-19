"""LLM Orchestrator: LangChain-powered reasoning for agent cognition."""

from __future__ import annotations
import os
from typing import TYPE_CHECKING

from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage

if TYPE_CHECKING:
    from src.agents.base import BasePanaAgent


SYSTEM_PROMPT = """You are {agent_type} Agent {agent_id} operating in jurisdiction {jurisdiction}.
You are "Systemic-Risk Aware" — you must prioritise survival and profit while reacting to ESG policy shifts.

Your internal state:
- Cash: {cash}
- Green Assets: {green_assets}
- Brown Assets: {brown_assets}
- Liabilities: {liabilities}
- ESG Score: {esg_score}/100
- Risk Threshold: {risk_threshold}

Current Global Policy: {policy_string}

Your available actions:
1. HOLD — maintain current position
2. LIQUIDATE_BROWN — sell {pct}% of brown assets to reduce carbon liability
3. BUY_GREEN — shift portfolio toward green assets
4. HEDGE — purchase carbon credits to offset liability
5. DELEVERAGE — reduce liabilities to improve Tier 1 Capital ratio

Reason step-by-step:
- How does the policy impact my balance sheet?
- What is my current ESG risk?
- Which action best preserves Tier 1 Capital while managing ESG exposure?

Output your reasoning then your chosen action (HOLD / LIQUIDATE_BROWN / BUY_GREEN / HEDGE / DELEVERAGE)."""


class PanaLLMOrchestrator:
    """
    Wraps LangChain + Ollama for agent cognition.
    Falls back to rule-based reasoning if LLM is unavailable.
    """

    def __init__(
        self,
        model_name: str = "llama3",
        base_url: str = "http://localhost:11434",
        use_llm: bool = True,
    ):
        self.use_llm = use_llm and _check_ollama_available(base_url)

        if self.use_llm:
            self.llm = ChatOllama(
                model=model_name,
                base_url=base_url,
                temperature=0.3,   # Low temperature for financial reasoning
                timeout=30,
            )
        else:
            self.llm = None

        self.prompt_template = PromptTemplate.from_template(SYSTEM_PROMPT)

    def reason_for_agent(
        self,
        agent: "BasePanaAgent",
        policy_string: str,
        liquidation_pct: float = 20.0,
    ) -> str:
        """
        Produce a reasoning trace and suggested action for an agent.
        """

        if not self.use_llm or self.llm is None:
            return self._rule_based_reasoning(agent, policy_string, liquidation_pct)

        prompt = self.prompt_template.format(
            agent_type=agent.agent_type.value.upper(),
            agent_id=agent.agent_id,
            jurisdiction=agent.jurisdiction,
            cash=agent.balance_sheet.Cash,
            green_assets=agent.balance_sheet.Green_Assets,
            brown_assets=agent.balance_sheet.Brown_Assets,
            liabilities=agent.balance_sheet.Liabilities,
            esg_score=agent.esg_score,
            risk_threshold=agent.risk_threshold,
            policy_string=policy_string,
            pct=liquidation_pct,
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

    @staticmethod
    def _rule_based_reasoning(
        agent: "BasePanaAgent",
        policy_string: str,
        liquidation_pct: float = 20.0,
    ) -> str:
        """Fallback rule-based reasoning when LLM is unavailable."""
        thoughts = []
        thoughts.append(f"[{agent.agent_id}] Perceiving: {policy_string}")

        tier1 = agent.compute_tier1_capital()
        thoughts.append(f"Tier 1 Capital: {tier1:.2f}")

        if "Carbon tax" in policy_string or "carbon" in policy_string.lower():
            total_assets = agent.balance_sheet.Green_Assets + agent.balance_sheet.Brown_Assets
            brown_ratio = agent.balance_sheet.Brown_Assets / max(total_assets, 1e-9)
            if brown_ratio > 0.3:
                action = "LIQUIDATE_BROWN"
                thoughts.append(f"Brown asset ratio {brown_ratio:.0%} exceeds threshold — {action}")
            else:
                action = "HOLD"
                thoughts.append(f"Brown asset ratio acceptable — HOLD")
        else:
            action = "HOLD"
            thoughts.append("No relevant policy detected — HOLD")

        agent.log_thought(" | ".join(thoughts))
        return " | ".join(thoughts) + f"\n**Action: {action}**"


def _check_ollama_available(base_url: str) -> bool:
    """Check if Ollama is reachable."""
    try:
        import httpx
        r = httpx.get(f"{base_url}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
