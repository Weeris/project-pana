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

        # Create agents — stored in our own list for cross-version compatibility
        # (mesa 2.x model.agents is empty; mesa 3.x model.agents works)
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
    def agents(self) -> list[BasePanaAgent]:
        """
        Compatible agent accessor for both mesa 2.x and 3.x.
        mesa 2.x Model.agents is never populated (agents live in schedule.agents),
        so we use our own _pana_agents list as the authoritative source.
        """
        return self._pana_agents

    @property
    def all_bank_agents(self) -> list[BankAgent]:
        return [a for a in self._pana_agents if isinstance(a, BankAgent)]

    @property
    def all_firm_agents(self) -> list[FirmAgent]:
        return [a for a in self._pana_agents if isinstance(a, FirmAgent)]

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
        1. Apply carbon tax cash drain to firms
        2. Recalculate ESG scores for all agents
        3. Apply contagion for agents with high brown exposure
        4. Advance schedule
        """
        self.current_step += 1

        # (a) Apply carbon tax cash drain to firms
        for firm in self.all_firm_agents:
            jurisdiction = next(
                (j for j in self.jurisdictions if j.name == firm.jurisdiction), None
            )
            if jurisdiction:
                tax_rate = jurisdiction.carbon_tax_rate
                tax_burden = firm.compute_carbon_tax_burden(tax_rate)
                firm.balance_sheet.Cash = max(0.0, firm.balance_sheet.Cash - tax_burden)

        # (b) Recalculate ESG for all agents
        for agent in self._pana_agents:
            agent._recalc_esg()

        # (c) Apply contagion for agents with high brown exposure
        for agent in self._pana_agents:
            bs = agent.balance_sheet
            total_assets = bs.Green_Assets + bs.Brown_Assets
            if total_assets > 0:
                brown_ratio = bs.Brown_Assets / total_assets
                if brown_ratio > 0.3:
                    # Apply contagion based on brown exposure
                    self.apply_contagion_to_agent(agent, price_shock=0.1)

        # (d) Advance schedule
        self.schedule.step()

        return {
            "step": self.current_step,
            "policy": self.global_policy_string,
            "num_agents": len(self._pana_agents),
        }

    def execute_agent_action(self, agent: "BasePanaAgent", action: str) -> dict:
        """
        Execute a named agent action and update the agent's balance sheet.
        Recognised actions: HOLD, LIQUIDATE_BROWN, BUY_GREEN, HEDGE, DELEVERAGE.
        """
        bs = agent.balance_sheet

        if action == "LIQUIDATE_BROWN":
            # Sell 20% of brown assets, convert proceeds to cash
            proceeds = bs.Brown_Assets * 0.20
            bs.Brown_Assets -= proceeds
            bs.Cash += proceeds

        elif action == "BUY_GREEN":
            # Shift up to 20% of cash into green assets
            allocation = bs.Cash * 0.20
            bs.Cash -= allocation
            bs.Green_Assets += allocation

        elif action == "HEDGE":
            # Purchase carbon credits: deduct cash, conceptually tracked
            hedge_cost = bs.Cash * 0.05
            bs.Cash -= hedge_cost

        elif action == "DELEVERAGE":
            # Pay down liabilities using available cash
            payoff = min(bs.Cash, bs.Liabilities * 0.10)
            bs.Cash -= payoff
            bs.Liabilities -= payoff

        elif action == "HOLD":
            pass

        else:
            # Unknown action — no-op
            pass

        # Recalculate ESG after balance sheet changes
        agent._recalc_esg()

        return {
            "agent_id": agent.agent_id,
            "action": action,
            "status": "ok",
            "cash": bs.Cash,
            "green_assets": bs.Green_Assets,
            "brown_assets": bs.Brown_Assets,
            "liabilities": bs.Liabilities,
        }

    def apply_contagion_to_agent(self, agent: "BasePanaAgent", price_shock: float) -> dict:
        """
        Apply a price shock to an agent's balance sheet and detect cascade risk.
        Updates Brown_Assets based on the price shock and flags contagion risk.
        """
        bs = agent.balance_sheet

        # Apply price shock to brown assets (devalue)
        bs.Brown_Assets *= max(0.0, 1.0 - price_shock)

        # Recalculate ESG
        agent._recalc_esg()

        # Detect cascade using ContagionEngine
        connected_ids = self.get_connected_agents(agent.agent_id)
        cascade_victims = self.contagion_engine.detect_liquidation_cascade(
            agent.agent_id,
            price_shock,
            connected_ids,
        )

        return {
            "agent_id": agent.agent_id,
            "price_shock": price_shock,
            "brown_assets_after": bs.Brown_Assets,
            "cascade_victims": cascade_victims,
        }

    def get_systemic_metrics(self) -> dict:
        """
        Compute aggregate metrics for the dashboard.
        """
        all_agents = self._pana_agents
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

        # Aggregate carbon tax burden across firms
        total_carbon_tax_burden = sum(
            firm.compute_carbon_tax_burden(
                next(
                    (j.carbon_tax_rate for j in self.jurisdictions if j.name == firm.jurisdiction),
                    0.0,
                )
            )
            for firm in self.all_firm_agents
        )

        # Average transition readiness across firms
        transition_readiness_scores = [
            firm.assess_transition_readiness() for firm in self.all_firm_agents
        ]
        avg_transition_readiness = (
            sum(transition_readiness_scores) / max(len(transition_readiness_scores), 1)
        )

        # Green asset ratio across all agents
        total_green = sum(a.balance_sheet.Green_Assets for a in all_agents)
        total_assets_all = sum(
            a.balance_sheet.Green_Assets + a.balance_sheet.Brown_Assets for a in all_agents
        )
        green_asset_ratio = total_green / max(total_assets_all, 1e-9)

        return {
            "avg_esg_score": round(total_esg, 2),
            "total_liquidity_gap": round(total_liquidity_gap, 2),
            "contagion_risk_ratio": round(contagion_risk, 3),
            "systemic_carbon_footprint": sum(
                getattr(a, "carbon_liability", 0.0) for a in all_agents
            ),
            "total_carbon_tax_burden": round(total_carbon_tax_burden, 2),
            "avg_transition_readiness": round(avg_transition_readiness, 3),
            "green_asset_ratio": round(green_asset_ratio, 3),
        }
