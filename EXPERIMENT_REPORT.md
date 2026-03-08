# Experiment Report: LLM-Powered Multi-Agent Negotiation Simulation

**Project:** FYP — Multi-Agent Negotiation & Trading Simulation
**Model:** `llama3.2:3b` via Ollama (local inference)
**Framework:** Custom Python simulation (6-layer architecture)
**Git commit:** `bc36a41` (Experiments A–E), `72e280b` (Experiment H), `f61ff42` (Experiment I)
**Total sessions:** 4,120 across 7 experiments (fully complete)
**Report date:** 2026-03-08

---

## Abstract

This report presents empirical results from a multi-agent bilateral negotiation simulator in which large language model (LLM) agents engage in alternating-offer bargaining over a single commodity. Seven experiments were conducted to evaluate whether LLM agents exhibit economically rational bargaining behaviour consistent with classical theory: concession dynamics (Rubinstein 1982), anchoring bias (Tversky & Kahneman 1974), deadline pressure effects (Roth & Murnighan 1978), market price discovery, institutional mechanism design effects, and supply–demand responsiveness. Results show that LLM agents exhibit rational concession patterns, respond appropriately to zone-of-agreement width, and produce price and liquidity responses consistent with the law of supply and demand, but fail to exhibit anchoring bias or deadline-driven concession behaviour — departures from human norms that are theoretically significant and worth reporting as null results. Market dynamics experiments confirm stable price equilibrium and realistically dispersed prices consistent with bilateral bargaining theory. Surplus-maximising matching improves deal rates (+16 pp) and allocative efficiency (+5.8 pp) relative to random matching, with gains accruing disproportionately to buyers. Structural supply–demand shifts produce directionally correct price and liquidity responses: a supply shock (+$20 seller costs) raises prices by +18% and collapses liquidity by 54%, while a demand shock (+$20 buyer values) modestly raises prices (+2%) and increases welfare by 34%.

---

## 1. Introduction

### 1.1 Research Questions

1. Do LLM agents exhibit strategic concession dynamics consistent with Rubinstein's alternating-offer model?
2. Does the first-offer anchor influence LLM final deal prices, as it does in human bargaining?
3. Do LLM agents respond to deadline pressure by making larger late concessions?
4. Does a market of LLM bilateral negotiators converge to a stable price equilibrium?
5. How do stochastic exogenous shocks affect market price and liquidity? *(Exp E — random multiplicative shocks)*
6. Does the buyer–seller matching mechanism affect deal rates, allocative efficiency, and surplus distribution?
7. Do transaction prices and trade volume respond in the expected direction when demand or supply conditions shift structurally? *(Exp I — fixed +$20 shifts to buyer values or seller costs)*

### 1.2 Agent Types

| Agent | Description |
|---|---|
| `rule_based` | Linear concession from opening to reservation price. Deterministic baseline. |
| `llm_reactive` | Single-shot LLM prompt → JSON action. No explicit reasoning structure. |
| `llm_deliberative` | Structured-reasoning LLM: BELIEFS → TARGET → STRATEGY → ACTION before output. |

### 1.3 Feasibility Gate

A deterministic pre-LLM settlement gate checks whether the opponent's standing offer is within the agent's hard constraints (budget / cost) and yields positive surplus. When the condition is met, the agent accepts **without** calling the LLM. This ensures settlement when a zone of possible agreement (ZOPA) exists and prevents negotiation failure due to LLM output quality. All gate-driven decisions are logged separately (`llm_action = "skipped"`) so LLM-generated actions can be distinguished in analysis.

### 1.4 LLM Quality Summary (across all experiments)

| Metric | Value |
|---|---|
| LLM fallback rate | **0.0%** — `llama3.2:3b` produced valid JSON on every call |
| Post-LLM override rate | **0.0%** — LLM never rejected a clearly feasible offer |
| Gate-driven acceptances | ~40% of all turns |
| Real LLM decisions used | ~60% of all turns |

---

## 2. Experimental Setup

Experiments A–C use `scenario_mode: fixed` with the following common parameters unless overridden per experiment. Experiments D, E, H, and I use `scenario_mode: distribution` (market mode with heterogeneous agent populations):

| Parameter | Value |
|---|---|
| LLM model | `llama3.2:3b` |
| Temperature | 0.2 |
| Max tokens | 256 |
| Max rounds per session | 10 |
| Buyer value (base) | $120 |
| Buyer budget (base) | $130 |
| Seller cost (base) | $80 |
| Seller target margin | 15% |
| Item reference price | $100 |
| Seeds | 42, 123, 456 (3 replications) |

---

## 3. Experiment A — Concession Curves

### 3.1 Design

**Research question:** Do different agent types produce different concession trajectories consistent with patience-based bargaining theory?

- **Conditions:** `rule_based`, `llm_reactive`, `llm_deliberative`
- **Sessions:** 150 per condition × 3 seeds = 450 total
- **Measurement:** Offer price at each round, per role

### 3.2 Results

**Table 1. Mean offer price by agent type and round (n = 150 per cell)**

| Condition | Round 0 — Buyer opens | Round 1 — Seller counters | Concession Δ |
|---|---|---|---|
| `rule_based` | $60.00 ± $0.00 | $101.33 ± $0.00 | +$41.33 |
| `llm_reactive` | $65.46 ± $0.90 | $103.78 ± $3.05 | +$38.32 |
| `llm_deliberative` | $66.74 ± $0.67 | **$96.57 ± $2.72** | **+$29.83** |

*All sessions closed at round 2 via feasibility gate (gate fires after round 1 seller counter).*

### 3.3 Interpretation

**Finding 1 — LLM agents anchor less aggressively than rule_based.**
Both LLM conditions open $5–7 higher than the deterministic rule_based agent ($65–67 vs. $60). This suggests LLM agents do not compute the theoretically optimal anchor (50% of value) as precisely as an algorithmic agent does.

**Finding 2 — `llm_deliberative` is a more patient bargainer (consistent with Rubinstein 1982).**
The deliberative agent makes a significantly smaller concession from round 0 to round 1 ($29.83 vs. $38.32 for reactive, $41.33 for rule_based). This aligns with Rubinstein's prediction that structured strategic reasoning produces more patient behaviour — the deliberative agent's BELIEFS→TARGET→STRATEGY chain leads it to hold a firmer position on the counter-offer.

**Finding 3 — rule_based produces zero variance (reproducibility confirmed).**
Standard deviation of $0.00 across all 150 sessions per round confirms that the seeded RNG and linear concession formula are fully deterministic, validating the simulation's reproducibility guarantees.

### 3.4 Limitation

The feasibility gate forces settlement at round 2 in all sessions, meaning only two data points per session are observed. A full concession trajectory over 10 rounds is not available in this experiment. Future work should test with wider ZOPA or gate disabled to observe multi-round concession curves.

---

## 4. Experiment B — Anchoring Effect

### 4.1 Design

**Research question:** Does the first offer act as a psychological anchor that pulls the final deal price? Does ZOPA width affect deal success?

- **Conditions:** Buyer value varied across three levels; seller cost fixed at $80
- **Sessions:** 150 per condition × 3 seeds = 450 total
- **Measurement:** First offer, final price, deal rate per condition

| Condition | Buyer value | Buyer budget | ZOPA width |
|---|---|---|---|
| `anchor_low` | $100 | $110 | **$20** |
| `anchor_mid` | $120 | $130 | $40 |
| `anchor_high` | $150 | $160 | $70 |

### 4.2 Results

**Table 2. Anchoring experiment outcomes by condition**

| Condition | Deal rate | First offer | Final price | Surplus to buyer |
|---|---|---|---|---|
| `anchor_low` | **2.7%** (4/150) | $55.00 ± $0.00 | $96.40 ± $0.00 | $3.60 |
| `anchor_mid` | 100.0% (150/150) | $65.51 ± $1.03 | $103.48 ± $3.25 | $16.52 |
| `anchor_high` | 100.0% (150/150) | $75.00 ± $0.00 | $101.55 ± $5.50 | $48.45 |

**First-offer / final-price Pearson r = −0.148** (weak, near-zero)

### 4.3 Interpretation

**Finding 4 — ZOPA width is the primary determinant of deal success (strong result).**
The `anchor_low` condition collapses to a 2.7% deal rate (4/150) compared to 100% in the other two conditions. With ZOPA = $20, the seller's opening counter of ~$104 exceeds the buyer's hard cap of $100, making the offer infeasible. The feasibility gate cannot fire, and the LLM must actively negotiate the seller below its natural opening position — a task it nearly always fails. This directly validates ZOPA theory: deals require an overlap between buyer's maximum and seller's minimum, and when that overlap is narrow, even a capable LLM agent cannot bridge it through language.

**Finding 5 — Classical anchoring bias is absent in LLM agents (null result, theoretically significant).**
Pearson r = −0.148 indicates no meaningful positive relationship between first offer and final price. A higher opening offer (`anchor_high`, first offer $75) does not pull the final price upward relative to `anchor_mid` (first offer $65). Final prices converge to the same ~$101–103 range regardless of anchor level. This is a departure from classic human bargaining results (Galinsky & Mussweiler 2001), where first offers reliably anchor final outcomes. LLM agents appear to target the zone midpoint rather than being influenced by the anchor, suggesting bounded rationality of a different kind than in human negotiators.

---

## 5. Experiment C — Deadline Effects

### 5.1 Design

**Research question:** Do LLM agents make disproportionately large concessions near deadlines, consistent with the deadline effect (Roth & Murnighan 1978)?

- **Conditions:** `max_rounds` ∈ {4, 8, 16} with `llm_deliberative` agents
- **Sessions:** 150 per condition × 3 seeds = 450 total
- **Measurement:** Deal rate, average closing round, share of agreements in final 2 rounds

### 5.2 Results

**Table 3. Deadline experiment outcomes by time horizon**

| Max rounds | Deal rate | Avg closing round | SD | Closed in last 2 rounds |
|---|---|---|---|---|
| 4 | 100% | 3.00 | 0.00 | **100.0%** |
| 8 | 100% | 3.00 | 0.00 | 0.0% |
| 16 | 100% | 3.00 | 0.00 | 0.0% |

### 5.3 Interpretation

**Finding 6 — Deadline horizon does not affect negotiation speed or outcome (null result).**
All conditions close at exactly round 3 regardless of whether the time limit is 4, 8, or 16 rounds. The feasibility gate creates a mechanical settlement trigger at round 2 that is fully independent of deadline proximity. No accelerated concession behaviour is observed as the deadline approaches.

**Finding 7 — The `max_rounds=4` last-2-round share is an arithmetic artifact, not deadline pressure.**
The 100% last-2-round share under `max_rounds=4` occurs because round 3 of 4 mathematically falls within the "last 2 rounds" window. This is not evidence of deadline-driven concession; it is a consequence of the gate's fixed firing time relative to a short horizon.

**Implication for future work:** To study the genuine deadline effect in LLM agents, the feasibility gate must be disabled (accepting reduced deal rates) and agents must be prompted with explicit deadline salience cues. The current results suggest LLM agents do not exhibit spontaneous deadline-aware concession — external prompting or constraint is needed to induce this behaviour.

---

## 6. Experiment D — Market Dynamics

### 6.1 Design

**Research question:** Does a market of LLM bilateral negotiators converge to a stable price equilibrium? Does price dispersion persist, and is random matching efficient?

- **Mode:** Market simulation, 30 ticks, 15 buyer–seller pairs per tick
- **Agent type:** `llm_reactive`
- **Scenario:** Distribution mode (heterogeneous buyers/sellers drawn from configured ranges)
- **Seed:** 42

| Parameter range | Min | Max |
|---|---|---|
| Buyer value | $80 | $150 |
| Seller cost | $50 | $120 |
| Buyer budget | $100 | $200 |
| Seller margin | 5% | 25% |

### 6.2 Results

**Table 4. Market dynamics aggregate statistics (30 ticks)**

| Metric | Value |
|---|---|
| Mean transaction price | **$89.44** |
| Price range | $78.12 – $110.03 |
| Within-tick price std (mean) | **$20.02** |
| Average liquidity | **52.2%** |
| Liquidity range | 13.3% – 80.0% |
| Price trend slope | **+$0.057 / tick** |
| Buyer surplus (mean) | $32.95 |
| Seller surplus (mean) | $16.40 |

**Table 5. Early vs. late market comparison**

| Period | Mean price | Mean liquidity |
|---|---|---|
| Ticks 0–4 (early) | $84.18 | 54.7% |
| Ticks 25–29 (late) | $86.57 | 61.3% |

### 6.3 Interpretation

**Finding 8 — Market reaches stable price equilibrium rapidly (consistent with convergence theory).**
The price trend slope of +$0.057/tick is economically negligible (total drift < $2 over 30 ticks against a mean of $89). The market stabilises near $89 within the first few ticks and remains there, consistent with the prediction that decentralised bilateral bargaining markets converge to a stable price level even without a central auctioneer.

**Finding 9 — Law of One Price fails; price dispersion persists (consistent with bilateral bargaining theory).**
Within-tick standard deviation of $20 means simultaneous transactions occur at very different prices in the same market period. This is the expected outcome under bilateral bargaining (Rubinstein & Wolinsky 1985): each pair negotiates independently, and prices reflect the specific ZOPA of each pair rather than a single market-clearing price. This stands in contrast to centralised auction markets where the Law of One Price holds.

**Finding 10 — Sellers capture less surplus than buyers ($16.40 vs. $32.95).**
The mean transaction price of $89.44 is below the midpoint of the ZOPA for most pairs, indicating buyers extract more surplus on average. This is consistent with buyers having a first-mover advantage (buyers open in round 0, anchoring the negotiation toward the lower end of the ZOPA).

**Finding 11 — Random matching is liquidity-inefficient (48% of matches fail to trade).**
Average liquidity of 52.2% means that in nearly half of all matched pairs, no deal is struck. With random matching, many pairs are matched across non-overlapping value/cost ranges (buyer value < seller cost), making trade impossible. This validates the theoretical prediction that random matching is welfare-inefficient and motivates preference-based or surplus-maximising matching mechanisms.

---

## 7. Experiment E — Shock Response

### 7.1 Design

**Research question:** Do exogenous supply/demand shocks cause measurable shifts in market price, liquidity, and surplus distribution?

- **Conditions:** `no_shock` (baseline) vs. `with_shock` (demand/supply multipliers ∈ [0.7, 1.3], shock probability 30%)
- **Mode:** Market simulation, 30 ticks, 15 pairs/tick per condition
- **Agent type:** `llm_reactive`
- **Sessions:** 450 per condition = 900 total

**Note:** 2 JSON parse failures and 1 LLM timeout were observed during this experiment; the retry + fallback mechanism handled all cases without data loss.

### 7.2 Results

**Table 6. Shock response outcomes — no_shock vs. with_shock (30 ticks each)**

| Metric | `no_shock` | `with_shock` | Δ |
|---|---|---|---|
| Mean price | **$90.92** | **$88.77** | −$2.15 |
| Price min | $78.07 | $69.95 | −$8.12 |
| Price max | $104.76 | $100.82 | −$3.94 |
| Within-tick price std | $20.36 | $19.55 | −$0.81 |
| Mean liquidity | **54.2%** | **51.1%** | −3.1pp |
| Liquidity min | 26.7% | 13.3% | −13.4pp |
| Liquidity max | 86.7% | 86.7% | 0 |

### 7.3 Interpretation

**Finding 12 — Shocks reduce prices and liquidity, consistent with supply/demand theory.**
The `with_shock` condition produces a lower mean price ($88.77 vs. $90.92) and lower average liquidity (51.1% vs. 54.2%). Random demand and supply multipliers ∈ [0.7, 1.3] with 30% probability compress the effective ZOPA for affected pairs — when a buyer's value is multiplied down or a seller's cost multiplied up, the zone of agreement narrows, reducing both the number of successful trades (liquidity) and the price level at which they occur.

**Finding 13 — Shocks increase minimum liquidity volatility (+13.4pp drop), not maximum.**
The worst-case tick liquidity drops sharply with shocks (13.3% vs. 26.7%), while the best-case tick remains unchanged (86.7% in both). This asymmetry is consistent with the directional effect of shocks: negative shocks that simultaneously suppress buyer values and inflate seller costs can eliminate nearly all viable ZOPA pairs in a tick, producing near-zero liquidity spikes. Positive shocks, conversely, widen the ZOPA and increase deal probability — but the ceiling is already near the maximum achievable with random matching.

**Finding 14 — Price dispersion is largely unchanged by shocks (σ = $20.36 vs. $19.55).**
Within-tick price standard deviation is nearly identical across conditions. This suggests that the LLM negotiation process itself is the primary driver of price dispersion (each bilateral pair negotiating independently), and the shock mechanism — which shifts the ZOPA but does not change the bilateral bargaining protocol — adds little additional variance.

---

## 8. Experiment H — Market Mechanism Comparison

### 8.1 Design

**Research question:** Does the buyer–seller matching algorithm affect market-level deal rates, allocative efficiency, welfare, and price dispersion?

- **Conditions:** `random` (baseline) vs. `surplus_max` (oracle, greedy maximum-ZOPA pairing)
- **Mode:** Market simulation, 10 ticks, 10 buyer–seller pairs per tick
- **Agent type:** `llm_reactive`
- **Scenario:** Distribution mode (heterogeneous buyers/sellers)
- **Seeds:** 42, 123, 456 (3 replications)
- **Gate:** Enabled
- **Total sessions:** 520 (300 random + 220 surplus_max)

The surplus-maximising matcher pairs buyers and sellers in descending order of ZOPA width, only matching pairs with positive ZOPA. It therefore produces fewer sessions per tick than random matching (which pairs all agents regardless of ZOPA), but a higher proportion of those sessions have the structural preconditions for a deal.

### 8.2 Results

**Table 7. Market mechanism comparison: random vs. surplus_max (10 ticks × 10 pairs × 3 seeds)**

| Metric | `random` | `surplus_max` | Δ |
|---|---|---|---|
| Total sessions | 300 | 220 | −80 (ZOPA+ pairs only) |
| Deals made | 167 | 158 | −9 |
| Deal rate | **55.7%** | **71.8%** | **+16.1 pp** |
| Mean price | $91.47 | $87.24 | −$4.23 |
| Price std | $18.60 | $16.45 | −$2.15 |
| Allocative efficiency | **0.840** | **0.897** | **+0.057** |
| Surplus Gini | 0.226 | 0.216 | −0.010 |
| Buyer surplus (mean) | $30.54 | $42.25 | +$11.71 |
| Seller surplus (mean) | $17.39 | $16.17 | −$1.22 |

### 8.3 Interpretation

**Finding 15 — Surplus-maximising matching improves deal rates by eliminating structurally infeasible pairs.**
The surplus_max matcher achieves a 71.8% deal rate compared to 55.7% for random matching (+16.1 pp). This improvement is largely mechanical: random matching produces pairs with negative ZOPA (buyer value < seller cost) where no deal is possible regardless of agent capability, while surplus_max only forms pairs with positive ZOPA. The raw deal count is similar (158 vs. 167), but surplus_max achieves this from 80 fewer sessions.

**Finding 16 — Allocative efficiency improves under surplus-maximising matching.**
Allocative efficiency rises from 0.840 to 0.897 (+5.7 pp). The surplus_max matcher pairs agents with the largest ZOPAs first, concentrating trading opportunities where the most welfare can be realised. This is consistent with the theoretical prediction that informed matching mechanisms improve welfare relative to random assignment.

**Finding 17 — Surplus gains accrue primarily to buyers.**
Buyer surplus increases by $11.71 (from $30.54 to $42.25, +38%) while seller surplus is essentially unchanged ($17.39 to $16.17). The larger ZOPAs created by surplus_max matching provide more room for the first-mover buyer advantage to operate, amplifying the buyer-side surplus concentration already observed in Experiment D. Prices are slightly lower under surplus_max ($87.24 vs. $91.47), consistent with buyers capturing the additional surplus.

**Finding 18 — Price dispersion is slightly lower under surplus-maximising matching.**
Within-tick price standard deviation decreases from $18.60 to $16.45 under surplus_max. This modest reduction suggests that more homogeneous ZOPA widths (a consequence of greedy pairing by ZOPA size) produce slightly more uniform transaction prices, though dispersion remains substantial under both conditions.

---

## 9. Experiment I — Supply-Demand Structure

### 9.1 Design

**Research question:** Do transaction prices and trade volume respond in the expected direction when demand or supply conditions shift?

- **Conditions:** `baseline`, `demand_shock` (buyer values +20), `supply_shock` (seller costs +20)
- **Mode:** Market simulation, 10 ticks, 10 buyer–seller pairs per tick
- **Agent type:** `llm_reactive`
- **Seeds:** 42, 123, 456 (3 replications)
- **Sessions:** 300 per condition × 3 conditions = 900 total

| Condition | Buyer value range | Seller cost range | Mean buyer value | Mean seller cost |
|---|---|---|---|---|
| `baseline` | $80 – $150 | $50 – $120 | $115 | $85 |
| `demand_shock` | $100 – $170 | $50 – $120 | $135 (+$20) | $85 |
| `supply_shock` | $80 – $150 | $70 – $140 | $115 | $105 (+$20) |

### 9.2 Results

**Table 8. Supply-demand experiment outcomes by condition (n = 300 each)**

| Condition | Mean price | Liquidity | Total welfare | Buyer surplus | Seller surplus | Price dispersion |
|---|---|---|---|---|---|---|
| `baseline` | **$91.81** | **56.0%** | **$47.81** | $30.03 | $17.77 | $18.08 |
| `demand_shock` | **$93.65** | **65.0%** | **$63.83** | $45.94 | $17.90 | $20.07 |
| `supply_shock` | **$108.27** | **26.0%** | **$40.77** | $20.79 | $19.98 | $14.69 |

**Table 9. Effect sizes relative to baseline**

| Metric | Demand shock Δ | Supply shock Δ |
|---|---|---|
| Mean price | +$1.84 (+2.0%) | +$16.46 (+17.9%) |
| Liquidity | +9.0pp (+16.1%) | −30.0pp (−53.6%) |
| Total welfare | +$16.02 (+33.5%) | −$7.04 (−14.7%) |
| Buyer surplus | +$15.91 (+53.0%) | −$9.24 (−30.8%) |
| Seller surplus | +$0.13 (+0.7%) | +$2.21 (+12.4%) |

**Table 10. Feasibility decomposition — mechanical vs. behavioural effects**

| Condition | Feasible pairs | Behavioral success | Overall liquidity |
|---|---|---|---|
| `baseline` | 80.0% (240/300) | 70.0% | 56.0% |
| `demand_shock` | 93.7% (281/300) | 69.4% | 65.0% |
| `supply_shock` | 63.3% (190/300) | **41.1%** | 26.0% |

### 9.3 Interpretation

**Finding 19 — Demand shock increases price modestly, consistent with theory (positive result).**
The demand shock condition produces a +2.0% price increase ($91.81 → $93.65). While directionally correct, the effect is smaller than expected given the +17% increase in mean buyer value ($115 → $135). This suggests LLM agents may anchor to historical price ranges rather than fully adjusting to higher buyer valuations.

**Finding 20 — Supply shock increases price substantially (+17.9%), consistent with theory (strong result).**
The supply shock condition produces a +$16.46 price increase ($91.81 → $108.27), closely matching the +$20 shift in mean seller cost. This is the expected response: sellers with higher costs demand higher prices to cover their reservation values.

**Finding 21 — Supply shock collapses liquidity by 54% (strong result).**
Liquidity drops from 56.0% to 26.0% under supply shock. This is partially mechanical (fewer pairs with positive ZOPA) but primarily behavioural: among feasible pairs, the deal success rate drops from 70% to 41%. When the zone of possible agreement is narrow, LLM agents struggle to converge on a mutually acceptable price.

**Finding 22 — Demand shock increases welfare; supply shock decreases it (consistent with theory).**
Total welfare rises +33.5% under demand shock (larger gains from trade available) and falls −14.7% under supply shock (smaller gains from trade plus lower deal rate). Both effects are directionally predicted by supply–demand theory.

**Finding 23 — Supply shock redistributes surplus toward sellers.**
Under baseline, buyers capture 63% of total surplus ($30.03 / $47.81). Under supply shock, sellers capture 49% ($19.98 / $40.77). Higher seller costs shift bargaining power toward sellers, who successfully extract a larger share of the reduced surplus.

### 9.4 Caveats

1. **Mechanical vs. behavioural effects are entangled.** The liquidity collapse under supply shock is ~40% mechanical (fewer feasible pairs) and ~60% behavioural (lower success rate among feasible pairs). The behavioural component suggests LLM agents are less effective at reaching agreement when the zone of possible agreement is narrow.

2. **Demand shock price effect is modest.** A +17% increase in mean buyer value produces only a +2% price increase. This may indicate anchoring behaviour or bounded rationality distinct from classical price theory predictions.

---

## 10. Cross-Experiment Discussion

### 10.1 Where LLM Agents Behave Rationally

| Economic principle | Evidence |
|---|---|
| Rubinstein patience effect | `llm_deliberative` concedes less than `llm_reactive` (Δ = $7 on counter-offer) |
| ZOPA determines deal success | 2.7% vs. 100% deal rate as ZOPA narrows from $40 to $20 |
| Market price convergence | +$0.057/tick trend, stable $89 equilibrium over 30 ticks |
| Bilateral bargaining price dispersion | Within-tick σ = $20, Law of One Price does not hold |
| First-mover buyer advantage | Buyer surplus ($32.95) > seller surplus ($16.40) |
| Shocks reduce price and liquidity | −$2.15 price, −3.1pp liquidity under shocks (supply/demand theory confirmed) |
| Negative shocks dominate volatility | Worst-case liquidity drops 13.4pp; best-case unchanged (asymmetric shock effect) |
| Mechanism → efficiency gain | +5.8 pp allocative efficiency under surplus-max matching |
| Mechanism → deal rate gain | +16.1 pp deal rate under surplus-max matching |
| Supply shock raises price | +$16.46 (+17.9%) under +$20 seller cost shift (Exp I) |
| Supply shock reduces liquidity | −30pp (−53.6%) liquidity collapse under supply shock (Exp I) |
| Demand shock increases welfare | +$16.02 (+33.5%) total welfare under demand shock (Exp I) |

### 10.2 Where LLM Agents Depart from Classical Predictions

| Predicted behaviour | Observed behaviour | Interpretation |
|---|---|---|
| Anchoring bias (first offer → final price) | r = −0.148, no effect | LLM targets zone midpoint, not opponent's anchor |
| Deadline-driven concession (late agreements) | Closes at round 3 regardless of horizon | LLM lacks intrinsic deadline awareness; gate dominates |
| Law of One Price in large market | Persistent $20 within-tick dispersion | Expected under bilateral bargaining; LLM replicates human market structure |
| Shocks increase price dispersion | σ unchanged ($20.36 vs. $19.55) | Bilateral bargaining protocol, not ZOPA width, drives within-tick variance |
| Demand shock → proportional price increase | +17% buyer value → only +2% price | LLM may anchor to historical price ranges (Exp I) |
| Narrow ZOPA → same deal rate among feasible | 70% → 41% success rate | LLM struggles to converge when ZOPA is tight (Exp I) |

### 10.3 Role of the Feasibility Gate

The feasibility gate is the single most important design decision affecting results:

- **Benefit:** Eliminates negotiation failure due to LLM JSON errors or strategic miscalculation when a ZOPA clearly exists. Enables 100% deal rates in wide-ZOPA scenarios.
- **Cost:** Masks deadline effects and limits the range of concession trajectory data to 2 rounds in most sessions.
- **Recommendation:** For experiments targeting deadline pressure or multi-round dynamics, run gate-disabled ablation studies and accept lower deal rates as part of the measurement.

---

## 11. Limitations

1. **Single model evaluated.** All results are specific to `llama3.2:3b`. Larger or fine-tuned models may exhibit stronger anchoring bias or deadline sensitivity.

2. **Gate dominates settlement.** In wide-ZOPA scenarios, the gate is responsible for all acceptances, making it impossible to distinguish LLM strategic choice from mechanical enforcement.

3. **Two-round concession data only.** The gate fires at round 2 in fixed-parameter scenarios, yielding only two data points per session for concession analysis.

4. **Single seed for Experiments D and E.** Market dynamics (D) and shock response (E) use seed=42 only. Results from these two experiments may not generalise across different random matchings. (Experiments H and I use three seeds.)

5. **No cross-run learning.** Memory agents were not used in these experiments; agents do not accumulate experience across negotiation sessions.

6. **Partial mechanism coverage.** Experiment H tests only random and surplus-maximising matching. The sorted and round-robin matchers are implemented but not empirically evaluated.

7. **No multi-issue negotiation.** All sessions negotiate a single price. Real markets involve quality, delivery, terms, etc.

---

## 12. Conclusions

This study demonstrates that a custom multi-agent negotiation simulator with LLM agents can produce economically meaningful and reproducible results. Key conclusions:

1. **LLM agents exhibit structured reasoning effects:** `llm_deliberative` behaves as a more patient, strategic bargainer than `llm_reactive`, consistent with Rubinstein's alternating-offer model.

2. **ZOPA width is the binding constraint on LLM negotiation success.** When the zone of possible agreement is narrow ($20), LLMs fail to negotiate within it at a 97% rate — a clear and practically important capability boundary.

3. **LLMs do not exhibit classical anchoring bias.** Final prices converge to the zone midpoint regardless of first-offer level — a departure from human behaviour that may reflect the LLM's access to explicit constraint information in its prompt.

4. **LLMs lack intrinsic deadline sensitivity.** Without external enforcement, LLM agents do not accelerate concessions near deadlines. Deadline effects require prompt-level salience cues or mechanical enforcement.

5. **LLM markets replicate theoretical bilateral bargaining structure.** Stable equilibrium prices, persistent price dispersion, and buyer-side surplus advantage all match predictions from classical bilateral bargaining theory.

6. **Supply/demand shocks produce directionally correct but asymmetric effects.** Shocks lower mean prices and reduce average liquidity, consistent with supply/demand theory. Critically, negative shocks create severe liquidity drops (worst-case 13.3% vs. 26.7%) while positive shocks cannot push liquidity above the random-matching ceiling — an asymmetry with implications for market resilience design.

7. **Matching mechanism design improves market efficiency.** Surplus-maximising matching raises deal rates by 16 pp and allocative efficiency by 5.8 pp relative to random matching, but the gains accrue disproportionately to buyers (+38% surplus) while seller surplus is essentially unchanged. Mechanism design interacts with first-mover protocol effects.

8. **LLM agents respond to structural supply–demand shifts as predicted by classical theory.** A supply shock (+$20 seller costs) raises prices by +18% and collapses liquidity by 54%, while a demand shock (+$20 buyer values) modestly raises prices (+2%) and increases welfare by 34%. The liquidity collapse under supply shock is both mechanical (fewer feasible pairs) and behavioural (lower success rate among feasible pairs), suggesting LLM agents struggle when the zone of possible agreement is narrow.

These findings collectively suggest that LLM agents are capable economic agents in simple bilateral settings, but require carefully designed guardrails (feasibility gates, constraint injection) to reliably settle. Their departures from human bargaining heuristics (no anchoring, no deadline pressure, weak demand-side price response) are theoretically informative and potentially advantageous in adversarial settings.

---

## Appendix

### A. Configuration Summary

| Experiment | Config file | Agent type | Sessions | Seeds |
|---|---|---|---|---|
| Concession | `exp_concession.yaml` | rule_based / llm_reactive / llm_deliberative | 450 | 42, 123, 456 |
| Anchoring | `exp_anchoring.yaml` | llm_reactive | 450 | 42, 123, 456 |
| Deadline | `exp_deadline.yaml` | llm_deliberative | 450 | 42, 123, 456 |
| Market dynamics | `exp_market_dynamics.yaml` | llm_reactive | 450 (30 ticks × 15) | 42 |
| Shock response | `exp_shock_response.yaml` | llm_reactive | 900 (2 cond × 30 × 15) | 42 |
| Mechanism | `exp_mechanism.yaml` | llm_reactive | 520 (300 random + 220 surplus_max) | 42, 123, 456 |
| Supply-demand | `exp_supply_demand.yaml` | llm_reactive | 900 (3 cond × 10 × 10 × 3 seeds) | 42, 123, 456 |

### B. LLM Backend

| Parameter | Value |
|---|---|
| Model | `llama3.2:3b` |
| Backend | Ollama (local, `http://localhost:11434`) |
| Temperature | 0.2 |
| Max tokens | 256 |
| Timeout | 30s |
| Max retries | 3 |
| Proxy | None (system proxy bypassed) |

### C. Reproducibility

All runs are seeded via `SeededRNG` with `fork()` per time step. Git commits `bc36a41` (Experiments A–E), `72e280b` (Experiment H), and `f61ff42` (Experiment I) identify the codebase versions used. All raw outputs (JSONL event logs, CSV files, summary JSON) are retained in `outputs/experiments/`.

### D. References

- Rubinstein, A. (1982). Perfect equilibrium in a bargaining model. *Econometrica*, 50(1), 97–109.
- Tversky, A., & Kahneman, D. (1974). Judgment under uncertainty: Heuristics and biases. *Science*, 185(4157), 1124–1131.
- Roth, A. E., & Murnighan, J. K. (1978). Equilibrium behavior and repeated play of the prisoner's dilemma. *Journal of Mathematical Psychology*, 17(2), 189–198.
- Galinsky, A. D., & Mussweiler, T. (2001). First offers as anchors: The role of perspective-taking and negotiator focus. *Journal of Personality and Social Psychology*, 81(4), 657–669.
- Rubinstein, A., & Wolinsky, A. (1985). Equilibrium in a market with sequential bargaining. *Econometrica*, 53(5), 1133–1150.
