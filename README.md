# Multi-Agent Negotiation & Trading Simulator

A reproducible simulation framework where LLM-powered buyer and seller agents negotiate over prices using alternating offers. Built for FYP research on multi-agent market dynamics.

## Features

- **Four agent types**: rule-based baseline, LLM reactive, LLM deliberative (structured reasoning), and memory-augmented
- **Ollama backend**: local LLM inference via HTTP — no API keys, runs fully offline
- **Deterministic**: seeded RNG ensures reproducible results across runs
- **Hard safety constraints**: budget/cost violations are blocked and logged as risk events
- **Structured outputs**: agents produce strict JSON; robust parsing with automatic repair
- **Rich evaluation**: deal success rate, surplus, price distribution, deadlock rate, risk metrics
- **Parameter sweeps**: grid search over seeds, agent types, and negotiation parameters

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) (only needed for LLM agent types)

## Installation

```bash
# Install with pip (editable mode)
pip install -e ".[dev]"

# Or just install the one external dependency
pip install pyyaml
```

## Ollama Setup (for LLM agents only)

```bash
# 1. Install Ollama — https://ollama.com
# 2. Pull a model
ollama pull qwen2.5:3b

# 3. Verify it works
curl http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5:3b","prompt":"Say hello","stream":false}'
```

## Quick Start

### Rule-based baseline (no LLM needed)

```bash
python experiments/run.py --config experiments/configs/baseline.yaml --seed 42
```

### LLM reactive agents

```bash
python experiments/run.py --config experiments/configs/llm_reactive.yaml --seed 42
```

### LLM deliberative agents

```bash
python experiments/run.py --config experiments/configs/llm_deliberative.yaml --seed 42
```

### Mixed: rule-based buyers vs LLM sellers

```bash
python experiments/run.py \
  --config experiments/configs/baseline.yaml \
  --buyer_agent_type rule_based \
  --seller_agent_type llm_reactive \
  --steps 5 --buyers_per_step 10 --sellers_per_step 10
```

### CLI override examples

```bash
python experiments/run.py \
  --config experiments/configs/baseline.yaml \
  --seed 123 \
  --steps 50 \
  --buyers_per_step 100 \
  --sellers_per_step 100 \
  --max_rounds 15
```

### Parameter sweep

```bash
python experiments/sweep.py \
  --config experiments/configs/baseline.yaml \
  --seeds 42 123 456 \
  --agent_types rule_based \
  --max_rounds_list 5 10 15
```

## Output Structure

Each run produces a timestamped directory under `outputs/runs/`:

```
outputs/runs/20260208_143000_s42/
  events.jsonl    # every turn + result as newline-delimited JSON
  summary.json    # aggregate metrics
  deals.csv       # one row per negotiation
```

### Key metrics in `summary.json`

| Metric | Description |
|--------|-------------|
| `deal_success_rate` | Fraction of negotiations that reached a deal |
| `avg_price` / `median_price` | Deal price statistics |
| `buyer_surplus_mean` | Average (value − price) for deals |
| `seller_surplus_mean` | Average (price − cost) for deals |
| `avg_rounds_to_close` | Mean rounds for successful deals |
| `deadlock_rate` | Fraction of negotiations that timed out |
| `budget_violation_attempts` | Blocked buyer constraint violations |
| `cost_violation_attempts` | Blocked seller constraint violations |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
src/
  core/           # types, config, RNG, logging
  llm/            # Ollama backend, prompts, JSON schemas
  agents/         # base, rule_based, llm_reactive, llm_deliberative, memory
  negotiation/    # protocol, constraints, parser
  market/         # catalog, matching, simulator, shocks
  evaluation/     # metrics, reports
experiments/
  run.py          # single-run CLI
  sweep.py        # parameter sweep CLI
  configs/        # YAML configurations
tests/            # unit + integration tests
```

## Reproducibility

All simulations are deterministic given the same `--seed`. The RNG is forked per time step to isolate randomness. LLM agents introduce non-determinism from the model itself, but the market generation and matching remain reproducible.
