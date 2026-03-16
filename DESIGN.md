# Architecture Design Document

## 1. Overview

This framework implements a multi-agent negotiation and trading simulation
with LLM-powered agents. Agents bargain over price using alternating offers,
respond strategically to counteroffers, and optimise outcomes subject to
private constraints (value, cost, budget, patience).

The simulator supports two agent types used in the final experiments:

- **`rule_based`** — deterministic linear concession baseline (no LLM).
- **`llm_free_language`** — natural-language LLM agent that produces prices
  via `### PRICE($X) ###` tags and accepts via the `ACCEPT_DEAL` keyword.

The framework supports two LLM backends:

- **Ollama** — local HTTP inference (no API keys).
- **HuggingFace Transformers** — GPU inference with optional quantisation.

The framework enables analysis of:

- **Negotiation patterns** — concession curves, deadline effects, rejection reasons.
- **Market dynamics** — price trends and dispersion, volatility, liquidity.
- **Deal success rates** — by scenario, agent type, matching strategy, and market structure.

---

## 2. Architecture (6-Layer Separation of Concerns)

```
┌──────────────────────────────────────────────────┐
│  Experiment Control (runners / YAML configs)      │
├──────────────────────────────────────────────────┤
│  MarketSimulator  (tick loop, matching, logging) │
├──────────────────────────────────────────────────┤
│  NegotiationSession  (rounds, offer state, term) │
├──────────────────────────────────────────────────┤
│  Agents  (LLM policy wrappers + private state)   │
├──────────────────────────────────────────────────┤
│  ActionJudge  (schema + legality + enforcement)  │
├──────────────────────────────────────────────────┤
│  Settlement & Metrics  (non-LLM computation)     │
└──────────────────────────────────────────────────┘
```

### Layer responsibilities

| Layer | Module(s) | Owns | Does NOT own |
|-------|-----------|------|-------------|
| MarketSimulator | `src/market/simulator.py` | Tick loop, agent creation, matching dispatch, global JSONL log, run directory, anchor tracking | Negotiation logic, LLM calls |
| NegotiationSession | `src/negotiation/session.py` | Rounds, transcript, last_offer, termination, settlement | Agent decisions, constraint rules |
| Agents | `src/agents/*.py` | Decision policy, prompt construction, private reasoning | Validity checking, surplus |
| ActionJudge | `src/negotiation/judge.py` | Schema validation, constraint checking, first-round corrections, enforcement policy | Agent logic, market state |
| Settlement & Metrics | `src/evaluation/metrics.py`, `reports.py`, `stats.py` | Surplus, welfare, aggregates, tick stats, CSV/JSON output | Negotiation flow |
| Experiment Control | `experiments/run_free_language_all.py`, `run_shock_anchor_ablation.py`, `experiments.py` | CLI parsing, config loading, experiment orchestration | Simulation logic |

---

## 3. Module Structure

```
src/
├── core/
│   ├── types.py          # Domain dataclasses (Item, BuyerState, SellerState,
│   │                     #   NegotiationAction, NegotiationTurn, NegotiationResult,
│   │                     #   AgentContext, MarketTickStats)
│   ├── config.py         # SimulationConfig, LLMConfig, MarketConfig,
│   │                     #   NegotiationConfig, ShockConfig, FixedScenarioConfig,
│   │                     #   PromptConfig, load_config
│   ├── rng.py            # SeededRNG (deterministic randomness with fork())
│   └── logging.py        # EventLogger (JSONL: turn, result, risk, tick_end)
│
├── agents/
│   ├── base.py           # BaseAgent (abstract: decide, agent_type)
│   ├── rule_based.py     # RuleBasedAgent (linear concession, no LLM)
│   ├── llm_free_language.py  # LLMFreeLanguageAgent (natural-language + price tags)
│   └── llm_utils.py      # Shared LLM pipeline: call_llm_free_language,
│                          #   call_llm_and_parse, to_action, fallback_action
│
├── llm/
│   ├── backend.py        # OllamaLLMBackend (HTTP, retry, timeout)
│   ├── hf_backend.py     # HuggingFaceBackend (Transformers, GPU, quantisation)
│   ├── prompts.py        # Prompt builders (free_language, reactive, deliberative)
│   └── schemas.py        # Action JSON schema, FORMAT_ERROR_PROMPT, rethink prompts
│
├── negotiation/
│   ├── session.py        # NegotiationSession (first-class session object)
│   ├── judge.py          # ActionJudge (validate + enforce)
│   ├── constraints.py    # validate_action, ValidationResult
│   ├── parser.py         # extract_json, validate_action_json, extract_price_from_text,
│   │                     #   detect_accept_intent, _attempt_repair
│   └── feasibility.py    # compute_utility, is_offer_feasible (deterministic gate)
│
├── market/
│   ├── simulator.py      # MarketSimulator (orchestration, anchor tracking)
│   ├── matcher.py        # Matcher interface + RandomMatcher, SurplusMaxMatcher
│   │                     #   (also SortedMatcher, RoundRobinMatcher — unused in final experiments)
│   ├── matching.py       # generate_buyers/sellers, adjust_pair_for_item,
│   │                     #   validate_market_coherence
│   ├── catalog.py        # Catalog (item generation with reference prices)
│   └── shocks.py         # apply_shocks (demand/supply multipliers)
│
└── evaluation/
    ├── metrics.py        # compute_metrics, compute_tick_stats,
    │                     #   compute_allocative_efficiency, compute_surplus_gini
    ├── stats.py          # pearson_correlation, simple_linear_regression
    ├── reports.py        # write_summary, write_deals_csv, write_concession_csv,
    │                     #   write_deadline_csv, write_anchoring_csv,
    │                     #   write_mechanism_csv, write_tick_stats_csv,
    │                     #   write_experiment_summary
    └── parse_diagnostics.py  # LLM parsing reliability metrics for free-language agents
```

---

## 4. Data Models

### 4.1 Agent State

```python
@dataclass
class BuyerState:
    buyer_id: str
    value: float               # max willingness-to-pay
    budget: float              # hard spending cap
    patience: int              # informational

@dataclass
class SellerState:
    seller_id: str
    cost: float                # reservation price (floor)
    target_margin: float       # desired profit fraction
    patience: int
```

### 4.2 Actions & Offers

```python
class ActionType(str, Enum):
    OFFER = "offer"            # first proposal
    COUNTER = "counter"        # subsequent counter-offer
    ACCEPT = "accept"          # accept opponent's last offer
    REJECT = "reject"          # walk away / end negotiation

@dataclass
class NegotiationAction:
    action: ActionType
    offer_price: Optional[float]
    message_public: str        # visible to opponent
    rationale_private: str     # private reasoning (not shared)
```

**Free-language output format:**
The `llm_free_language` agent produces natural text containing price tags
(`### PRICE($X) ###`) and optional accept keywords (`ACCEPT_DEAL`). The
parser in `llm_utils.py` extracts actions from this format.

**Structured JSON schema (used by parser internals):**
```json
{
    "action": "offer" | "counter" | "accept" | "reject",
    "offer_price": <number | null>,
    "message_public": "<string>",
    "rationale_private": "<string>"
}
```

### 4.3 Session State

```python
class NegotiationSession:
    transcript: list[NegotiationTurn]  # full round-by-round log
    risk_events: list[dict]            # constraint violations
    last_offer: Optional[float]        # most recent proposed price
    current_round: int
    is_complete: bool
    judge: ActionJudge                 # validates each action
    gate_enabled: bool                 # deterministic feasibility gate toggle
```

### 4.4 Outcome

```python
@dataclass
class NegotiationResult:
    item: Item
    buyer_id: str
    seller_id: str
    deal_made: bool
    deal_price: Optional[float]
    termination_reason: TerminationReason
    rounds_taken: int
    history: list[NegotiationTurn]
    buyer_value: float
    seller_cost: float
    buyer_surplus: float
    seller_surplus: float
    risk_events: list[dict]
    time_step: int
```

### 4.5 Market Tick Stats

```python
@dataclass
class MarketTickStats:
    tick: int
    num_sessions: int
    deals_made: int
    fail_rate: float               # (total - deals) / total
    mean_price: float
    price_std: float               # price dispersion
    liquidity: float               # deals / sessions
    buyer_surplus_mean: float
    seller_surplus_mean: float
```

---

## 5. Logging Schema (JSONL)

All events are written to `events.jsonl` as newline-delimited JSON.

### 5.1 Turn event

```json
{
    "event": "turn",
    "time_step": 0,
    "item_id": "item_001",
    "buyer_id": "buyer_t0_000",
    "seller_id": "seller_t0_000",
    "round": 0,
    "role": "buyer",
    "action": "offer",
    "offer_price": 85.0,
    "message_public": "I propose $85.00.",
    "raw_llm_output": "...",
    "timestamp": 1700000000.0
}
```

### 5.2 Session result event

```json
{
    "event": "result",
    "time_step": 0,
    "item_id": "item_001",
    "buyer_id": "buyer_t0_000",
    "seller_id": "seller_t0_000",
    "deal_made": true,
    "deal_price": 95.0,
    "termination": "accepted",
    "rounds_taken": 4,
    "buyer_value": 120.0,
    "seller_cost": 70.0,
    "buyer_surplus": 25.0,
    "seller_surplus": 25.0,
    "risk_events_count": 0
}
```

### 5.3 Risk event

```json
{
    "event": "risk",
    "round": 2,
    "role": "buyer",
    "violation_type": "budget",
    "reason": "Buyer offer $135.00 exceeds budget $110.00",
    "attempted_action": "offer",
    "attempted_price": 135.0,
    "time_step": 0
}
```

### 5.4 Tick-end event (market mode only)

```json
{
    "event": "tick_end",
    "tick": 0,
    "num_sessions": 5,
    "deals_made": 3,
    "fail_rate": 0.4,
    "mean_price": 92.5,
    "price_std": 4.33,
    "liquidity": 0.6,
    "buyer_surplus_mean": 18.5,
    "seller_surplus_mean": 15.3
}
```

---

## 6. Action Validation Pipeline

The validation pipeline has three layers, consolidated under `ActionJudge`:

```
LLM raw text
    │
    ▼
[Parser] extract_price_from_text / detect_accept_intent    (free-language)
         OR extract_json → validate_action_json             (structured)
    │
    ▼
[Judge]  correct_first_round → validate → enforce           (domain-level)
    │
    ▼
Valid NegotiationAction  or  REJECT + risk_event
```

1. **Parser** (`parser.py`): For free-language agents, extracts prices via
   `### PRICE($X) ###` tags and detects accept intent via `ACCEPT_DEAL`.
   For structured agents, extracts JSON using 4 strategies (direct, markdown
   fences, brace extraction, heuristic repair). Validates required fields
   and schema. One retry with `FORMAT_ERROR_PROMPT` if invalid.

2. **ActionJudge** (`judge.py`): Receives a parsed `NegotiationAction` and:
   - Corrects first-round illegalities (COUNTER→OFFER, ACCEPT/REJECT→OFFER)
   - Validates against hard constraints (budget, cost, bounds, logic)
   - Enforces: invalid actions are replaced with REJECT + risk event logged

3. **Enforcement policy**: Invalid → REJECT with risk event.

---

## 7. Market Simulation Flow

```
MarketSimulator.run()
│
├── for tick in range(num_ticks):
│   ├── fork RNG for this tick
│   ├── generate_buyers(rng, count, tick, market_cfg, fixed_cfg)
│   ├── generate_sellers(rng, count, tick, market_cfg, fixed_cfg)
│   ├── apply_shocks(buyers, sellers, rng, shock_cfg)
│   ├── pairs = matcher.match(buyers, sellers, items, rng)
│   ├── [coherent_sampling] adjust_pair_for_item(buyer, seller, item, ...)
│   ├── validate_market_coherence(pairs)
│   ├── [anchor_mode] apply anchor adjustments to item reference prices
│   │
│   ├── for (buyer, seller, item) in pairs:
│   │   ├── create buyer_agent, seller_agent
│   │   ├── session = NegotiationSession(...)
│   │   ├── result = session.run()
│   │   └── log_result(result)
│   │
│   ├── [market mode] compute_tick_stats → log_tick_stats
│   └── [anchor_mode=updated] update effective anchors from deal prices
│
├── compute_metrics(all_results)
├── write_summary(metrics, run_dir)
└── write_deals_csv(results, run_dir)
```

### Anchor modes

The simulator supports three anchor modes for the item reference price
provided in agent prompts, controlled by `market.anchor_mode`:

| Mode | Behaviour |
|------|-----------|
| `fixed` | Reference price is unchanged across ticks (default). |
| `updated` | Reference price is updated to the mean deal price after each tick. |
| `no_anchor` | Reference price is set to 0.0, effectively removing the anchor from prompts. |

### Matching strategies

```python
class Matcher(ABC):
    @abstractmethod
    def match(self, buyers, sellers, items, rng) -> list[tuple]:
        ...
```

The final experiments use only two matchers:

| Strategy | Class | Description |
|----------|-------|-------------|
| `random` | `RandomMatcher` | Random 1:1 pairing (baseline, default) |
| `surplus_max` | `SurplusMaxMatcher` | Greedy max-ZOPA pairing (used in Experiment 5) |

`SortedMatcher` and `RoundRobinMatcher` also exist in the codebase but are
not used in any final experiment. They were built for planned reputation and
communication experiments that were descoped from the thesis.

Configured via `matching:` in YAML config or overridden per-condition in
`experiments/experiments.py`.

---

## 8. Experiment Workflow

### 8.1 Running experiments

```bash
# Run all six main experiments (3 seeds: 42, 123, 456)
python experiments/run_free_language_all.py

# Run the anchor-mode ablation extension
python experiments/run_shock_anchor_ablation.py

# Single experiment only
python experiments/run_free_language_all.py --only A

# Pilot mode (1 seed, reduced scale)
python experiments/run_free_language_all.py --pilot

# Override LLM backend
python experiments/run_free_language_all.py --backend ollama --model llama3.2:3b
```

### 8.2 Experiment orchestration

`experiments/experiments.py` defines the core experiment functions:

| Function | Experiment |
|----------|-----------|
| `run_concession()` | Exp 1 — Concession dynamics |
| `run_deadline()` | Exp 2 — Deadline pressure |
| `run_market_dynamics()` | Exp 3 — Market dynamics |
| `run_shock_response()` | Exp 4 — Supply shock |
| `run_mechanism()` | Exp 5 — Mechanism comparison |
| `run_supply_demand()` | Exp 6 — Supply-demand shift |
| `run_shock_anchor_ablation()` | Exp 4 extension — Anchor ablation |

### 8.3 YAML config example

```yaml
agent_type: llm_free_language
mode: market
steps: 10
buyers_per_step: 10
sellers_per_step: 10
seed: 42
scenario_mode: distribution

llm:
  backend: huggingface
  model: Qwen/Qwen2.5-14B-Instruct
  device: auto
  temperature: 0.2
  max_tokens: 512

negotiation:
  max_rounds: 10
  min_price: 1.0
  max_price: 500.0
  gate_enabled: false

shock:
  enabled: false
```

---

## 9. Key Class & Method Signatures

### MarketSimulator

```python
class MarketSimulator:
    def __init__(self, config: SimulationConfig, rng: SeededRNG,
                 backend: Optional[OllamaLLMBackend | HuggingFaceBackend] = None): ...
    def run(self, on_session: Callable | None = None) -> list[NegotiationResult]: ...
    # attributes:
    matcher: Matcher
    results: list[NegotiationResult]
    tick_stats: list[MarketTickStats]
    run_dir: str
```

### NegotiationSession

```python
class NegotiationSession:
    def __init__(self, buyer_agent, seller_agent, item, buyer, seller,
                 max_rounds=10, min_price=1.0, max_price=500.0,
                 event_logger=None, time_step=0,
                 gate_enabled=False): ...
    def run(self) -> NegotiationResult: ...
    # attributes:
    transcript: list[NegotiationTurn]
    risk_events: list[dict]
    last_offer: Optional[float]
    is_complete: bool
    gate_enabled: bool
    result: Optional[NegotiationResult]  # property
```

### ActionJudge

```python
class ActionJudge:
    def __init__(self, min_price=1.0, max_price=500.0): ...
    def correct_first_round(self, action, role, buyer, seller) -> NegotiationAction: ...
    def validate(self, role, action, buyer, seller, last_offer, item, round_number) -> ValidationResult: ...
    def enforce(self, role, action, buyer, seller, last_offer, item, round_number, time_step=0) -> tuple[NegotiationAction, Optional[dict]]: ...
```

### LLM Agent Pipeline

```python
# src/agents/llm_utils.py
def to_action(obj: dict) -> NegotiationAction: ...
def fallback_action(ctx: AgentContext) -> NegotiationAction: ...
def call_llm_and_parse(backend, prompt, ctx) -> NegotiationAction: ...
def call_llm_free_language(backend, prompt, ctx) -> NegotiationAction: ...
```

### Metrics

```python
def compute_metrics(results: list[NegotiationResult]) -> dict[str, Any]: ...
def compute_tick_stats(tick: int, results: list[NegotiationResult]) -> MarketTickStats: ...
def compute_allocative_efficiency(results: list[NegotiationResult]) -> float: ...
def compute_surplus_gini(surpluses: list[float]) -> float: ...
```

---

## 10. Communication Strategies

Prompt-level communication strategy injection is supported via
`prompt.communication_strategy` in the YAML config:

| Strategy | Description |
|----------|-------------|
| `neutral` | No messaging instructions (default) |
| `assertive` | Firm, confident tone; emphasise constraints |
| `collaborative` | Cooperative, friendly; acknowledge opponent's interests |
| `strategic` | Maximise advantage; may exaggerate or withhold true constraints |

---

## 11. Feasibility Gate

The deterministic feasibility gate (`src/negotiation/feasibility.py`) checks
whether the opponent's standing offer yields positive surplus for the agent.
When the condition is met and `gate_enabled=True`, the agent accepts without
calling the LLM.

In the final experiments, the gate is **disabled** (`gate_enabled: false` in
all YAML configs) so that all decisions flow through the LLM agent. The gate
remains in the codebase for ablation purposes and is tested in
`tests/test_feasibility_gate.py`.
