"""PanaModel: Mesa Model managing time-steps, agents, and Market Bridge."""

from __future__ import annotations

import mesa
from mesa.space import NetworkGrid
import networkx as nx
from typing import Optional

from src.agents.base import BasePanaAgent, AgentType
from src.agents.bank_agent import BankAgent
from src.agents.firm_agent import FirmAgent
from src.engine.market_bridge import GlobalOrderBook, ContagionEngine
from src.engine.jurisdiction import Jurisdiction


class PanaModel(mesa.Model):
    """
    Mesa Model for Project PANA.

    Manages:
    - Agent schedule (random activation per step)
    - Agent interaction via Market Bridge
    - Contagion propagation across jurisdictions
    - Global policy string accessible to all agents
    """

    def __init__(
        self,
        num_banks: int = 5,
        num_firms: int = 10,
        jurisdictions: Optional[list[Jurisdiction]] = None,
        contagion_engine: Optional[ContagionEngine] = None,
    ):
        super().__init__()
        self.current_step = 0
        self.schedule = mesa.time.RandomActivation(self)
        self.market_bridge = GlobalOrderBook()
        self.contagion_engine = contagion_engine or ContagionEngine()
        self.jurisdictions = jurisdictions or [
            Jurisdiction("EU"),
            Jurisdiction("US"),
            Jurisdiction("SG"),
        ]
        self.global_policy_string = "No active policy changes."

        # Build agent interaction network (small-world via NetworkX)
        total_agents = num_banks + num_firms
        self.network = nx.watts_strogatz_graph(
            n=total_agents, k=min(4, total_agents - 1), p=0.3, seed=42
        )
        self.grid = NetworkGrid(self.network)

        # Create agents
        self._pana_agents: list[BasePanaAgent] = []
        for i in range(num_banks):
            j = self.jurisdictions[i % len(self.jurisdictions)]
            bank = BankAgent(f"bank-{i:03d}", j.name)
            self._pana_agents.append(bank)
            self.schedule.add(bank)

        for i in range(num_firms):
            j = self.jurisdictions[i % len(self.jurisdictions)]
            firm = FirmAgent(f"firm-{i:03d}", j.name)
            self._pana_agents.append(firm)
            self.schedule.add(firm)

        # Map agent_id → position in network
        self._agent_pos = {a.agent_id: i for i, a in enumerate(self._pana_agents)}

    @property
    def all_bank_agents(self) -> list[BankAgent]:
        return [a for a in self.schedule.agents if isinstance(a, BankAgent)]

    @property
    def all_firm_agents(self) -> list[FirmAgent]:
        return [a for a in self.schedule.agents if isinstance(a, FirmAgent)]

    def set_policy(self, policy_string: str) -> None:
        self.global_policy_string = policy_string

    def get_policy_string(self) -> str:
        return self.global_policy_string

    def get_connected_agents(self, agent_id: str) -> list[str]:
        """Return agent IDs connected to this agent in the network."""
        idx = self._agent_pos[agent_id]
        neighbours = self.network.neighbors(idx)
        return [self._pana_agents[i].agent_id for i in neighbours]

    def step(self) -> dict:
        """
        One simulation step:
        1. Each agent reads global policy
        2. Each agent reasons and proposes an action (placeholder → LLM hook)
        3. Actions are resolved through Market Bridge
        4. Contagion engine checks for cascades
        5. Agent states are updated
        """
        self.current_step += 1
        self.schedule.step()

        return {
            "step": self.current_step,
            "policy": self.global_policy_string,
            "num_agents": len(self.schedule.agents),
        }

    def get_systemic_metrics(self) -> dict:
        """
        Compute aggregate metrics for the dashboard.
        """
        all_agents = list(self.schedule.agents)
        total_esg = sum(a.esg_score for a in all_agents) / max(len(all_agents), 1)
        total_liquidity_gap = sum(
            self.contagion_engine.compute_liquidity_gap(
                a.balance_sheet.Cash,
                a.balance_sheet.Liabilities,
                a.balance_sheet.Green_Assets + a.balance_sheet.Brown_Assets,
            )
            for a in all_agents
        )
        contagion_risk = len(
            [a for a in self.all_bank_agents if a.assess_panic_sell_risk() > 0.3]
        ) / max(len(self.all_bank_agents), 1)

        return {
            "avg_esg_score": round(total_esg, 2),
            "total_liquidity_gap": round(total_liquidity_gap, 2),
            "contagion_risk_ratio": round(contagion_risk, 3),
            "systemic_carbon_footprint": sum(
                getattr(a, "carbon_liability", 0.0) for a in all_agents
            ),
        }
