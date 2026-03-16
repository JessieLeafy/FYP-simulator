# LLM-Powered Multi-Agent Negotiation Simulator

A configurable multi-agent buyer-seller negotiation simulator where LLM-powered agents negotiate prices through alternating-offer bargaining in simulated markets. Built for an FYP study on how simulator design, protocol design, and market conditions affect negotiation outcomes and aggregate economic behavior.

## Experiments

This repository contains six experiments plus one extension study:

| # | Experiment | Description |
|---|-----------|-------------|
| 1 | Concession dynamics | Compares offer-price trajectories between rule-based and LLM free-language agents |
| 2 | Deadline pressure | Varies max negotiation rounds (6, 12, 20) to measure deadline effects on agreement rates and timing |
| 3 | Market dynamics | Observes price trends, dispersion, and liquidity over multiple market ticks |
| 4 | Supply shock | Compares market outcomes with and without demand/supply shocks |
| 5 | Market mechanism comparison | Compares random vs surplus-maximising buyer-seller matching |
| 6 | Supply-demand shift | Tests whether prices and volume respond to shifts in buyer-value and seller-cost distributions |
| 4-ext | Anchor environment extension | Ablation on Experiment 4: tests whether weak shock response is caused by fixed prompt-level reference price anchors. The fixed-anchor condition reuses the same dataset as Experiment 4. |

All experiments use `llm_free_language` agents with the feasibility gate disabled, except Experiment 1 which includes a `rule_based` baseline condition.

## Requirements

- Python 3.10+
- PyYAML
- An LLM backend: [Ollama](https://ollama.com) (local) or HuggingFace Transformers (GPU)

## Installation

```bash
pip install -e ".[dev]"
```

## Reproducing Experiments

```bash
# Run all six main experiments (3 seeds: 42, 123, 456)
python experiments/run_free_language_all.py

# Run the anchor-mode ablation extension
python experiments/run_shock_anchor_ablation.py

# Single experiment only
python experiments/run_free_language_all.py --only A

# Pilot mode (1 seed, reduced scale)
python experiments/run_free_language_all.py --pilot
```

### LLM Backend Configuration

Experiments default to the HuggingFace backend with `Qwen/Qwen2.5-14B-Instruct` as specified in the YAML configs. To use Ollama instead:

```bash
python experiments/run_free_language_all.py --backend ollama --model llama3.2:3b
```

## Results

Pre-computed results from the final experiment runs (2026-03-13 and 2026-03-14) are in `results/`:

```
results/
  exp1_concession/              # Experiment 1: concession curves
  exp2_deadline/                # Experiment 2: deadline pressure
  exp3_market_dynamics/         # Experiment 3: market dynamics
  exp4_supply_shock/            # Experiment 4: supply shock
  exp4_anchor_environment_extension/  # Experiment 4 extension: anchor ablation
  exp5_mechanism/               # Experiment 5: mechanism comparison
  exp6_supply_demand/           # Experiment 6: supply-demand shift
```

Each experiment directory contains:
- `experiment_summary.json` — aggregate metrics and condition statistics
- One or more CSV files with per-session or per-tick data
- `parse_diagnostics.json` — LLM parsing reliability metrics
- `runs/` — raw per-simulation JSONL event logs

## Project Structure

```
src/
  agents/         # agent implementations (rule_based, llm_free_language)
  core/           # types, config, seeded RNG, event logging
  llm/            # Ollama and HuggingFace backends, prompt construction, JSON schemas
  negotiation/    # session protocol, action judge, parser, feasibility, constraints
  market/         # market simulator, catalog, matching strategies, shocks
  evaluation/     # metrics, statistical utilities, CSV/JSON report writers
experiments/
  run_free_language_all.py       # main experiment runner (Experiments 1-6)
  run_shock_anchor_ablation.py   # anchor-mode ablation runner (Experiment 4 extension)
  experiments.py                 # experiment definitions and orchestration
  configs/                       # YAML experiment configurations
results/                         # final experiment outputs
paper/                           # FYP thesis LaTeX source
tests/                           # unit and integration tests
docs/                            # analysis notes and revision plans
```

## Experiment Configurations

Each experiment is configured via a YAML file in `experiments/configs/`:

| Config | Experiment | Mode | Agent |
|--------|-----------|------|-------|
| `exp_concession.yaml` | 1 - Concession | session, fixed | llm_free_language + rule_based |
| `exp_deadline.yaml` | 2 - Deadline | session, fixed | llm_free_language |
| `exp_market_dynamics.yaml` | 3 - Market dynamics | market, distribution | llm_free_language |
| `exp_shock_response.yaml` | 4 - Supply shock + extension | market, distribution | llm_free_language |
| `exp_mechanism.yaml` | 5 - Mechanism | market, distribution | llm_free_language |
| `exp_supply_demand.yaml` | 6 - Supply-demand | market, distribution | llm_free_language |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Reproducibility

All simulations are seed-controlled. Market generation, agent matching, and parameter sampling are deterministic given the same seed. LLM inference introduces non-determinism from the model itself, but the experimental framework ensures structural reproducibility across runs.

Seeds used in final experiments: 42, 123, 456.
