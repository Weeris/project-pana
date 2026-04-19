"""Tests for PanaModel Mesa ABM."""

import pytest
from src.engine.pana_model import PanaModel
from src.engine.jurisdiction import Jurisdiction
from src.engine.market_bridge import ContagionEngine


def test_model_initialisation():
    model = PanaModel(num_banks=3, num_firms=5)
    assert model.current_step == 0
    assert len(model.schedule.agents) == 8
    assert len(model.all_bank_agents) == 3
    assert len(model.all_firm_agents) == 5


def test_model_step():
    model = PanaModel(num_banks=2, num_firms=3)
    result = model.step()
    assert result["step"] == 1
    assert result["num_agents"] == 5
    assert model.current_step == 1


def test_set_and_get_policy():
    model = PanaModel()
    model.set_policy("Carbon tax $100/t in EU")
    assert "Carbon tax $100/t" in model.get_policy_string()


def test_get_connected_agents():
    model = PanaModel(num_banks=4, num_firms=4)
    connected = model.get_connected_agents("bank-000")
    assert isinstance(connected, list)
    assert all(isinstance(aid, str) for aid in connected)


def test_systemic_metrics():
    model = PanaModel(num_banks=2, num_firms=3)
    metrics = model.get_systemic_metrics()
    assert "avg_esg_score" in metrics
    assert "total_liquidity_gap" in metrics
    assert "contagion_risk_ratio" in metrics
    assert "systemic_carbon_footprint" in metrics
    assert 0 <= metrics["contagion_risk_ratio"] <= 1


def test_model_with_custom_jurisdictions():
    jurisdictions = [
        Jurisdiction("EU", carbon_tax_rate=50.0, green_subsidy=0.2),
        Jurisdiction("SG", carbon_tax_rate=80.0, green_subsidy=0.3),
    ]
    model = PanaModel(num_banks=2, num_firms=2, jurisdictions=jurisdictions)
    assert len(model.jurisdictions) == 2
    assert model.jurisdictions[0].carbon_tax_rate == 50.0


def test_model_with_custom_contagion_engine():
    contagion = ContagionEngine(liquidation_threshold=0.10, cascade_probability=0.5)
    model = PanaModel(contagion_engine=contagion)
    assert model.contagion_engine.liquidation_threshold == 0.10
    assert model.contagion_engine.cascade_probability == 0.5
