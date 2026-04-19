import pytest
from src.agents.base import BasePanaAgent, AgentType, BalanceSheet, ESG_Rating


def test_agent_initialisation():
    a = BasePanaAgent("bank-001", AgentType.BANK, "SG")
    assert a.agent_id == "bank-001"
    assert a.jurisdiction == "SG"
    assert a.esg_score == 75.0
    assert a.risk_threshold == 0.05


def test_tier1_capital_calculation():
    a = BasePanaAgent("bank-001", AgentType.BANK, "SG")
    a.balance_sheet = BalanceSheet(Cash=100, Green_Assets=200, Brown_Assets=50, Liabilities=150)
    assert a.compute_tier1_capital() == 150.0


def test_esg_score_update():
    a = BasePanaAgent("bank-001", AgentType.BANK, "SG")
    a.update_esg_score(green_ratio=0.8)
    assert 85.0 <= a.esg_score <= 88.0  # 40 + 60*0.8 = 88


def test_thought_log():
    a = BasePanaAgent("firm-001", AgentType.FIRM, "EU")
    a.log_thought("Carbon tax rise detected — adjusting portfolio.")
    assert len(a.thought_log) == 1
    assert "Carbon tax" in a.thought_log[0]


def test_perceive_policy():
    a = BasePanaAgent("bank-001", AgentType.BANK, "EU")
    result = a.perceive_policy("Carbon tax increased by 15% in Jurisdiction EU")
    assert "Carbon tax increased" in result


def test_act_returns_dict():
    a = BasePanaAgent("bank-001", AgentType.BANK, "EU")
    result = a.act("LIQUIDATE_BROWN")
    assert result["agent_id"] == "bank-001"
    assert result["action"] == "LIQUIDATE_BROWN"
    assert result["status"] == "ok"
