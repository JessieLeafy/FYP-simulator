# Free-Language Gate-Off Migration Plan

> Generated: 2026-03-12
> Branch: `prompt-redesign`
> Status: PLAN ONLY — no code edits or experiment runs yet

## 1. Current Results Reorganized

### Evidence Inventory

Every output artifact was traced back to its config, git hash, and pipeline. Key disambiguation method: `experiment_summary.json` records `git_hash` and session counts; directory naming distinguishes gate-off runs; the `gate_enabled` default was `True` on `main` (git hashes `bc36a41`, `30f61d4`, `72e280b`, `52e39a3`) and changed to `False` only on the `prompt-redesign` branch. Since no experiment config explicitly sets `gate_enabled`, all runs on `main` used gate ON.

### BUCKET 1 — MAIN RESULTS (gate ON, structured agents, full 3-seed runs)

| Artifact | Experiment | Agent | Gate | Sessions | Seeds | Git Hash | Citable? |
|---|---|---|---|---|---|---|---|
| `outputs/experiments/exp_concession_20260221_234050/` | A: Concession | rule_based, llm_reactive, llm_deliberative | ON | 450 | 42,123,456 | `bc36a41` | **YES** |
| `outputs/experiments/exp_anchoring_20260222_005220/` | B: Anchoring | llm_reactive | ON | 450 | 42,123,456 | `bc36a41` | **YES** |
| `outputs/experiments/exp_deadline_20260222_024017/` | C: Deadline | llm_deliberative | ON | 450 | 42,123,456 | `bc36a41` | **YES** |
| `outputs/experiments/exp_market_dynamics_20260222_043735/` | D: Market Dynamics | llm_reactive | ON | ~450 | 42 | `bc36a41` | **YES** (1 seed) |
| `outputs/experiments/exp_shock_response_20260222_063844/` | E: Shock Response | llm_reactive | ON | ~900 | 42 | `bc36a41` | **YES** (1 seed) |
| `outputs/full_mechanism/exp_mechanism_20260307_183624/` | H: Mechanism | llm_reactive | ON | 520 | 42,123,456 | `72e280b` | **YES** (strongest) |
| `outputs/experiments/exp_supply_demand_20260308_000307/` | I: Supply-Demand | llm_reactive | ON | ~300 | 42,123,456 | `30f61d4` | **YES** |

**Evidence**: All on `main` branch where `config.py` had `gate_enabled: bool = True`. No config overrides it. Git hashes confirmed from `experiment_summary.json`.

### BUCKET 2 — GATE-OFF REAL RESULTS

| Artifact | Experiment | Agent | Gate | Sessions | Seeds | Status | Citable? |
|---|---|---|---|---|---|---|---|
| `outputs/experiments_gate_off/exp_concession_20260310_105833/` | A: Concession | rule_based, llm_reactive, llm_deliberative | **OFF** | 450 | 42,123,456 | Complete | **YES** |
| `outputs/experiments_gate_off/exp_deadline_20260310_151300/` | C: Deadline | llm_deliberative | **OFF** | ~50 | 42 | **Incomplete** (events.jsonl only, no summary) | **NO** |

**Evidence**: Directory name `experiments_gate_off/`. Script `run_gate_off_full_ac.py` line 138: `cfg.negotiation.gate_enabled = False`.

### BUCKET 3 — PILOT RESULTS (seed 42 only, reduced scale)

| Artifact | Experiment | Sessions | Git Hash | Notes |
|---|---|---|---|---|
| `outputs/experiments/exp_concession_20260308_224407/` | A | 30 | `52e39a3` | 3 conds × 1 seed |
| `outputs/experiments/exp_concession_20260308_225403/` | A | 30 | `52e39a3` | duplicate pilot |
| `outputs/experiments/exp_anchoring_20260308_230108/` | B | 30 | `52e39a3` | r=0.6864 (opposite sign vs full run) |
| `outputs/experiments/exp_deadline_20260308_233947/` | C | 30 | `52e39a3` | 100% deal rate all conditions |
| `outputs/experiments/exp_market_dynamics_20260308_235254/` | D | ~100 | `52e39a3` | 20 ticks, lower liquidity |
| `outputs/experiments/exp_shock_response_20260309_005143/` | E | ~200 | `52e39a3` | 40 ticks |
| `outputs/experiments/exp_mechanism_20260309_024408/` | H | 43 | `52e39a3` | 16.3% deal rate |
| `outputs/experiments/exp_supply_demand_20260309_031123/` | I | ~45 | `52e39a3` | very low liquidity |
| `outputs/experiments/pilot_summary_20260309_033707.json` | ALL | 478 total | `52e39a3` | Coordinated pilot batch |

**Critical note**: Pilots on `52e39a3` show dramatically different behavior from full runs on `bc36a41` (anchoring correlation flips sign, mechanism deal rate drops from 57% to 16%). This likely reflects prompt/config changes between commits, not just seed variance.

### BUCKET 4 — GATE ABLATION (partial, supplementary)

| Artifact | Condition | Sessions | Seeds | Status |
|---|---|---|---|---|
| `outputs/experiments/gate_ablation/run_20260308_172108/gate_on/seed_42/` | gate ON | 25 | 42 | Complete |
| `outputs/experiments/gate_ablation/run_20260308_172108/gate_on/seed_123/` | gate ON | 25 | 123 | Complete |
| `outputs/experiments/gate_ablation/run_20260308_172108/gate_on/seed_456/` | gate ON | ? | 456 | **Incomplete** (events.jsonl only) |
| `outputs/experiments/gate_ablation/run_20260308_172108/gate_off/` | gate OFF | ? | ? | Structure unclear |

**Evidence**: `gate_ablation.py` runner. Seed 456 gate-on incomplete (no summary.json).

### BUCKET 5 — STALE / LEGACY / DEVELOPMENT

| Artifact | Category | Citable? |
|---|---|---|
| `outputs/experiments/exp_concession_20260210_*` (5 dirs) | Early dev, high violation rates, 1-6 sessions each | **NO** |
| `outputs/experiments/exp_anchoring_20260308_231457/` | Incomplete (events only) | **NO** |
| `outputs/experiments/exp_mechanism_20260307_145334/` | Early pilot (6 ticks, 88.5% deal rate — anomalous) | **NO** |
| `outputs/experiments/exp_supply_demand_20260307_211344/` | 1-seed pre-pilot | **NO** |
| `outputs/experiments/exp_supply_demand_20260307_211417/` | 2-seed pre-pilot | **NO** |
| `outputs/pilot_mechanism/` | Early mechanism pilots | **NO** |
| `outputs/runs/` (22 dirs) | Development/validation runs | **NO** |
| `outputs/_debug_risk/`, `_exp3cond/`, `_exp_check/` | Debugging artifacts | **NO** |
| `outputs/prompt_test_llama3.2_3b_*.json` | Single LLM test | **NO** |

### Key Finding: No Free-Language Experiment Results Exist

**Zero outputs were produced using `llm_free_language` agent in any experiment pipeline.** The free-language agent has only been tested via standalone scripts (`run_free_language_test.py`, `run_hf_test.py`), not through the experiment runner.

---

## 2. Current Free-Language Agent Readiness

### 2.1 Runtime Path

Traced from code in `llm_free_language.py`, `llm_utils.py`, `parser.py`, `prompts.py`:

```
LLMFreeLanguageAgent.decide(ctx)
  → build_free_language_prompt(ctx, prompt_cfg)     [prompts.py:608-616]
    → build_free_language_buyer_prompt() or          [prompts.py:409-503]
      build_free_language_seller_prompt()             [prompts.py:506-605]
    → includes: role persona, item info, round/deadline context,
      conversation history as "[Round N] ROLE: message",
      negotiation strategy hints, private constraints (cap/cost),
      price tag format (### BUYER_PRICE($X) ###), MAKE_DEAL instruction

  → call_llm_free_language(backend, prompt, ctx)     [llm_utils.py:303-368]
    → backend.generate(prompt)                        [1st attempt]
    → _parse_free_language(raw, ctx)                  [llm_utils.py:261-300]
      → strip <think>...</think> tags                 [regex, line 272]
      → detect_accept_intent(cleaned)                 [parser.py:164-167]
        → check for "ACCEPT_DEAL" or "MAKE_DEAL" (case-insensitive substring)
      → extract_price_from_text(cleaned)              [parser.py:138-161]
        → primary: ### BUYER_PRICE($X) ### or ### SELLER_PRICE($X) ### regex
        → fallback: bare $X regex
        → takes LAST match in both cases
      → Decision tree:
        → has_accept=True → ACCEPT (price=None, full text as message)
        → price found → OFFER (round 0) or COUNTER (later)
        → neither → REJECT

    → IF REJECT (nothing extracted):
      → ONE retry with hint appended                  [llm_utils.py:334-356]
        → hint: "You MUST include exactly one price in format: ### {TAG}($X) ###"
        → re-parse
        → if still REJECT: log error, return REJECT

    → IF OFFER/COUNTER:
      → _check_feasibility(action, ctx)               [llm_utils.py:362-366]
        → buyer: price ≤ min(value, budget)
        → seller: price ≥ cost
        → if infeasible: log warning, pass through (NO retry)

    → attach prompt_sent + raw_llm_output to action

  → ActionJudge.enforce(role, action, buyer, seller, round, ...)  [judge.py:91-136]
    → correct_first_round() if round 0               [COUNTER→OFFER, ACCEPT/REJECT→OFFER]
    → validate_action()                               [constraints.py]
    → if invalid → REJECT + risk_event

  → NegotiationSession records turn, logs event, checks termination
```

### 2.2 Fragilities and Blockers

**BLOCKER-LEVEL issues:**

None. The free-language agent is technically runnable in the experiment pipeline right now.

**HIGH-SEVERITY fragilities:**

| Issue | Details | Impact |
|---|---|---|
| **Accept + price mixed** | "MAKE_DEAL at ### BUYER_PRICE($100) ###" → ACCEPT wins (line 277), price ignored | Semantic info lost; agent may intend to accept at a specific price but price is discarded |
| **Bare dollar fallback** | "Seller wants $150 but I'll offer $95" → extracts $95 (last match). But "Your $120 budget..." → extracts $120 (constraint leakage into price) | Silent wrong price extraction if LLM echoes constraint values |
| **No parse diagnostics** | No per-experiment summary of parse success rate, retry rate, or fallback usage | Cannot assess parsing reliability without manual JSONL inspection |

**MEDIUM-SEVERITY fragilities:**

| Issue | Details | Impact |
|---|---|---|
| **Retry logs overwrite** | On successful retry, `prompt_sent` = retry prompt (not original). On backend error during retry, `prompt_sent` = original. Inconsistent. | Complicates post-hoc analysis of which prompt produced which response |
| **No communication_strategy in free-language prompts** | `prompts.py` lines 409-605: free-language builders don't read `comm_strategy` from PromptConfig | Experiment G cannot run with free-language agent as-is |
| **No tone hints in free-language prompts** | Same gap — `_TONE_HINTS` not injected | Minor, but inconsistent with structured agents |

**LOW-SEVERITY fragilities:**

| Issue | Details |
|---|---|
| **Last-wins for multiple tags** | Multiple `### BUYER_PRICE($X) ###` tags: takes last. No warning logged. |
| **Decimal edge case** | "$100." (trailing dot) not captured by regex `[\d]+(?:\.[\d]+)?` |
| **<think> tag stripping** | Only strips top-level `<think>` blocks; nested tags pass through |

### 2.3 Experiment Compatibility Matrix

All experiment runner functions in `experiments.py` extract data exclusively from `NegotiationResult` fields (`deal_made`, `deal_price`, `rounds_taken`, `buyer_surplus`, `seller_surplus`) and `NegotiationAction.offer_price` from history turns. **None depend on structured JSON output format.**

| Experiment | Data source | Free-lang compatible? | Notes |
|---|---|---|---|
| A: Concession | `turn.action.offer_price` from history | **YES** | Price extracted from tags works identically |
| B: Anchoring | `first_offer` from history + `result.deal_price` | **YES** | Same extraction path |
| C: Deadline | `result.deal_made` + `result.rounds_taken` | **YES** | No format dependency at all |
| D: Market Dynamics | `sim.tick_stats` (aggregated from results) | **YES** | Fully agent-agnostic |
| E: Shock Response | `sim.tick_stats` | **YES** | Same as D |
| H: Mechanism | `sim.tick_stats` + `compute_allocative_efficiency()` | **YES** | All from NegotiationResult fields |
| I: Supply-Demand | `sim.tick_stats` | **YES** | Same as D |

---

## 3. Experiment-by-Experiment Redesign Assessment

### Experiment A: Concession Curves

**Current setup**: 3 agent types × 3 seeds × 50 sessions/condition = 450 sessions. Fixed scenario (buyer $120, seller $80, ZOPA=$40). Max rounds=10.

**With free-language + gate-off**:
- **Hypothesis remains valid**: Do agents concede over rounds? Free-language may show more varied concession patterns since output is less constrained.
- **Expected changes**: Without gate, more timeouts expected. Without structured JSON forcing a price every turn, some turns may produce REJECT (unparseable). Concession curves may have gaps.
- **Max rounds**: 10 is probably sufficient. The gate-off concession experiment already ran at 10 rounds with 33% deal rate (150/450). This is workable.
- **New metrics needed**: Parse success rate, retry rate, timeout rate per agent type.
- **Condition design**: Replace 3 agent types with a single `llm_free_language` condition. Optionally keep `rule_based` as deterministic baseline.

**Recommendation**: **KEEP BUT MODIFY DESIGN**
- Drop `llm_reactive` and `llm_deliberative` conditions (they use structured prompts)
- Keep `rule_based` as baseline + `llm_free_language` as treatment
- Add parse diagnostic metrics
- Scale: 2 conditions × 3 seeds × 50 sessions = 300 sessions
- **Priority: HIGH** — most interpretable micro-level experiment

### Experiment B: Anchoring

**Current setup**: 3 buyer valuations ($100/$120/$150) × 3 seeds × 50 sessions = 450 sessions.

**Fundamental problem**: Anchoring is confounded with ZOPA width ($20/$40/$70). The experiment cannot isolate first-offer anchoring from zone-of-agreement effects. This problem is independent of agent type.

**With free-language + gate-off**:
- Lower deal rates expected, making correlation computation noisier.
- Anchoring correlation already unstable (r = −0.148 on full run, r = +0.687 on pilot — opposite signs).
- Free-language adds additional noise (parsing variance).

**Recommendation**: **KEEP BUT MODIFY DESIGN**
- Fix the ZOPA confound: hold buyer value constant ($120), but instruct the agent to open at different price levels via prompt manipulation (e.g., "start by offering around $X"). This isolates anchoring from ZOPA.
- Alternative: use fixed ZOPA pairs but vary only seller cost to keep ZOPA constant at $40 while shifting the bargaining range.
- Scale: 3 anchor conditions × 3 seeds × 50 sessions = 450 sessions
- **Priority: MEDIUM** — scientifically important but needs redesign

### Experiment C: Deadline Pressure

**Current setup**: 3 max_rounds (4/8/16) × 3 seeds × 50 sessions = 450 sessions.

**With free-language + gate-off**:
- **This experiment benefits most from gate-off.** Gate was masking deadline effects (100% deal rate in all conditions). Without gate, agents must actually decide to accept, and deadline pressure should be observable.
- **Free-language risk**: With 4 rounds and no gate, deal rate may drop very low (agent needs to parse AND decide within 4 turns). Parse failures count as wasted rounds.
- **Max rounds adjustment**: Consider testing 6/12/20 instead of 4/8/16 to give free-language agents enough breathing room for parse failures.

**Recommendation**: **KEEP BUT MODIFY DESIGN**
- Increase round counts slightly: 6/12/20 instead of 4/8/16
- Add deadline-salience as explicit prompt variation (already supported via `include_deadline_salience` config)
- Add new metrics: timeout rate per condition, parse failure rate, last-N-round agreement share
- Scale: 3 conditions × 3 seeds × 50 sessions = 450 sessions
- **Priority: HIGH** — the experiment most improved by removing the gate

### Experiment D: Market Dynamics

**Current setup**: 30 ticks × 15 pairs/tick = 450 sessions, 1 seed, distribution mode.

**With free-language + gate-off**:
- Deal rates will likely drop below the already-low 17-52% range. With parse failures on top, per-tick statistics may be computed from 0-2 deals.
- Price trend analysis requires enough deals per tick to compute meaningful means.

**Recommendation**: **KEEP BUT SCALE UP**
- Increase pairs per tick: 15 → 25-30
- Increase seeds: 1 → 3
- Consider reducing ticks if compute is constrained: 30 → 20
- Add new metrics: per-tick parse failure count, per-tick retry count
- Scale: 20 ticks × 25 pairs × 3 seeds = 1,500 sessions
- **Priority: MEDIUM** — important for macro story but compute-intensive

### Experiment E: Shock Response

**Current setup**: 2 conditions (shock on/off) × 30 ticks × 15 pairs × 1 seed = 900 sessions.

**With free-language + gate-off**:
- Same low-deal-rate concern as D, compounded across 2 conditions.
- Shock effects are subtle — need enough data to distinguish signal from noise.

**Recommendation**: **KEEP BUT SCALE UP**
- Increase pairs per tick: 15 → 25
- Increase seeds: 1 → 3
- Scale: 2 conditions × 20 ticks × 25 pairs × 3 seeds = 3,000 sessions
- **Priority: LOW** — most compute-intensive, weakest expected signal. Run last.

### Experiment H: Mechanism Comparison

**Current setup**: 2 matchers (random/surplus_max) × 3 seeds × 10 ticks × ~10 pairs = 520 sessions.

**With free-language + gate-off**:
- SurplusMax should still outperform Random (it creates positive-ZOPA pairs by design).
- Lower deal rates make efficiency metrics noisier but the directional effect should survive.
- This experiment is fundamentally about matching, not agent type — free-language shouldn't qualitatively change the comparison.

**Recommendation**: **KEEP BUT SCALE UP**
- Increase pairs per tick: 10 → 20
- Scale: 2 conditions × 3 seeds × 10 ticks × 20 pairs = 1,200 sessions
- **Priority: MEDIUM** — the strongest existing experiment, worth replicating

### Experiment I: Supply-Demand Structure

**Current setup**: 3 conditions × 3 seeds × 10 ticks × 10 pairs = 900 sessions.

**With free-language + gate-off**:
- Demand/supply shift effects should still be directionally correct.
- Low deal rates reduce statistical power.

**Recommendation**: **KEEP BUT SCALE UP**
- Increase pairs per tick: 10 → 20
- Scale: 3 conditions × 3 seeds × 10 ticks × 20 pairs = 1,800 sessions
- **Priority: MEDIUM**

### Summary Table

| Exp | Status | Reason | Priority | Est. Sessions |
|---|---|---|---|---|
| **A** | KEEP BUT MODIFY | Drop structured agents, add diagnostics | HIGH | 144 |
| **B** | **HOLD** | ZOPA confound — needs redesign before rerun | — | 0 |
| **C** | KEEP BUT MODIFY | Adjust round counts, biggest gate-off beneficiary | HIGH | 216 |
| **D** | KEEP | 3 seeds, 10 ticks × 10 pairs | MEDIUM | 300 |
| **E** | KEEP | 3 seeds, 10 ticks × 10 pairs | LOW | 600 |
| **H** | KEEP | 3 seeds, 8 ticks × 8 pairs | MEDIUM | 384 |
| **I** | KEEP | 3 seeds, 8 ticks × 8 pairs | MEDIUM | 576 |

**Total estimated**: ~2,220 sessions. At ~32 sec/session (free-language, 10 rounds), approximately **20 hours** of compute.

### New Metrics to Add Across All Experiments

These are needed for free-language scientific defensibility:

| Metric | Purpose | Where to compute |
|---|---|---|
| **Parse success rate** | % of turns where price or accept was extracted on first attempt | Per-experiment aggregate from JSONL |
| **Retry rate** | % of turns that required the retry hint | Per-experiment aggregate from JSONL |
| **Invalid action rate** | % of turns where judge overrode to REJECT | From risk_events count |
| **Timeout rate** | % of sessions ending in timeout vs deal vs explicit reject | From `NegotiationResult.termination_reason` |
| **Acceptance source** | LLM-accept vs timeout vs judge-reject breakdown | From JSONL `llm_action` vs `effective_action` |
| **Mean response length** | Tokens/characters in `raw_llm_output` | From JSONL `raw_llm_output` |

---

## 4. Required New Features / Instrumentation Before Reruns

### ESSENTIAL (must have before any rerun)

#### 4.1 Parse Diagnostics Reporter
**Problem**: No way to assess free-language parsing reliability without manually reading JSONL logs.
**Solution**: Add a post-run function that reads `events.jsonl` and computes: parse success rate, retry rate, fallback-to-bare-dollar rate, REJECT-from-parse-failure rate.
**Files**: New function in `experiments.py` or `src/evaluation/reports.py`.
**Validity impact**: Without this, we cannot claim the free-language pipeline is reliable.

#### 4.2 Accept-Detection Hardening
**Problem**: `detect_accept_intent()` at `parser.py:164-167` uses substring matching: `any(kw in upper for kw in ("ACCEPT_DEAL", "MAKE_DEAL"))`. An agent saying "I won't MAKE_DEAL at that price" would falsely trigger accept.
**Solution**: Use word-boundary regex: `r'\bMAKE_DEAL\b'` and `r'\bACCEPT_DEAL\b'`. Also consider requiring MAKE_DEAL to NOT be preceded by negation words.
**Files**: `src/negotiation/parser.py` line 164-167.
**Validity impact**: Without this, some acceptances may be false positives.

#### 4.3 Accept+Price Conflict Resolution
**Problem**: If agent writes "MAKE_DEAL at ### BUYER_PRICE($100) ###", the current parser returns ACCEPT with `price=None`, discarding the $100. The semantics of MAKE_DEAL (per the prompt at `prompts.py:492-499`) is "accept opponent's last price". But the agent may be trying to accept at a specific price.
**Solution**: If MAKE_DEAL is detected AND a price tag is present, log this as a conflict. If the extracted price equals `last_offer`, treat as clean accept. If different, decide on a policy (accept at `last_offer`? or treat as counter?). At minimum, log the conflict.
**Files**: `src/agents/llm_utils.py` `_parse_free_language()` lines 277-283.
**Validity impact**: Without this, we silently lose semantic information in some % of acceptances.

#### 4.4 Explicit gate_enabled in All Experiment Configs
**Problem**: No experiment config sets `gate_enabled`. The default differs between branches (`True` on main, `False` on prompt-redesign). This is a silent behavior change.
**Solution**: Add `gate_enabled: false` to every experiment YAML's `negotiation:` section. Makes behavior explicit regardless of branch.
**Files**: All 7 configs in `experiments/configs/`.
**Validity impact**: Prevents silent experiment invalidation when switching branches.

### NICE-TO-HAVE (improve quality but not blockers)

#### 4.5 Communication Strategy in Free-Language Prompts
**Problem**: `build_free_language_buyer_prompt()` and `build_free_language_seller_prompt()` at `prompts.py:409-605` do not read `communication_strategy` or `message_tone` from PromptConfig. Only structured prompt builders do.
**Solution**: Add comm_strategy/tone injection to free-language builders (same pattern as reactive builder lines 266-269).
**Files**: `src/llm/prompts.py` lines 409-605.
**Validity impact**: Required only if running Experiment G with free-language.

#### 4.6 Experiment-Level Summary of Acceptance Sources
**Problem**: The gate ablation script computes acceptance-source breakdowns, but the main experiment runner doesn't.
**Solution**: Add a `compute_acceptance_sources(events_jsonl_path)` function that reads JSONL and classifies each acceptance as: llm_accept, gate_pre_llm, gate_post_override, parse_fallback.
**Files**: New function in `src/evaluation/reports.py` or `experiments.py`.
**Validity impact**: Useful for Results/Discussion, not a blocker.

#### 4.7 Response Length Tracking
**Problem**: No metric for how verbose free-language agents are.
**Solution**: Compute mean/median character count of `raw_llm_output` per experiment condition.
**Files**: Post-processing in experiment summary.
**Validity impact**: Nice for characterizing agent behavior, not essential.

### MUST DISABLE/VERIFY

| Item | Current state | Required state | File |
|---|---|---|---|
| Pre-LLM gate | `gate_enabled: False` on prompt-redesign branch default | Explicitly `false` in all configs | `src/core/config.py:52`, all YAML configs |
| Post-LLM override | Gated by same flag (`session.py:207-220`) | Disabled when `gate_enabled=false` | Already correct |
| Structured-only assumptions | None found in experiment pipeline | N/A | Verified clean |
| Action coercion | Judge corrects round-0 COUNTER→OFFER, invalid→REJECT | Same for free-language — appropriate | `src/negotiation/judge.py` |

---

## 5. Feasibility of Reviving Experiments F and G

### Experiment F: Reputation & Memory

**Intended hypothesis**: Does accumulated experience (memory of past opponent interactions) affect LLM negotiation strategy in repeated interactions?

**Infrastructure status**:

| Component | Status | Location |
|---|---|---|
| `MemoryStore` class | Implemented, tested | `src/agents/memory_agent.py` |
| `ReputationStore` class | Implemented, tested (6 tests) | `src/agents/memory_agent.py` |
| `ReputationAgent` class | Implemented | `src/agents/memory_agent.py` lines 172-257 |
| `RoundRobinMatcher` | Implemented, tested (2 tests) | `src/market/matcher.py` lines 131-184 |
| `build_reputation_context()` | Implemented | `src/llm/prompts.py` lines 640-663 |
| `run_reputation()` runner | Implemented in expF only | `Simulator-expF/experiments/experiments.py` lines 466-617 |
| `stable_ids` parameter | Implemented in expF only | `Simulator-expF/src/market/matching.py` |
| Experiment config | In expF only | Not in main |
| Sample outputs | Exist in expF | 9 sessions, 1 seed |

**Critical blocker**: `stable_ids` is not in main. Without it, `generate_buyers()`/`generate_sellers()` produce tick-stamped IDs (`buyer_t0_000`, `buyer_t1_000`), breaking RoundRobinMatcher's pairing persistence. Must be ported from expF commit `06ee87d`.

**Can it work with free-language?** YES, with caveats:
- Reputation/memory context is injected as prose into the prompt — works for any prompt style.
- But `ReputationAgent` currently extends the deliberative prompt builder, not the free-language builder. Would need a new `ReputationFreeLanguageAgent` or a refactor to make the reputation context injection prompt-agnostic.
- `record_outcome()` uses `NegotiationResult` fields (`deal_made`, `deal_price`, `rounds`) — no format dependency.

**Scientific value**: HIGH. Reputation effects are genuinely interesting for the thesis and would strengthen the "multi-level" story.

**Estimated effort**: 2-4 hours (port stable_ids, port runner, adapt for free-language, smoke test).

**Recommendation**: **REVIVE — scientifically worthwhile and mostly implemented.**

### Experiment G: Communication Strategy

**Intended hypothesis**: Does explicit communication strategy prompting (assertive, collaborative, strategic) affect concession patterns and deal outcomes?

**Infrastructure status**:

| Component | Status | Location |
|---|---|---|
| `_COMMUNICATION_STRATEGIES` dict | Implemented (4 strategies) | `src/llm/prompts.py:156-177` |
| PromptConfig `communication_strategy` field | Implemented | `src/core/config.py:108` |
| Injection into reactive prompt | Implemented | `src/llm/prompts.py:266-269` |
| Injection into deliberative prompt | Implemented | `src/llm/prompts.py:371-374` |
| **Injection into free-language prompt** | **NOT IMPLEMENTED** | Gap in `src/llm/prompts.py:409-605` |
| `run_communication()` runner | **NOT IMPLEMENTED** | No function exists anywhere |
| Experiment config | **NOT IMPLEMENTED** | No YAML exists |
| Test coverage | Implemented (5 tests) | `tests/test_shared_infrastructure.py` lines 322-354 |

**Can it work with free-language?** NOT YET — requires adding `communication_strategy` injection to free-language prompt builders.

**Scientific value**: MODERATE. Effect may be subtle and hard to detect with a 3B model. Results may be null.

**Estimated effort**: 4-6 hours (add to free-lang prompts, implement runner, design conditions, smoke test).

**Recommendation**: **REVIVE ONLY IF TIME PERMITS — implement as a pilot first.** If the 3B model shows no sensitivity to strategy hints, don't include in thesis.

---

## 6. Concrete Next-Step Plan

### Phase A: Repo Cleanup & Instrumentation (before any runs)

| Step | Task | Files | Est. Time |
|---|---|---|---|
| A1 | Add `gate_enabled: false` explicitly to all 7 experiment configs | `experiments/configs/exp_*.yaml` | 15 min |
| A2 | Harden accept detection with word-boundary regex | `src/negotiation/parser.py:164-167` | 15 min |
| A3 | Handle accept+price conflict in `_parse_free_language()` | `src/agents/llm_utils.py:277-283` | 30 min |
| A4 | Add parse diagnostics function (success/retry/reject rates from JSONL) | `src/evaluation/reports.py` or new file | 1 hour |
| A5 | Add `agent_type: llm_free_language` support to experiment condition overrides | `experiments/experiments.py` condition dicts | 30 min |
| A6 | Port `stable_ids` from expF to main (for Experiment F) | `src/market/matching.py`, `src/market/simulator.py` | 30 min |
| A7 | Add `communication_strategy` to free-language prompt builders (for Exp G) | `src/llm/prompts.py:409-605` | 30 min |
| A8 | Run existing test suite to verify no regressions | `pytest` | 5 min |

**Total Phase A**: ~3.5 hours

### Phase B: Smoke Tests (verify pipeline end-to-end)

| Step | Task | Est. Time |
|---|---|---|
| B1 | Run 1 session with `llm_free_language` + gate-off via CLI | 5 min |
| B2 | Inspect events.jsonl: verify `prompt_sent`, `raw_llm_output`, parsed action logged | 10 min |
| B3 | Run 1 concession experiment with 1 seed, 2 steps, 2 pairs (minimal) | 5 min |
| B4 | Verify `concession_curves.csv` has `offer_price` data from free-language parsing | 5 min |
| B5 | Run 1 market-mode experiment (3 ticks, 5 pairs) to verify tick_stats | 5 min |
| B6 | Run parse diagnostics on smoke test output | 5 min |

**Total Phase B**: ~35 min

### Phase C: Pilot Reruns (1 seed, minimal scale)

> **Status**: REDESIGNED 2026-03-12. Uses `--pilot` flag added to `run_free_language_all.py`.
> The flag forces seed=42, and reduces scale to 2 steps × 3 pairs (session-mode) or
> 3 ticks × 5 pairs (market-mode). This is the smallest pilot that still exercises
> every experiment, every condition arm, both agent types, and both simulation modes.

**Command**: `python experiments/run_free_language_all.py --pilot`

| Step | Experiment | Mode | Scale | Est. Sessions |
|---|---|---|---|---|
| C1 | A: Concession (rule_based + free_language) | session | 2 conds × 1 seed × 2 steps × 3 pairs | 12 |
| C2 | C: Deadline (6/12/20 rounds) | session | 3 conds × 1 seed × 2 steps × 3 pairs | 18 |
| C3 | B: Anchoring (low/mid/high) | session | 3 conds × 1 seed × 2 steps × 3 pairs | 18 |
| C4 | H: Mechanism (random + surplus_max) | market | 2 conds × 1 seed × 3 ticks × 5 pairs | 30 |
| C5 | I: Supply-Demand (baseline + 2 shifts) | market | 3 conds × 1 seed × 3 ticks × 5 pairs | 45 |
| C6 | D: Market Dynamics | market | 1 cond × 1 seed × 3 ticks × 5 pairs | 15 |
| C7 | E: Shock Response (no_shock + with_shock) | market | 2 conds × 1 seed × 3 ticks × 5 pairs | 30 |

**Total Phase C**: ~168 sessions, ~15-40 min (at ~5-15 sec/session with HuggingFace)

**What the pilot catches:**
- Crashes / parsing errors in free-language pipeline
- HuggingFace backend loading and GPU memory issues
- Pathological deal-rate (0% or 100%) revealing prompt/protocol failures
- Broken metric computation (tick stats, concession CSV, anchoring CSV)
- Parse diagnostics (auto-generated per experiment)
- Config override bugs (agent_type, max_rounds, matcher, shock, buyer_value)

**Go/no-go criteria after pilot:**
- All 7 experiments complete without crash → GO
- Parse success rate > 70% for free-language conditions → GO
- Deal rate between 5% and 95% for most conditions → GO
- If any experiment crashes or deal rate is 0%: investigate before full run
- If parse success < 50%: adjust prompt or add retry logic before full run

**Backend reuse verification:**
The `--pilot` flag reuses the same `shared_backend` instance across all experiments
(threaded via `run_dir, shared_backend = runner(..., backend=shared_backend)`).
The HuggingFace model is loaded exactly once on the first `llm_free_language` condition
(after rule_based in Exp A completes without needing the LLM).

### Phase D: Full Reruns (3 seeds, production scale)

> **Revised 2026-03-12.** Downsized to fit within ~20 hours of compute at ~32s/session.
> Experiment B (Anchoring) is **HELD** pending ZOPA confound redesign.
> Experiment F (Reputation) deferred — requires `stable_ids` port and separate planning.

**Sizing principle**: enough sessions per condition per seed for credible reporting,
without overdoing compute. Session-mode experiments need ~24 sessions/cond/seed;
market-mode experiments need ~64–100 sessions/cond/seed for stable per-tick aggregates.

| Step | Experiment | Scale | Sessions | Hours | Priority |
|---|---|---|---|---|---|
| D1 | A: Concession | 2 conds × 3 seeds × 3 steps × 8 pairs | 144 | 1.3 | HIGH |
| D2 | C: Deadline | 3 conds × 3 seeds × 3 steps × 8 pairs | 216 | 1.9 | HIGH |
| D3 | H: Mechanism | 2 conds × 3 seeds × 8 ticks × 8 pairs | 384 | 3.4 | MEDIUM |
| D4 | I: Supply-Demand | 3 conds × 3 seeds × 8 ticks × 8 pairs | 576 | 5.1 | MEDIUM |
| D5 | D: Market Dynamics | 1 cond × 3 seeds × 10 ticks × 10 pairs | 300 | 2.7 | MEDIUM |
| D6 | E: Shock Response | 2 conds × 3 seeds × 10 ticks × 10 pairs | 600 | 5.3 | LOW |

**Total Phase D**: ~2,220 sessions, ~19.7 hours of compute

**Per-condition/seed credibility**:
- A, C: 24 sessions (3 steps × 8 pairs) — sufficient for concession curves and deal-rate comparison
- H, I: 64 sessions (8 ticks × 8 pairs) — solid for efficiency/price comparison across ticks
- D: 100 sessions/seed (10 × 10) — sufficient for price trend analysis
- E: 100 sessions/cond/seed (10 × 10) — enough for shock vs no-shock comparison

**Held experiments**:
- **B: Anchoring** — ZOPA confound (buyer value varies across conditions, confounding anchoring with zone-of-agreement width). Needs redesign before rerun.
- **F: Reputation** — requires `stable_ids` port from expF branch, plus `ReputationFreeLanguageAgent`. Separate planning needed.

### Phase D-Server: Full Run Deployment on Server

> **Added 2026-03-12.** Step-by-step plan for running Phase D on a GPU server.

**Prerequisites**:
- Server with GPU (CUDA) and ≥16 GB VRAM for Qwen2.5-14B-Instruct (4-bit quantized)
- Python 3.10+, PyTorch with CUDA, transformers, bitsandbytes
- Pilot (Phase C) completed locally with go/no-go criteria met

**Setup steps**:

```bash
# 1. Clone and checkout
git clone https://github.com/JessieLeafy/FYP-simulator.git
cd FYP-simulator
git checkout prompt-redesign

# 2. Create venv and install deps
python -m venv .venv
source .venv/bin/activate
pip install pyyaml transformers torch accelerate bitsandbytes tqdm

# 3. Verify GPU is available
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# 4. Quick smoke test (1 session, ~30s)
python experiments/run_smoke_test.py --backend huggingface

# 5. Full run in tmux/screen (detached, survives SSH disconnect)
tmux new -s fyp-run
python experiments/run_free_language_all.py \
  --backend huggingface \
  --quantize 4bit \
  2>&1 | tee outputs/full_run_$(date +%Y%m%d_%H%M%S).log

# Detach: Ctrl-B then D
# Reattach later: tmux attach -t fyp-run
```

**Monitoring**:
- tqdm progress bar shows sessions completed, deal rate, and ETA
- Log file captures everything for post-mortem
- If SSH drops, reattach with `tmux attach -t fyp-run`

**Expected timeline** (~32s/session):

| Experiment | Sessions | Est. Time | Cumulative |
|---|---|---|---|
| A: Concession | 144 | 1.3h | 1.3h |
| C: Deadline | 216 | 1.9h | 3.2h |
| H: Mechanism | 384 | 3.4h | 6.6h |
| I: Supply-Demand | 576 | 5.1h | 11.7h |
| D: Market Dynamics | 300 | 2.7h | 14.4h |
| E: Shock Response | 600 | 5.3h | 19.7h |

**Recovery**: Each experiment writes its own output directory and summary.
If the run crashes mid-way, re-run with `--only` for remaining experiments:
```bash
# Example: resume from experiment D onward
python experiments/run_free_language_all.py \
  --only D,E \
  --backend huggingface \
  --quantize 4bit
```

**Post-run**:
```bash
# Verify all outputs exist
ls outputs/experiments_free_language/

# Parse diagnostics are auto-generated per experiment
cat outputs/experiments_free_language/*/parse_diagnostics.json

# Copy results back to local machine
# (from local): scp -r server:FYP-simulator/outputs/experiments_free_language/ outputs/
```

### Phase E: Paper/Report Updates

| Step | Task |
|---|---|
| E1 | Update `method.tex`: describe free-language agent pipeline, prompt design, parsing |
| E2 | Update `experiments.tex`: note gate-off, free-language as new experimental condition |
| E3 | Update `results.tex`: report new results with parse diagnostics alongside settlement metrics |
| E4 | Update `discussion.tex`: compare gate-on/structured vs gate-off/free-language findings |
| E5 | Add parse reliability analysis as a methodological result |
| E6 | Update `abstract.tex` after all sections stable |

---

## Final Verdict

### Is free-language + gate-off a realistic new main direction?

**Yes, with qualifications.**

**Why yes:**
1. The experiment pipeline is fully agent-agnostic. Switching to `llm_free_language` requires zero changes to experiment runner code, metrics computation, or CSV output schemas. Verified by tracing every `run_*()` function in `experiments.py`.
2. The free-language agent is implemented, tested, and has a clean runtime path with retry logic and full prompt/output logging.
3. Gate-off is already the default on the current branch. Adding it explicitly to configs is a 15-minute task.
4. The combination directly addresses the two biggest criticisms from the audit: (a) gate contamination masking agent behavior, and (b) structured JSON constraining agent responses.

**Why qualified:**
1. Free-language parsing is inherently noisier than structured JSON. Some % of turns will produce REJECT (unparseable), and this noise must be measured, reported, and defended.
2. Deal rates will drop. Market-mode experiments (D, E, H, I) already had 13-27% deal rates with gate ON. With gate OFF + parse failures, expect 5-20%. This requires scaling up session counts.
3. The 3B model (`llama3.2:3b`) may struggle more with free-language output than structured JSON. Parse failure rates from pilot runs will determine if the model is viable or needs upgrading.
4. Experiment B (anchoring) has a fundamental design flaw (ZOPA confound) independent of agent type. Needs redesign regardless.

**Bottom line**: This is a strong new direction that makes the thesis more scientifically honest and more interesting. The free-language + gate-off setup lets the LLM actually negotiate rather than being overridden by mechanical enforcement. The risk is lower deal rates and parse noise, but these are measurable and reportable — and arguably more interesting than perfect-deal-rate results driven by a deterministic gate.

---

## Top 10 Most Important Actions (Priority Order)

1. **Add `gate_enabled: false` to all experiment configs** — prevents silent behavior change, 15 minutes, zero risk.

2. **Harden accept detection** (`\bMAKE_DEAL\b` word boundary) — prevents false-positive acceptances, 15 minutes, essential for validity.

3. **Build parse diagnostics reporter** — without this, you cannot defend free-language results. Must report parse success/retry/reject rates per experiment.

4. **Handle accept+price conflict** — decide and document policy for "MAKE_DEAL at ### PRICE($100) ###". Log the conflict at minimum.

5. **Run a smoke test** — 1 free-language session end-to-end, inspect JSONL, confirm prompt/output logging works before committing to pilots.

6. **Run pilot reruns for A and C** — these are the highest-priority, most interpretable experiments. Pilots reveal whether the 3B model produces parseable free-language output at acceptable rates.

7. **Evaluate pilot parse failure rates** — if >30% of turns are unparseable after retry, consider: (a) adjusting prompt, (b) adding second retry, or (c) upgrading model size.

8. **Port stable_ids from expF** — needed for Experiment F (reputation). Small change, big payoff.

9. **Add communication_strategy injection to free-language prompts** — needed for Experiment G. Simple code change but only worth doing after pilots show free-language viability.

10. **Redesign Experiment B anchoring** — fix the ZOPA confound. This is a design issue, not a code issue, and should be decided before full reruns.
