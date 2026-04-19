"""app.py: Streamlit Forester Control Panel for Project PANA."""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx

from src.engine.pana_model import PanaModel
from src.engine.jurisdiction import Jurisdiction
from src.engine.market_bridge import ContagionEngine
from src.intelligence.llm_orchestrator import PanaLLMOrchestrator

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Project PANA — พนา | Forester Control Panel",
    layout="wide",
    page_icon="🌲",
)

# ── Session state ────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "model": None,
        "orchestrator": None,
        "step": 0,
        "policy_log": [],
        "metrics_history": [],
        "thought_stream": [],
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_state()

# ── Sidebar Controls ─────────────────────────────────────────────────────────
st.sidebar.header("🌿 Forester Controls")

carbon_tax = st.sidebar.slider(
    "Carbon Tax Rate (USD/tonne CO₂)", 0, 200, 0, step=5,
    help="Simulates a carbon pricing shock across all jurisdictions."
)
green_subsidy = st.sidebar.slider(
    "Green Subsidy Level (%)", 0.0, 1.0, 0.0, step=0.05,
    help="Government subsidy fraction for qualifying green capex."
)
shock_intensity = st.sidebar.slider(
    "Shock Intensity (price drop %)", 0.0, 0.5, 0.0, step=0.01,
    help="Exogenous asset price shock applied to brown assets."
)
num_banks = st.sidebar.slider("Number of Bank Agents", 1, 20, 5)
num_firms = st.sidebar.slider("Number of Firm Agents", 1, 30, 10)
use_llm = st.sidebar.toggle("Enable LLM Reasoning (requires Ollama)", value=False)
llm_model = st.sidebar.selectbox("SLM Model", ["llama3", "mistral"], disabled=not use_llm)

if st.sidebar.button("🚀 Initialise / Reset Sandbox", use_container_width=True):
    jurisdictions = [
        Jurisdiction("EU", carbon_tax_rate=carbon_tax, green_subsidy=green_subsidy),
        Jurisdiction("US", carbon_tax_rate=carbon_tax * 0.8, green_subsidy=green_subsidy * 0.9),
        Jurisdiction("SG", carbon_tax_rate=carbon_tax * 1.2, green_subsidy=green_subsidy * 1.1),
    ]
    contagion = ContagionEngine(liquidation_threshold=shock_intensity)
    model = PanaModel(
        num_banks=num_banks,
        num_firms=num_firms,
        jurisdictions=jurisdictions,
        contagion_engine=contagion,
    )
    orchestrator = PanaLLMOrchestrator(use_llm=use_llm, model_name=llm_model)

    policy = f"Carbon tax ${carbon_tax}/t | Green subsidy {green_subsidy:.0%}"
    model.set_policy(policy)

    st.session_state.model = model
    st.session_state.orchestrator = orchestrator
    st.session_state.step = 0
    st.session_state.policy_log = [policy]
    st.session_state.metrics_history = [model.get_systemic_metrics()]
    st.session_state.thought_stream = []
    st.rerun()

if st.sidebar.button("▶️ Step Simulation", use_container_width=True):
    model = st.session_state.model
    orchestrator = st.session_state.orchestrator

    if model is None:
        st.error("Initialise the sandbox first.")
    else:
        new_policy = (
            f"Step {st.session_state.step+1}: "
            f"Carbon tax ${carbon_tax}/t | Green subsidy {green_subsidy:.0%}"
        )
        model.set_policy(new_policy)

        thought_lines = []
        for agent in model.agents:
            bs = agent.balance_sheet
            if shock_intensity > 0 and bs.Brown_Assets > 0:
                bs.Brown_Assets *= (1 - shock_intensity)

            if orchestrator is not None:
                thought = orchestrator.reason_for_agent(agent, new_policy)
                agent.log_thought(thought)
                thought_lines.append(thought)

        result = model.step()
        st.session_state.step = result["step"]
        st.session_state.policy_log.append(new_policy)

        metrics = model.get_systemic_metrics()
        st.session_state.metrics_history.append(metrics)
        st.session_state.thought_stream.extend(thought_lines[-10:])

# ── Main Panel ───────────────────────────────────────────────────────────────
st.title("🌲 Project PANA (พนา) — Green Swan Simulator")
st.caption("Agentic AI · Cross-Border ESG Transition · Systemic Reflexivity")

col_main, col_thought = st.columns([3, 1])

with col_main:
    m = st.session_state.metrics_history[-1] if st.session_state.metrics_history else {}
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Step", st.session_state.step)
    mc2.metric("Avg ESG Score", m.get("avg_esg_score", "—"))
    mc3.metric("Liquidity Gap", f"${m.get('total_liquidity_gap', 0):,.0f}")
    mc4.metric("Contagion Risk", f"{m.get('contagion_risk_ratio', 0):.0%}")

    # --- Liquidity Gap Chart ---
    st.subheader("📉 Liquidity Gaps Over Time")
    if len(st.session_state.metrics_history) > 1:
        df_gap = {
            "Step": list(range(len(st.session_state.metrics_history))),
            "Liquidity Gap": [x["total_liquidity_gap"] for x in st.session_state.metrics_history],
        }
        fig_gap = px.line(df_gap, x="Step", y="Liquidity Gap", title="Systemic Liquidity Gap")
        st.plotly_chart(fig_gap, use_container_width=True)
    else:
        st.info("Run at least 2 steps to see the Liquidity Gap chart.")

    # --- ESG Score Chart ---
    st.subheader("🌿 ESG Score Distribution")
    if st.session_state.model:
        esg_data = {
            "Agent": [a.agent_id for a in st.session_state.model.agents],
            "ESG Score": [a.esg_score for a in st.session_state.model.agents],
            "Type": [a.agent_type.value for a in st.session_state.model.agents],
        }
        fig_esg = px.bar(
            esg_data, x="Agent", y="ESG Score",
            color="Type", color_discrete_map={"bank": "#2E7D32", "firm": "#1565C0"},
            title="Agent ESG Scores"
        )
        st.plotly_chart(fig_esg, use_container_width=True)

    # --- Contagion Map ---
    st.subheader("🧬 Contagion Map")
    if st.session_state.model:
        G = st.session_state.model.network
        pos = nx.spring_layout(G, seed=42, k=2)

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y, line=dict(width=0.5, color="#888"),
            hoverinfo="none", mode="lines"
        )

        node_x, node_y, node_text, node_color = [], [], [], []
        for i, agent in enumerate(st.session_state.model.agents):
            x, y = pos[i]
            node_x.append(x)
            node_y.append(y)
            node_text.append(
                f"{agent.agent_id}<br>ESG: {agent.esg_score:.0f}<br>"
                f"Tier1: {agent.compute_tier1_capital():.0f}"
            )
            node_color.append(agent.esg_score)

        node_trace = go.Scatter(
            x=node_x, y=node_y, text=node_text, mode="markers+text",
            hoverinfo="text",
            marker=dict(
                showscale=True, colorscale="RdYlGn",
                color=node_color, size=14,
                colorbar=dict(title="ESG Score")
            ),
            textposition="top center",
            textfont=dict(size=7),
        )

        fig_map = go.Figure(data=[edge_trace, node_trace])
        fig_map.update_layout(
            title="Agent Network — Colour = ESG Score",
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Initialise the sandbox to see the Contagion Map.")

with col_thought:
    st.subheader("💭 Thought Stream")
    thoughts = st.session_state.thought_stream[-20:]
    if thoughts:
        for t in reversed(thoughts):
            st.code(t[:200] + ("..." if len(t) > 200 else ""), language=None)
            st.divider()
    else:
        st.info("Agent reasoning will appear here after stepping.")

# ── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Project PANA (พนา) · พนา means 'forest' in Thai — the Forester tends the systemic garden. "
    "MIT License · Agentic ESG Transition Simulator"
)
