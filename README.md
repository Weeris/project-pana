# Project PANA (พนา) 🌲

> *The Forester's Living Sandbox for Green Swan Events*

**PANA** (Thai: พนา, pronounced *pa-naa*) is an Agentic AI-driven, cross-border ESG
transition simulator. Central Banks and financial regulators observe emergent
systemic reflexivity — the feedback loops between ESG policy shocks, agent
behaviour, and market contagion — inside a controlled computational sandbox.

---

## The Forest Metaphor

In Thai, **พนา** means "forest." Just as a forester tends a living ecosystem —
nurturing growth, watching for disease, understanding how fire spreads through
connected trees — the PANA dashboard lets regulators tend the financial ecosystem.

- **Agents** are individual trees (banks, firms, jurisdictions).
- **Contagion** spreads like a forest fire through the network graph.
- **ESG policy** is the climate — carbon tax is drought, green subsidy is rain.
- **The Forester** adjusts dials and watches the system respond.

---

## Technical Architecture

```
app.py              Streamlit UI (Forester Control Panel)
src/
  agents/           Agent archetypes (BaseAgent, BankAgent, FirmAgent)
  engine/           Mesa ABM model + Market Bridge + Jurisdiction
  intelligence/     LangChain LLM orchestrator (Systemic-Risk Aware)
  utils/            Financial math utilities
tests/              pytest unit tests
```

### Agent State Machine

Each agent runs a **Pana-Brain Loop** every simulation step:

1. **Perceive** — read the Global Policy String (e.g. "Carbon tax $50/t in EU")
2. **Reason** — LLM (or rule-based fallback) analyses balance-sheet impact
3. **Act** — update ESG score, log reasoning, push orders to Market Bridge

Agents are **Systemic-Risk Aware**: they balance survival (Tier 1 Capital),
profit, and ESG compliance simultaneously.

### Cross-Border Market Bridge

- **Global Order Book** for Carbon Credits and Green Bonds
- **Jurisdiction objects** with independent interest rates, carbon tax, and subsidy
- **Contagion Engine** detecting liquidation cascades via probabilistic cascade propagation

### ABM Engine (Mesa)

- `PanaModel` orchestrates time-steps with `mesa.time.RandomActivation`
- Small-world network (Watts-Strogatz, k=4, p=0.3) connects agents realistically
- `NetworkGrid` used for contagion routing

---

## Prerequisites

- Python 3.10+
- (Optional, for LLM reasoning) [Ollama](https://ollama.com) with `llama3` or `mistral`

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/project-pana.git
cd project-pana

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Enable LLM reasoning
ollama pull llama3    # or: ollama pull mistral
ollama serve          # keep running in background

# 5. Launch the Forester Control Panel
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Using the Dashboard

1. Click **🚀 Initialise / Reset Sandbox** to create the agent population
2. Use the sidebar sliders to set:
   - **Carbon Tax Rate** — simulates a carbon pricing shock
   - **Green Subsidy Level** — government incentive for green capex
   - **Shock Intensity** — exogenous brown-asset price drop
   - **Number of agents** — scale the simulation
3. Toggle **Enable LLM Reasoning** if Ollama is running
4. Click **▶️ Step Simulation** to advance one tick
5. Watch **ESG Scores**, **Liquidity Gaps**, and the **Contagion Map** update in real time
6. Read the **Thought Stream** panel to see agent reasoning traces

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Testing with Ollama (Live LLM Reasoning)

When Ollama is running, agents use a LangChain + Ollama pipeline for genuine
LLM-driven reasoning instead of the rule-based fallback.

### 1. Check if Ollama is installed

```bash
ollama --version
```

### 2. Pull a model

```bash
ollama pull llama3    # ~5 GB, good balance of speed and quality
# or
ollama pull mistral   # smaller, faster
```

### 3. Start the Ollama server

```bash
ollama serve
```

Keep it running in a terminal or as a background process.

### 4. Launch the dashboard with LLM enabled

```bash
streamlit run app.py
```

In the sidebar, toggle **Enable LLM Reasoning** and select your model.
After initialising the sandbox, click **Step Simulation** — agent reasoning
traces will appear in the **💭 Thought Stream** panel.

If Ollama is not running, the app falls back to rule-based reasoning automatically
(the toggle will show a warning or the model select will be greyed out).

### Verifying Ollama is responding

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3",
  "prompt": "Why might a bank reduce its green assets during a carbon tax hike?",
  "stream": false
}'
```

A JSON response with an `response` field confirms Ollama is up.

---

## MIT Licence

Copyright (c) 2025 Project PANA Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
