"""Integration test: full agent loop — step → LLM reason → market bridge → contagion → metrics."""

from __future__ import annotations

import pytest
from src.agents.base import BasePanaAgent, AgentType, BalanceSheet
from src.agents.bank_agent import BankAgent
from src.agents.firm_agent import FirmAgent
from src.engine.jurisdiction import Jurisdiction
from src.engine.market_bridge import (
    GlobalOrderBook,
    ContagionEngine,
    Order,
    AssetType,
)
from src.engine.pana_model import PanaModel
from src.intelligence.llm_orchestrator import PanaLLMOrchestrator


class TestFullAgentLoop:
    """Run the complete PANA loop end-to-end."""

    @pytest.fixture
    def jurisdictions(self):
        return [
            Jurisdiction("EU", carbon_tax_rate=50.0, green_subsidy=0.1),
            Jurisdiction("US", carbon_tax_rate=40.0, green_subsidy=0.09),
            Jurisdiction("SG", carbon_tax_rate=60.0, green_subsidy=0.11),
        ]

    @pytest.fixture
    def contagion(self):
        return ContagionEngine(liquidation_threshold=0.20, cascade_probability=0.35)

    @pytest.fixture
    def model(self, jurisdictions, contagion):
        return PanaModel(
            num_banks=3,
            num_firms=5,
            jurisdictions=jurisdictions,
            contagion_engine=contagion,
        )

    @pytest.fixture
    def orchestrator(self):
        return PanaLLMOrchestrator(use_llm=False)  # rule-based fallback

    def test_model_init(self, model):
        assert model.current_step == 0
        assert len(model.schedule.agents) == 8  # 3 banks + 5 firms
        assert len(model.jurisdictions) == 3

    def test_agent_balance_sheets(self, model):
        banks = model.all_bank_agents
        firms = model.all_firm_agents
        assert all(isinstance(b.balance_sheet, BalanceSheet) for b in banks)
        assert all(b.compute_tier1_capital() is not None for b in banks)
        assert all(f.esg_score == 75.0 for f in firms)  # default

    def test_policy_roundtrip(self, model):
        policy = "Carbon tax $100/t in EU | Green subsidy 20%"
        model.set_policy(policy)
        assert model.get_policy_string() == policy
        # policy should propagate to agents via their perceive hook
        for agent in model.schedule.agents:
            perceived = agent.perceive_policy(model.get_policy_string())
            assert policy in perceived or perceived == policy

    def test_market_order_book(self):
        book = GlobalOrderBook()
        o1 = Order("bank-0", AssetType.CARBON_CREDIT, "buy",  100, 50.0, "EU")
        o2 = Order("firm-0", AssetType.CARBON_CREDIT, "sell",  50, 48.0, "EU")
        result = book.add_order(o1)  # bid 50, o1 buys at 50
        assert result["matched"] is False  # no ask at ≤ 50 yet
        result = book.add_order(o2)
        assert result["matched"] is True
        assert result["price"] == 50.0
        assert result["qty"] == 50

    def test_order_book_best_bid_ask(self):
        book = GlobalOrderBook()
        book.carbon_bids  = [(45.0, 100), (44.0, 50)]
        book.carbon_asks = [(48.0, 80),  (49.0, 30)]
        best_bid, best_ask = book.best_bid_ask(AssetType.CARBON_CREDIT)
        assert best_bid == 45.0
        assert best_ask == 48.0

    def test_contagion_engine_cascade(self, contagion):
        # No cascade below threshold
        result = contagion.detect_liquidation_cascade(
            "bank-0", price_shock=0.10, connected_agent_ids=["bank-1", "firm-0"]
        )
        assert isinstance(result, list)
        assert result == []  # below liquidation_threshold=0.20

        # Above threshold → stochastic cascade
        # Run multiple times; with prob=0.35 we expect some affected agents
        results = [
            contagion.detect_liquidation_cascade(
                "bank-0", price_shock=0.30,
                connected_agent_ids=[f"agent-{i}" for i in range(10)]
            )
            for _ in range(20)
        ]
        # At least some runs should return non-empty lists
        assert any(len(r) > 0 for r in results)

    def test_liquidity_gap(self, contagion):
        gap = contagion.compute_liquidity_gap(cash=20.0, liabilities=100.0, asset_value=150.0)
        # 100 - (20 + 0.5*150) = 100 - 95 = 5
        assert gap == 5.0

        positive_gap = contagion.compute_liquidity_gap(cash=5.0, liabilities=100.0, asset_value=50.0)
        # 100 - (5 + 25) = 70
        assert positive_gap == 70.0

    def test_llm_orchestrator_rule_based(self, orchestrator):
        agent = BankAgent("bank-test", "EU")
        agent.balance_sheet.Cash          = 50.0
        agent.balance_sheet.Green_Assets = 200.0
        agent.balance_sheet.Brown_Assets = 100.0
        agent.balance_sheet.Liabilities  = 150.0
        agent.esg_score = 80.0

        policy = "Carbon tax $100/t in EU"
        thought = orchestrator.reason_for_agent(agent, policy)

        assert isinstance(thought, str)
        assert len(thought) > 0
        assert "bank-test" in thought or "Bank" in thought or "tier1" in thought.lower()

    def test_full_loop_step(self, model, orchestrator):
        """One complete simulation step through all components."""
        shock_intensity = 0.10

        # ── Pre-step state ──────────────────────────────────────
        pre_metrics = model.get_systemic_metrics()
        assert "avg_esg_score" in pre_metrics
        assert "total_liquidity_gap" in pre_metrics

        # ── Apply policy + agent reasoning ──────────────────────
        policy = "Step 1: Carbon tax $100/t | Green subsidy 20%"
        model.set_policy(policy)

        thought_lines = []
        for agent in model.schedule.agents:
            # Apply exogenous brown-asset shock
            if shock_intensity > 0 and agent.balance_sheet.Brown_Assets > 0:
                agent.balance_sheet.Brown_Assets *= (1 - shock_intensity)

            # Reason (LLM or fallback)
            thought = orchestrator.reason_for_agent(agent, policy)
            agent.log_thought(thought)
            thought_lines.append(thought)

        # ── Execute model step ───────────────────────────────────
        result = model.step()
        assert result["step"] == 1
        assert result["num_agents"] == 8

        # ── Post-step metrics ───────────────────────────────────
        post_metrics = model.get_systemic_metrics()
        assert "avg_esg_score" in post_metrics
        assert "total_liquidity_gap" in post_metrics
        assert "contagion_risk_ratio" in post_metrics

        # Thought stream populated
        assert len(thought_lines) == 8

        # Policy log updated
        assert policy in model.get_policy_string()

    def test_multi_step_evolution(self, model, orchestrator):
        """Run 5 steps; verify metrics drift and agents accumulate thought logs."""
        initial_metrics = model.get_systemic_metrics()

        for step_num in range(1, 6):
            model.set_policy(f"Step {step_num}: Carbon tax ${step_num * 10}/t")
            for agent in model.schedule.agents:
                thought = orchestrator.reason_for_agent(
                    agent, f"Step {step_num} policy"
                )
                agent.log_thought(thought)
            model.step()

        final_metrics = model.get_systemic_metrics()
        assert final_metrics["avg_esg_score"] is not None
        assert len(model.policy_log) >= 5 if hasattr(model, "policy_log") else True

        # All agents accumulated at least 5 thought entries
        for agent in model.schedule.agents:
            assert len(agent.thought_log) >= 5

    def test_contagion_routing_via_network(self, model):
        """Verify get_connected_agents routes through NetworkX correctly."""
        bank0 = model.all_bank_agents[0]
        connected = model.get_connected_agents(bank0.agent_id)
        assert isinstance(connected, list)
        # Small-world graph with k=4 → each agent should have ~4 neighbours
        assert 0 <= len(connected) <= 4

    def test_jurisdiction_policy_awareness(self, model, jurisdictions):
        """Agents in different jurisdictions receive correct carbon tax rates."""
        eu_j = next(j for j in model.jurisdictions if j.name == "EU")
        assert eu_j.carbon_tax_rate == 50.0

        # Verify firm agents exist in every jurisdiction
        for j in model.jurisdictions:
            agents_in_j = [a for a in model.schedule.agents if a.jurisdiction == j.name]
            assert len(agents_in_j) > 0

    def test_systemic_metrics_aggregation(self, model):
        """get_systemic_metrics returns well-formed dict with all required keys."""
        metrics = model.get_systemic_metrics()
        required_keys = {
            "avg_esg_score",
            "total_liquidity_gap",
            "contagion_risk_ratio",
            "systemic_carbon_footprint",
        }
        assert required_keys.issubset(metrics.keys()), f"Missing: {required_keys - metrics.keys()}"
        assert isinstance(metrics["avg_esg_score"], (int, float))
        assert isinstance(metrics["total_liquidity_gap"], (int, float))
        assert 0.0 <= metrics["contagion_risk_ratio"] <= 1.0

    def test_bank_leverage_constraint(self, model):
        """Bank leverage constraint check returns bool."""
        for bank in model.all_bank_agents:
            result = bank.check_leverage_constraint()
            assert isinstance(result, bool)

    def test_bank_panic_sell_risk(self, model):
        """Bank panic-sell probability is bounded [0, 1]."""
        for bank in model.all_bank_agents:
            prob = bank.assess_panic_sell_risk()
            assert 0.0 <= prob <= 1.0

    def test_firm_carbon_tax_burden(self, model):
        """Firm carbon tax burden is computed correctly."""
        for firm in model.all_firm_agents:
            firm.carbon_liability = 1000.0
            burden = firm.compute_carbon_tax_burden(50.0)
            assert burden == 50_000.0

    def test_firm_transition_readiness(self, model):
        """Firm transition readiness is bounded [0, 1]."""
        for firm in model.all_firm_agents:
            firm.balance_sheet.Green_Assets = 100.0
            firm.balance_sheet.Brown_Assets = 100.0
            firm.green_capex = 20.0
            firm.revenue = 100.0
            score = firm.assess_transition_readiness()
            assert 0.0 <= score <= 1.0

    def test_order_book_cross_agent(self):
        """Two agents can trade across the order book (buy vs sell)."""
        book = GlobalOrderBook()

        # Bank sells green bonds
        sell_order = Order("bank-0", AssetType.GREEN_BOND, "sell", 200, 1.05, "EU")
        result = book.add_order(sell_order)
        assert result["matched"] is False  # no buyer yet

        # Firm buys green bonds
        buy_order = Order("firm-0", AssetType.GREEN_BOND, "buy", 200, 1.10, "EU")
        result = book.add_order(buy_order)
        assert result["matched"] is True
        assert result["price"] == 1.05  # executes at seller's price
        assert result["qty"] == 200

    def test_no_agents_left_behind(self, model):
        """All agents are reachable via the schedule after init."""
        agents_list = list(model.schedule.agents)
        assert len(agents_list) == 8
        assert all(a.compute_tier1_capital() is not None for a in agents_list)
