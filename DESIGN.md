# Architecture Design Document

## 1. Overview & FYP Alignment

This framework implements a multi-agent negotiation and trading simulation
with LLM-powered agents.  Agents bargain over price using alternating offers,
respond strategically to counteroffers, and optimise outcomes subject to
private constraints (value, cost, budget, patience).

The framework enables analysis of:
- **Negotiation patterns** — concession curves, anchoring, deadline effects, rejection reasons.
- **Market fluctuations** — price trends and dispersion, volatility proxies, liquidity.
- **Deal success rates** — by scenario, agent type, matching strategy, and information asymmetry.

---

## 2. Architecture (6-Layer Separation of Concerns)

```
┌──────────────────────────────────────────────────┐
│  Experiment Control (CLI / sweep / YAML configs) │
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
| MarketSimulator | `src/market/simulator.py` | Tick loop, agent creation, matching dispatch, global JSONL log, run directory | Negotiation logic, LLM calls |
| NegotiationSession | `src/negotiation/session.py` | Rounds, transcript, last_offer, termination, settlement | Agent decisions, constraint rules |
| Agents | `src/agents/*.py` | Decision policy, prompt construction, private reasoning | Validity checking, surplus |
| ActionJudge | `src/negotiation/judge.py` | Schema validation, constraint checking, first-round corrections, enforcement policy | Agent logic, market state |
| Settlement & Metrics | `src/evaluation/metrics.py`, `reports.py` | Surplus, welfare, aggregates, tick stats, CSV/JSON output | Negotiation flow |
| Experiment Control | `experiments/run.py`, `sweep.py` | CLI parsing, config loading, overrides | Simulation logic |

---

## 3. Module Structure

```
src/
├── core/
│   ├── types.py          # Domain dataclasses (Item, BuyerState, SellerState,
│   │                     #   NegotiationAction, NegotiationTurn, NegotiationResult,
│   │                     #   Offer, Outcome, MarketTickStats, AgentContext)
│   ├── config.py         # SimulationConfig, LLMConfig, MarketConfig, etc.
│   ├── rng.py            # SeededRNG (deterministic randomness)
│   └── logging.py        # EventLogger (JSONL: turn, result, risk, tick_end)
│
├── agents/
│   ├── base.py           # BaseAgent (abstract: decide, agent_type)
│   ├── rule_based.py     # RuleBasedAgent (linear concession, no LLM)
│   ├── llm_utils.py      # to_action, fallback_action, call_llm_and_parse
│   ├── llm_reactive.py   # LLMReactiveAgent (single-shot)
│   ├── llm_deliberative.py  # LLMDeliberativeAgent (structured reasoning)
│   └── memory_agent.py   # MemoryStore + MemoryAgent (episodic memory)
│
├── llm/
│   ├── backend.py        # OllamaLLMBackend (HTTP, retry, timeout)
│   ├── prompts.py        # Prompt builders (reactive, deliberative, memory)
│   └── schemas.py        # Action JSON schema + FORMAT_ERROR_PROMPT
│
├── negotiation/
│   ├── session.py        # NegotiationSession (first-class session object)
│   ├── judge.py          # ActionJudge (validate + enforce)
│   ├── constraints.py    # validate_action, ValidationResult
│   ├── parser.py         # extract_json, validate_action_json, _attempt_repair
│   └── protocol.py       # run_negotiation (backwards-compat wrapper)
│
├── market/
│   ├── simulator.py      # MarketSimulator (orchestration)
│   ├── matcher.py        # Matcher interface + RandomMatcher
│   ├── matching.py       # ParameterSource, generate_buyers/sellers, match_pairs
│   ├── catalog.py        # Catalog (item generation)
│   └── shocks.py         # apply_shocks (demand/supply multipliers)
│
└── evaluation/
    ├── metrics.py        # compute_metrics, compute_tick_stats
    └── reports.py        # write_summary, write_deals_csv
```

---

## 4. Data Models

### 4.1 Agent State

```python
@dataclass
class BuyerState:              # ~ AgentProfile (buyer)
    buyer_id: str
    value: float               # max willingness-to-pay
    budget: float              # hard spending cap
    patience: int              # informational

@dataclass
class SellerState:             # ~ AgentProfile (seller)
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
class NegotiationAction:       # ~ Action
    action: ActionType
    offer_price: Optional[float]
    message_public: str        # visible to opponent
    rationale_private: str     # private reasoning (not shared)

@dataclass
class Offer:
    price: float
    round_number: int
    proposer_role: AgentRole
```

**LLM action schema (strict JSON):**
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
```

### 4.4 Outcome

```python
@dataclass
class Outcome:
    status: str                    # "deal" | "no_deal" | "timeout"
    agreed_price: Optional[float]
    rounds: int
    buyer_surplus: float           # value - price
    seller_surplus: float          # price - cost
    welfare: float                 # buyer_surplus + seller_surplus

@dataclass
class NegotiationResult:           # full result record
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
[Parser] extract_json → validate_action_json   (schema-level)
    │
    ▼
[Judge]  correct_first_round → validate → enforce  (domain-level)
    │
    ▼
Valid NegotiationAction  or  REJECT + risk_event
```

1. **Parser** (`parser.py`): Extracts JSON from LLM output using 4 strategies
   (direct, markdown fences, brace extraction, heuristic repair).  Validates
   required fields and schema.  One retry with `FORMAT_ERROR_PROMPT` if invalid.

2. **ActionJudge** (`judge.py`): Receives a parsed `NegotiationAction` and:
   - Corrects first-round illegalities (COUNTER→OFFER, ACCEPT/REJECT→OFFER)
   - Validates against hard constraints (budget, cost, bounds, logic)
   - Enforces: invalid actions are replaced with REJECT + risk event logged

3. **Enforcement policy**: Invalid → REJECT (configurable in future:
   repeat-turn, default-offer, etc.).

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
│   │
│   ├── for (buyer, seller, item) in pairs:
│   │   ├── create buyer_agent, seller_agent
│   │   ├── session = NegotiationSession(...)
│   │   ├── result = session.run()
│   │   ├── log_result(result)
│   │   └── feed memory agents
│   │
│   └── [market mode] compute_tick_stats → log_tick_stats
│
├── compute_metrics(all_results)
├── write_summary(metrics, run_dir)
└── write_deals_csv(results, run_dir)
```

### Matcher interface

```python
class Matcher(ABC):
    @abstractmethod
    def match(self, buyers, sellers, items, rng) -> list[tuple]:
        ...

class RandomMatcher(Matcher):  # current implementation
    ...
# Future: PreferenceMatcher, AuctionMatcher, etc.
```

---

## 8. Experiment Workflow

### 8.1 Single run

```bash
# Session mode (legacy, default):
python experiments/run.py --config experiments/configs/baseline.yaml

# Market mode (with tick stats):
python experiments/run.py --config experiments/configs/baseline.yaml \
    --mode market --ticks 10 --num_buyers 20 --num_sellers 20

# Fixed scenario:
python experiments/run.py --config experiments/configs/fixed_single.yaml \
    --mode market
```

### 8.2 Parameter sweep

```bash
python experiments/sweep.py --config experiments/configs/baseline.yaml \
    --seeds 42 123 456 --agent_types rule_based llm_reactive \
    --max_rounds_list 5 10 15 --steps 3
```

### 8.3 YAML config example (market mode)

```yaml
mode: market
agent_type: rule_based
steps: 10          # = num_ticks in market mode
buyers_per_step: 20
sellers_per_step: 20
seed: 42
matching: random

negotiation:
  max_rounds: 8
  min_price: 1.0
  max_price: 500.0

shock:
  enabled: true
  shock_probability: 0.2
```

---

## 9. Key Class & Method Signatures

### MarketSimulator

```python
class MarketSimulator:
    def __init__(self, config: SimulationConfig, rng: SeededRNG): ...
    def run(self) -> list[NegotiationResult]: ...
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
                 event_logger=None, time_step=0): ...
    def run(self) -> NegotiationResult: ...
    # attributes:
    transcript: list[NegotiationTurn]
    risk_events: list[dict]
    last_offer: Optional[float]
    is_complete: bool
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

### Matcher

```python
class Matcher(ABC):
    @abstractmethod
    def match(self, buyers, sellers, items, rng) -> list[tuple[BuyerState, SellerState, Item]]: ...

class RandomMatcher(Matcher):
    def match(self, buyers, sellers, items, rng) -> list[tuple[BuyerState, SellerState, Item]]: ...
```

### LLM Agent Pipeline

```python
# src/agents/llm_utils.py
def to_action(obj: dict) -> NegotiationAction: ...
def fallback_action(ctx: AgentContext) -> NegotiationAction: ...
def call_llm_and_parse(backend, prompt, ctx) -> NegotiationAction: ...
```

### Metrics

```python
def compute_metrics(results: list[NegotiationResult]) -> dict[str, Any]: ...
def compute_tick_stats(tick: int, results: list[NegotiationResult]) -> MarketTickStats: ...
```

---

## 10. Migration Checklist

### What changed to fix each mismatch

| # | Mismatch | Fix | Files changed |
|---|----------|-----|--------------|
| 1 | Private cross-agent imports (`_to_action`, `_fallback_action`) | Extracted to public `src/agents/llm_utils.py`; agents now import from there; old names kept as aliases | `llm_utils.py` (new), `llm_reactive.py`, `llm_deliberative.py`, `memory_agent.py` |
| 2 | Scattered validation logic (parser + constraints + protocol) | Created `ActionJudge` in `judge.py` consolidating first-round corrections + constraint checks + enforcement. `NegotiationSession` delegates to Judge. | `judge.py` (new), `session.py` (new), `protocol.py` (now wrapper) |
| 3 | No market-level tick loop / stats | Added `MarketTickStats` dataclass, `compute_tick_stats()`, `log_tick_stats()`, `Matcher` interface. Simulator now computes per-tick stats in market mode. | `types.py`, `metrics.py`, `logging.py`, `matcher.py` (new), `simulator.py`, `run.py` |

### Before → After responsibility mapping

| Responsibility | Before | After |
|---------------|--------|-------|
| Negotiation loop | `run_negotiation()` function in `protocol.py` | `NegotiationSession.run()` in `session.py` (`protocol.py` is a thin wrapper) |
| First-round corrections | Inline in `run_negotiation()` | `ActionJudge.correct_first_round()` |
| Constraint validation | `constraints.validate_action()` called in `run_negotiation()` | `ActionJudge.validate()` → `constraints.validate_action()` |
| Auto-correction policy | Inline in `run_negotiation()` | `ActionJudge.enforce()` |
| Surplus calculation | Inline in `run_negotiation()` | `NegotiationSession._settle()` |
| LLM parse-retry pipeline | Duplicated in each LLM agent's `_call_and_parse` | `llm_utils.call_llm_and_parse()` (shared) |
| Buyer-seller matching | `match_pairs()` function | `Matcher.match()` interface + `RandomMatcher` |
| Tick-level stats | Not computed | `compute_tick_stats()` + `log_tick_stats()` in market mode |

### How to run

**Session mode (old behaviour, unchanged):**
```bash
python experiments/run.py --config experiments/configs/baseline.yaml \
    --steps 5 --seed 42
```

**Market mode (new):**
```bash
python experiments/run.py --config experiments/configs/baseline.yaml \
    --mode market --ticks 10 --num_buyers 20 --num_sellers 20 --seed 42
```

---

## 11. TODO / Future Extensions

| Priority | Extension | Notes |
|----------|-----------|-------|
| High | Order book / double auction matching | Implement `AuctionMatcher(Matcher)` |
| High | Personality/style ablations | Add `style` field to agent profiles, inject into prompts |
| Medium | Multi-issue negotiation | Extend `Offer` to carry `{issue: value}` dict |
| Medium | Reputation system | Track deal history per agent ID across ticks |
| Medium | Cross-run memory persistence | Serialise `MemoryStore` to disk between runs |
| Low | Experiment tracking (MLflow/W&B) | Wrap `write_summary` with tracker API |
| Low | Parallel session execution | Thread pool for independent sessions within a tick |
| Low | Config validation | Warn on unknown YAML keys via `_dict_to_config` |
