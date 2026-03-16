# Experiment Report: LLM-Powered Multi-Agent Negotiation Simulation

**Project:** FYP — Multi-Agent Negotiation & Trading Simulation
**Model:** `Qwen/Qwen2.5-14B-Instruct` via HuggingFace Transformers (GPU inference)
**Framework:** Custom Python simulation (6-layer architecture)
**Git hash:** `59407e6` (Experiments 1–6), `706cd06` (Experiment 4 extension)
**Total sessions:** ~2,770 across 6 experiments + 1 extension (all with gate disabled)
**Final run dates:** 2026-03-13 (Experiments 1–6), 2026-03-14 (Experiment 4 extension)
**Seeds:** 42, 123, 456 (3 replications per experiment)

---

## Abstract

This report presents empirical results from a multi-agent bilateral negotiation simulator in which LLM agents engage in alternating-offer bargaining over a single commodity. Six experiments and one extension study were conducted using free-language LLM agents with the feasibility gate disabled, ensuring all negotiation decisions flow through the LLM.

Experiments evaluate concession dynamics (Experiment 1), deadline pressure (Experiment 2), market price discovery (Experiment 3), supply shock response (Experiment 4), market mechanism design (Experiment 5), and supply–demand structure effects (Experiment 6). The anchor environment extension (Experiment 4-ext) ablates the reference price anchor to investigate whether fixed prompt-level anchors suppress price adjustment in response to shocks.

---

## 1. Introduction

### 1.1 Research Questions

1. Do LLM free-language agents exhibit concession dynamics consistent with alternating-offer bargaining theory? (Exp 1)
2. Does the negotiation time horizon affect agreement rates, closing timing, and concession behaviour? (Exp 2)
3. Does a market of LLM bilateral negotiators exhibit stable price dynamics? (Exp 3)
4. Do exogenous supply/demand shocks cause measurable shifts in market price and liquidity? (Exp 4)
5. Does the buyer–seller matching mechanism affect deal rates, allocative efficiency, and surplus distribution? (Exp 5)
6. Do transaction prices and trade volume respond in the expected direction when demand or supply conditions shift structurally? (Exp 6)
7. Does the fixed prompt-level reference price anchor suppress price adjustment in response to shocks? (Exp 4 extension)

### 1.2 Agent Types

| Agent | Description |
|---|---|
| `rule_based` | Linear concession from opening to reservation price. Deterministic baseline. Used only in Experiment 1. |
| `llm_free_language` | Natural-language LLM agent. Produces prices via `### PRICE($X) ###` tags and accepts via `ACCEPT_DEAL`. Used in all experiments. |

### 1.3 Feasibility Gate

The deterministic feasibility gate (`gate_enabled: false` in all experiment configs) is **disabled** for all final experiments. All negotiation decisions are made by the LLM agent, with no automatic acceptance of feasible offers. The gate remains in the codebase for ablation purposes.

### 1.4 LLM Pipeline Quality

All experiments use the free-language parsing pipeline (`call_llm_free_language` in `src/agents/llm_utils.py`). Key reliability metrics across all experiments:

| Metric | Value |
|---|---|
| Parse success rate | **100%** (0 parse failures across ~2,770 sessions) |
| Override rate | **0.0%** (no judge overrides) |
| Mean response length | ~282 characters |
| Timeout rate | 2.8% (Exp 1) to 10.2% (Exp 4), varies by experiment complexity |

---

## 2. Experimental Setup

### 2.1 Common Parameters

| Parameter | Value |
|---|---|
| LLM model | `Qwen/Qwen2.5-14B-Instruct` |
| LLM backend | HuggingFace Transformers |
| Temperature | 0.2 |
| Max tokens | 512 |
| Max rounds per session | 10 (default, varied in Exp 2) |
| Seeds | 42, 123, 456 (3 replications) |
| Gate enabled | **false** (all experiments) |

### 2.2 Experiment Scripts and Provenance

| Script | Experiments | Run date |
|---|---|---|
| `experiments/run_free_language_all.py` | Experiments 1–6 | 2026-03-13 |
| `experiments/run_shock_anchor_ablation.py` | Experiment 4 extension | 2026-03-14 |

### 2.3 Experiment Summary

| # | Name | Config | Mode | Conditions | Sessions | Results directory | Run ID |
|---|---|---|---|---|---|---|---|
| 1 | Concession dynamics | `exp_concession.yaml` | session, fixed | rule_based, llm_free_language | 144 | `results/exp1_concession/` | `20260313_013102` |
| 2 | Deadline pressure | `exp_deadline.yaml` | session, fixed | max_rounds: 6, 12, 20 | 216 | `results/exp2_deadline/` | `20260313_015631` |
| 3 | Market dynamics | `exp_market_dynamics.yaml` | market, distribution | 1 condition | 300 | `results/exp3_market_dynamics/` | `20260313_094631` |
| 4 | Supply shock | `exp_shock_response.yaml` | market, distribution | no_shock, with_shock | 600 | `results/exp4_supply_shock/` | `20260313_115743` |
| 4-ext | Anchor environment | `exp_shock_response.yaml` | market, distribution | 2 anchor modes × 2 shock conditions | ~1,200 | `results/exp4_anchor_environment_extension/` | `20260314_122340` |
| 5 | Mechanism comparison | `exp_mechanism.yaml` | market, distribution | random, surplus_max | 335 | `results/exp5_mechanism/` | `20260313_031133` |
| 6 | Supply-demand shift | `exp_supply_demand.yaml` | market, distribution | baseline, demand_shock, supply_shock | 576 | `results/exp6_supply_demand/` | `20260313_054409` |

---

## 3. Experiment 1 — Concession Dynamics

### 3.1 Design

**Research question:** Do LLM free-language agents produce different concession trajectories than rule-based agents?

- **Conditions:** `rule_based` (deterministic baseline), `llm_free_language`
- **Sessions:** 72 per condition × 3 seeds = 144 total
- **Fixed parameters:** buyer_value=$120, seller_cost=$80, reference_price=$100
- **Measurement:** Offer price at each round, per role

### 3.2 Results

**Table 1. Concession dynamics — opening offers and multi-round trajectories**

| Condition | Round 0 (buyer) | Round 1 (seller) | Round 2 (buyer) | Deal rate | Avg rounds |
|---|---|---|---|---|---|
| `rule_based` | $60.00 | $101.33 | $73.33 | 97.2% | ~5–6 |
| `llm_free_language` | $71.88 | $89.93 | $85.18 | 97.2% | ~4–5 |

With the gate disabled, both agent types negotiate over multiple rounds (up to 10), producing richer concession trajectory data than in earlier gate-enabled experiments.

### 3.3 Interpretation

- **LLM agents open less aggressively** than the rule-based agent ($71.88 vs $60.00 for buyer openings), suggesting the LLM does not compute the theoretically optimal anchor as precisely as an algorithmic agent.
- **Seller counter-offers differ significantly:** the LLM seller counters at $89.93 vs the rule-based seller at $101.33, indicating the LLM agent starts closer to the zone midpoint rather than near its reservation price.
- Both conditions achieve similar overall deal rates (97.2%), with 4 timeouts each across 72 sessions.

---

## 4. Experiment 2 — Deadline Pressure

### 4.1 Design

**Research question:** Does the negotiation time horizon affect agreement rates and closing timing?

- **Conditions:** `max_rounds` ∈ {6, 12, 20} with `llm_free_language` agents
- **Sessions:** 72 per condition × 3 seeds = 216 total
- **Fixed parameters:** buyer_value=$120, seller_cost=$80, reference_price=$100

### 4.2 Results

**Table 2. Deadline experiment outcomes by time horizon**

| Max rounds | Sessions | Deals | Deal rate | Avg closing round | Last-2-round share |
|---|---|---|---|---|---|
| 6 | 72 | 68 | 94.4% | 5.21 | 82.4% |
| 12 | 72 | 70 | 97.2% | 6.70 | 15.7% |
| 20 | 72 | 70 | 97.2% | 7.30 | 11.4% |

### 4.3 Interpretation

- **Shorter horizons reduce deal rates modestly:** the 6-round condition achieves 94.4% vs 97.2% for longer horizons, indicating some negotiations need more than 6 rounds to converge.
- **Last-2-round share under max_rounds=6 is 82.4%**, suggesting that when the deadline is tight, most agreements cluster near the deadline — directionally consistent with deadline pressure effects.
- **Average closing round increases with horizon** (5.21 → 6.70 → 7.30), suggesting agents use available rounds but do not expand negotiations proportionally to the horizon length.
- The results are more nuanced than in earlier gate-enabled experiments where all sessions closed at round 2–3 regardless of horizon.

---

## 5. Experiment 3 — Market Dynamics

### 5.1 Design

**Research question:** Does a market of LLM bilateral negotiators exhibit stable price dynamics and meaningful liquidity?

- **Mode:** Market simulation, 10 ticks × 10 pairs/tick × 3 seeds = 300 sessions
- **Agent type:** `llm_free_language`
- **Scenario:** Distribution mode (heterogeneous buyers/sellers, coherent sampling enabled)

### 5.2 Results

**Table 3. Market dynamics aggregate statistics (30 tick-seed observations)**

| Metric | Value |
|---|---|
| Mean transaction price | **$90.33** |
| Price range | $83.38 – $97.29 |
| Price trend slope | **−$0.13 / tick** |
| Average liquidity | **82.3%** |
| Total ticks (across 3 seeds) | 30 |

### 5.3 Interpretation

- **The price trend slope of −$0.13/tick is economically negligible**, suggesting the market reaches a stable price level rather than drifting systematically.
- **Liquidity at 82.3%** indicates that LLM free-language agents with coherent sampling reach deals in most matched pairs.
- Price dispersion within ticks is present, consistent with bilateral bargaining theory where each pair negotiates independently.

---

## 6. Experiment 4 — Supply Shock

### 6.1 Design

**Research question:** Do exogenous supply/demand shocks cause measurable shifts in market price and liquidity?

- **Conditions:** `no_shock` (baseline) vs `with_shock` (demand/supply multipliers ∈ [0.7, 1.3], shock probability 30%)
- **Mode:** Market simulation, 10 ticks × 10 pairs/tick × 3 seeds × 2 conditions = 600 sessions
- **Agent type:** `llm_free_language`
- **Config note:** `coherent_sampling: false` — shocks multiply buyer values and seller costs before matching; coherent sampling would overwrite those shocked values.

### 6.2 Results

**Table 4. Shock response outcomes — no_shock vs with_shock (30 tick-seed observations each)**

| Metric | `no_shock` | `with_shock` | Δ |
|---|---|---|---|
| Mean price | $109.25 | $109.55 | +$0.30 |
| Mean liquidity | 68.7% | 72.3% | +3.6pp |

### 6.3 Interpretation

- **The price difference between shock and no-shock conditions is minimal** (+$0.30), suggesting that with the default `fixed` anchor mode, the reference price in the prompt anchors agent behaviour and suppresses price adjustment in response to shocks.
- **Liquidity is slightly higher under shocks**, possibly because positive shocks widen the ZOPA for some pairs more than negative shocks narrow it.
- This weak shock response motivates the anchor ablation study (Experiment 4 extension).

---

## 7. Experiment 4 Extension — Anchor Environment

### 7.1 Design

**Research question:** Does the fixed prompt-level reference price anchor suppress price adjustment in response to shocks?

This is an **extension** of Experiment 4, not a standalone experiment. It uses the same base configuration (`exp_shock_response.yaml`) but varies the anchor mode.

**Important methodological note:** The `fixed` anchor condition from Experiment 4 serves as the baseline. The extension runs two additional anchor modes (`updated` and `no_anchor`) rather than re-running the `fixed` condition.

- **Anchor modes tested:**
  - `updated` — reference price updated to mean deal price after each tick
  - `no_anchor` — reference price removed from prompts entirely
- **Shock conditions:** no_shock, with_shock (same as Experiment 4)
- **Seeds:** 42, 123, 456 (3 replications)
- **Script:** `experiments/run_shock_anchor_ablation.py`
- **Total tick records:** 120 (2 anchor modes × 2 shock conditions × 10 ticks × 3 seeds)

### 7.2 Results

**Table 5. Anchor ablation condition summaries**

| Anchor mode | Shock condition | Mean price | Price std | Avg liquidity |
|---|---|---|---|---|
| `updated` | no_shock | $78.84 | $14.16 | 71.3% |
| `updated` | with_shock | $82.99 | $14.69 | 71.7% |
| `no_anchor` | no_shock | $99.21 | $7.73 | 86.7% |
| `no_anchor` | with_shock | $99.01 | $8.94 | 92.0% |

**Comparison with Experiment 4 (fixed anchor):**

| Anchor mode | Shock Δ (mean price) | Shock Δ (liquidity) |
|---|---|---|
| `fixed` (Exp 4) | +$0.30 | +3.6pp |
| `updated` | +$4.15 | +0.4pp |
| `no_anchor` | −$0.20 | +5.3pp |

### 7.3 Interpretation

- **The `updated` anchor mode produces the largest price response to shocks** (+$4.15), suggesting that dynamic anchors allow prices to adjust when market conditions change.
- **The `no_anchor` condition produces the highest liquidity** (86.7%–92.0%) but minimal price response to shocks (−$0.20), suggesting that without a reference price, agents converge on similar prices regardless of shock conditions.
- **Lower price dispersion under `no_anchor`** (σ = $7.73–$8.94 vs $14.16–$14.69 under `updated`) suggests the reference price introduces price variability.
- The results directionally support the hypothesis that the fixed prompt-level anchor suppresses price adjustment, but the pattern is complex and warrants cautious interpretation.

---

## 8. Experiment 5 — Mechanism Comparison

### 8.1 Design

**Research question:** Does the buyer–seller matching algorithm affect market-level deal rates, allocative efficiency, and surplus distribution?

- **Conditions:** `random` (baseline) vs `surplus_max` (greedy maximum-ZOPA pairing)
- **Mode:** Market simulation, 8 ticks × 8 pairs/tick × 3 seeds × 2 conditions
- **Agent type:** `llm_free_language`
- **Scenario:** Distribution mode (coherent sampling enabled)

### 8.2 Results

**Table 6. Mechanism comparison: random vs surplus_max**

| Metric | `random` | `surplus_max` | Δ |
|---|---|---|---|
| Total sessions | 192 | 143 | −49 (ZOPA+ pairs only) |
| Deals made | 163 | 118 | −45 |
| Deal rate | **84.9%** | **82.5%** | −2.4pp |
| Mean price | $71.00 | $72.36 | +$1.36 |
| Allocative efficiency | **0.870** | **0.849** | −0.021 |
| Surplus Gini | 0.292 | 0.305 | +0.013 |
| Buyer surplus (mean) | $25.62 | $26.98 | +$1.36 |
| Seller surplus (mean) | $23.86 | $26.66 | +$2.80 |

### 8.3 Interpretation

- **Deal rates are similar** (84.9% vs 82.5%), indicating that both matching strategies produce pairs that LLM agents can negotiate successfully when coherent sampling is enabled.
- **Surplus_max produces fewer sessions** (143 vs 192) because it only matches pairs with positive ZOPA, but the per-session deal rate is comparable.
- **Seller surplus is higher under surplus_max** ($26.66 vs $23.86), suggesting larger ZOPAs allow sellers to capture more surplus.
- **Allocative efficiency is marginally lower under surplus_max** (0.849 vs 0.870), which is unexpected and may reflect the smaller sample size or the interaction between matching strategy and LLM negotiation behaviour.
- These results differ from earlier gate-enabled experiments and should be interpreted in the context of the gate-disabled, free-language pipeline.

---

## 9. Experiment 6 — Supply-Demand Shift

### 9.1 Design

**Research question:** Do transaction prices and trade volume respond in the expected direction when demand or supply conditions shift structurally?

- **Conditions:** `baseline`, `demand_shock` (buyer values +$20), `supply_shock` (seller costs +$20)
- **Mode:** Market simulation, 8 ticks × 8 pairs/tick × 3 seeds × 3 conditions = 576 sessions
- **Agent type:** `llm_free_language`
- **Config note:** `coherent_sampling: false` — shifts to buyer_value / seller_cost ranges must not be overwritten.

| Condition | Buyer value range | Seller cost range | Avg buyer value | Avg seller cost |
|---|---|---|---|---|
| `baseline` | $90 – $170 | $40 – $90 | $130 | $65 |
| `demand_shock` | $110 – $190 | $40 – $90 | $150 (+$20) | $65 |
| `supply_shock` | $90 – $170 | $60 – $110 | $130 | $85 (+$20) |

### 9.2 Results

**Table 7. Supply-demand experiment outcomes by condition**

| Condition | Mean price | Liquidity | Total welfare | Buyer surplus | Seller surplus | Price dispersion |
|---|---|---|---|---|---|---|
| `baseline` | **$109.33** | **72.4%** | **$65.60** | $21.40 | $44.19 | $15.47 |
| `demand_shock` | **$113.96** | **72.4%** | **$87.24** | $39.07 | $48.18 | $16.19 |
| `supply_shock` | **$110.50** | **66.7%** | **$49.84** | $22.16 | $27.67 | $17.19 |

**Table 8. Effect sizes relative to baseline**

| Metric | Demand shock Δ | Supply shock Δ |
|---|---|---|
| Mean price | +$4.63 (+4.2%) | +$1.17 (+1.1%) |
| Liquidity | 0.0pp (0%) | −5.7pp (−7.9%) |
| Total welfare | +$21.64 (+33.0%) | −$15.76 (−24.0%) |
| Buyer surplus | +$17.67 (+82.6%) | +$0.76 (+3.6%) |
| Seller surplus | +$3.99 (+9.0%) | −$16.52 (−37.4%) |

### 9.3 Interpretation

- **Demand shock increases prices moderately** (+4.2%), increases welfare substantially (+33.0%), and maintains liquidity. Higher buyer values create larger gains from trade, benefiting both sides but especially buyers (+82.6% surplus increase).
- **Supply shock increases prices only slightly** (+1.1%) despite a +$20 increase in mean seller cost, reduces liquidity modestly (−5.7pp), and reduces total welfare substantially (−24.0%). Sellers absorb most of the cost increase, with seller surplus dropping 37.4%.
- **The asymmetry between demand and supply shock effects** suggests LLM agents respond differently to shifts in buyer vs seller constraint distributions.
- These results are directionally consistent with supply-demand theory but the magnitudes differ from classical predictions, which may reflect the LLM's anchoring to reference prices or the specific distributions used.

---

## 10. Cross-Experiment Discussion

### 10.1 Patterns Consistent with Economic Theory

| Economic principle | Evidence |
|---|---|
| Concession dynamics | LLM and rule-based agents produce declining offer trajectories over rounds (Exp 1) |
| Deadline clustering | 82.4% of agreements in last 2 rounds under tight horizon (Exp 2) |
| Market price stability | Negligible price trend slope (−$0.13/tick) in market dynamics (Exp 3) |
| Supply shock reduces welfare | −24.0% total welfare under supply shock (Exp 6) |
| Demand shock increases welfare | +33.0% total welfare under demand shock (Exp 6) |

### 10.2 Patterns Requiring Cautious Interpretation

| Expected behaviour | Observed behaviour | Interpretation |
|---|---|---|
| Shocks shift prices | Minimal price response under fixed anchor (Exp 4) | Prompt-level anchor may suppress price adjustment |
| Surplus-max improves efficiency | Efficiency marginally lower under surplus-max (Exp 5) | May reflect interaction with gate-disabled LLM behaviour |
| Supply shock raises prices proportionally | +1.1% price increase from +$20 seller cost shift (Exp 6) | LLM agents may anchor to reference prices |
| Demand shock raises prices proportionally | +4.2% price increase from +$20 buyer value shift (Exp 6) | Under-response relative to shift magnitude |

### 10.3 Role of the Anchor Mode

The anchor ablation (Experiment 4 extension) suggests that the reference price in the prompt is a significant design variable:
- **Fixed anchors** suppress price adjustment to shocks.
- **Updated anchors** allow modest dynamic price adjustment.
- **No anchor** produces high liquidity but minimal price variation.

This is a central methodological finding: the simulator's prompt design directly affects the economic patterns it produces.

---

## 11. Limitations

1. **Single model evaluated.** All results are specific to `Qwen/Qwen2.5-14B-Instruct`. Larger or different models may exhibit different negotiation behaviour.

2. **Three seeds only.** While 3 replications provide some robustness, more seeds would strengthen statistical claims.

3. **No gate ablation.** All final experiments run with the gate disabled. A systematic gate-on vs gate-off comparison would isolate the effect of LLM decision quality from the enforcement mechanism.

4. **Anchor mode and coherent sampling interact.** Experiments 4 and 6 disable coherent sampling while Experiments 3 and 5 enable it, making cross-experiment comparisons difficult.

5. **No human baseline.** All comparisons are between agent types or market conditions, not between LLM agents and human negotiators.

6. **Single-issue negotiation only.** All sessions negotiate a single price. Multi-issue negotiation may produce different dynamics.

---

## 12. Conclusions

This study demonstrates that a multi-agent LLM negotiation simulator produces economically interpretable results when carefully designed. Key conclusions:

1. **LLM free-language agents exhibit concession dynamics** that differ from rule-based baselines in opening aggressiveness and trajectory shape.

2. **Shorter negotiation horizons reduce deal rates modestly** and produce deadline clustering, though the effect is weaker than classical predictions for human bargainers.

3. **LLM-driven markets reach stable price levels** with persistent price dispersion, consistent with bilateral bargaining theory.

4. **The prompt-level reference price anchor is a major design confound.** Fixed anchors suppress price adjustment to shocks; anchor mode should be treated as a first-class experimental variable.

5. **Matching mechanism effects are modest** when combined with coherent sampling and gate-disabled LLM agents, differing from earlier gate-enabled results.

6. **Structural supply-demand shifts produce directionally correct but attenuated responses,** with demand shocks more effectively transmitted to prices than supply shocks.

These findings suggest that LLM negotiation simulators can serve as useful research tools for studying market dynamics, but results are sensitive to simulator design choices (anchor mode, feasibility gate, coherent sampling) that must be carefully documented and ablated.

---

## Appendix

### A. Configuration Summary

| Experiment | Config file | Agent type | Sessions | Seeds |
|---|---|---|---|---|
| 1 — Concession | `experiments/configs/exp_concession.yaml` | rule_based + llm_free_language | 144 | 42, 123, 456 |
| 2 — Deadline | `experiments/configs/exp_deadline.yaml` | llm_free_language | 216 | 42, 123, 456 |
| 3 — Market dynamics | `experiments/configs/exp_market_dynamics.yaml` | llm_free_language | 300 | 42, 123, 456 |
| 4 — Supply shock | `experiments/configs/exp_shock_response.yaml` | llm_free_language | 600 | 42, 123, 456 |
| 4-ext — Anchor ablation | `experiments/configs/exp_shock_response.yaml` | llm_free_language | ~1,200 | 42, 123, 456 |
| 5 — Mechanism | `experiments/configs/exp_mechanism.yaml` | llm_free_language | 335 | 42, 123, 456 |
| 6 — Supply-demand | `experiments/configs/exp_supply_demand.yaml` | llm_free_language | 576 | 42, 123, 456 |

### B. LLM Backend

| Parameter | Value |
|---|---|
| Model | `Qwen/Qwen2.5-14B-Instruct` |
| Backend | HuggingFace Transformers |
| Temperature | 0.2 |
| Max tokens | 512 |
| Timeout | 60s |
| Max retries | 3 |
| Negotiation mode | `free_language` (natural text with price tags) |

### C. Results Directory Structure

```
results/
├── exp1_concession/                         # Run ID: 20260313_013102
│   ├── concession_curves.csv
│   ├── experiment_summary.json
│   ├── parse_diagnostics.json
│   └── runs/                                # 6 per-simulation run dirs
├── exp2_deadline/                           # Run ID: 20260313_015631
│   ├── deadline.csv
│   ├── experiment_summary.json
│   ├── parse_diagnostics.json
│   └── runs/                                # 9 per-simulation run dirs
├── exp3_market_dynamics/                    # Run ID: 20260313_094631
│   ├── tick_stats.csv
│   ├── experiment_summary.json
│   ├── parse_diagnostics.json
│   └── runs/                                # 3 per-simulation run dirs
├── exp4_supply_shock/                       # Run ID: 20260313_115743
│   ├── shock_tick_data.csv
│   ├── experiment_summary.json
│   ├── parse_diagnostics.json
│   └── runs/                                # 6 per-simulation run dirs
├── exp4_anchor_environment_extension/       # Run ID: 20260314_122340
│   ├── shock_anchor_tick_data.csv
│   ├── experiment_summary.json
│   └── runs/                                # 12 per-simulation run dirs
├── exp5_mechanism/                          # Run ID: 20260313_031133
│   ├── mechanism_ticks.csv
│   ├── experiment_summary.json
│   ├── parse_diagnostics.json
│   └── runs/                                # 6 per-simulation run dirs
└── exp6_supply_demand/                      # Run ID: 20260313_054409
    ├── supply_demand_results.csv
    ├── experiment_summary.json
    ├── parse_diagnostics.json
    └── runs/                                # 9 per-simulation run dirs
```

### D. Reproducibility

All experiments were run from a single codebase version using seeded RNG with `fork()` per time step. Market generation and matching are deterministic given the same seed. LLM inference introduces non-determinism from the model itself.

To reproduce:
```bash
python experiments/run_free_language_all.py --seeds 42,123,456
python experiments/run_shock_anchor_ablation.py --seeds 42,123,456 --anchor-modes updated,no_anchor
```

### E. References

- Rubinstein, A. (1982). Perfect equilibrium in a bargaining model. *Econometrica*, 50(1), 97–109.
- Roth, A. E., & Murnighan, J. K. (1978). Equilibrium behavior and repeated play of the prisoner's dilemma. *Journal of Mathematical Psychology*, 17(2), 189–198.
- Rubinstein, A., & Wolinsky, A. (1985). Equilibrium in a market with sequential bargaining. *Econometrica*, 53(5), 1133–1150.
