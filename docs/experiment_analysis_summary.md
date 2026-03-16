# Free-Language Experiment Analysis Summary

## Pipeline Configuration
- Model: Qwen/Qwen2.5-14B-Instruct (HuggingFace backend)
- Device: auto (multi-GPU)
- Temperature: 0.2
- Gate: DISABLED
- Agent type: llm_free_language
- Seeds: 42, 123, 456 (all experiments)
- Total sessions: 2,171
- Total deals: 1,705
- Total runtime: ~14.7 hours
- Parse success rate: 100% (all experiments)
- Retry rate: 0% (all experiments)

## Experiment A: Concession Curves
- Sessions: 144 (72 rule_based + 72 llm_free_language)
- Deal rate: 97.2% (140/144)
- All 140 deals are LLM-driven acceptances (0 gate-driven)

### Rule-based trajectory (deterministic, zero variance):
| Round | Buyer | Seller |
|-------|-------|--------|
| 0 | $60.00 | — |
| 1 | — | $101.33 |
| 2 | $73.33 | — |
| 3 | — | $96.00 |
| 4 | $86.67 | — |
| 5 | — | $90.67 |

### LLM free-language trajectory (mean ± std):
| Round | Buyer | Seller |
|-------|-------|--------|
| 0 | $71.88 ± 3.79 | — |
| 1 | — | $89.93 ± 0.59 |
| 2 | $85.18 ± 0.87 | — |
| 3 | — | $87.60 ± 2.05 |
| 4 | $86.72 ± 1.93 | — |
| 5 | — | $88.06 ± 1.87 |

### Concession step sizes (LLM buyer):
- Step 1→2: +$13.31 (massive)
- Step 2→3: +$1.54
- Step 3→4: +$0.31
- Step 4→5: +$0.14
- Pattern: CONCAVE (Boulware/hardline)

### Surplus analysis (buyer_value=120, seller_cost=80, ZOPA=40):
- Mean deal price: $87.82
- Buyer surplus: $32.18 (80.5% of ZOPA)
- Seller surplus: $7.82 (19.5% of ZOPA)
- Buyer-to-seller concession ratio: 5.65:1
- 100% of deals within ZOPA, clustered in $80-$91.25 range

## Experiment C: Deadline Pressure
- Sessions: 216 (72 per condition: max_rounds = 6, 12, 20)
- Deal rate: 96.3% (208/216)
- All 208 deals are LLM-driven acceptances

### Results by condition:
| max_rounds | Deal Rate | Mean Price | Avg Rounds | Last-2-Round Share |
|------------|-----------|------------|------------|-------------------|
| 6 | 94.4% | $86.47 | 5.21 | **82.4%** |
| 12 | 97.2% | $86.73 | 6.70 | 15.7% |
| 20 | 97.2% | $84.93 | 7.30 | 11.4% |

### Surplus by condition (buyer_value=120, seller_cost=80):
| max_rounds | Buyer Surplus | Seller Surplus | Buyer % |
|------------|--------------|----------------|---------|
| 6 | $33.53 | $6.47 | 83.8% |
| 12 | $33.27 | $6.73 | 83.2% |
| 20 | $35.07 | $4.93 | 87.7% |

### Concession rate:
- 6 rounds: $2.73/round
- 12 rounds: $2.36/round
- 20 rounds: $2.18/round
- Tight deadline → 25% faster concession

## Experiment D: Market Dynamics
- Sessions: 300 (10 ticks × 10 pairs × 3 seeds)
- Deal rate: 82.3% (247/300)
- Timeout rate: 9.7%

### Tick-level stats (averaged across seeds):
| Tick | Mean Price | Price Std | Liquidity |
|------|-----------|-----------|-----------|
| 0 | 83.68 | 14.54 | — |
| 1 | 97.29 | 17.53 | — |
| 5 | 92.16 | 5.51 | — |
| 9 | 84.50 | 16.51 | — |

- Mean liquidity: 0.81
- Price trend slope: -0.60/tick (mild downward drift)
- Price dispersion: NO convergence (CV fluctuates 0.06-0.20)
- Surplus split: roughly symmetric (buyer 31.48, seller 31.68)

## Experiment H: Mechanism Comparison
- Sessions: 335 (random: 192, surplus_max: 143)
- Deal rate: 83.9% overall

### Mechanism comparison:
| Metric | Random | SurplusMax | Diff |
|--------|--------|------------|------|
| Total Surplus | 49.48 | 53.05 | **+3.56 (+7.2%)** |
| Price Std | 17.92 | 16.14 | -1.78 |
| Liquidity | 0.85 | 0.82 | -0.03 |
| Buyer Surplus | 25.52 | 26.61 | +1.09 |
| Seller Surplus | 23.96 | 26.43 | +2.47 |

## Experiment I: Supply-Demand Structure
- Sessions: 576 (192 per condition × 3 seeds)
- Deal rate: 70.5% (406/576)

### Condition comparison:
| Condition | Buyer Value | Seller Cost | Mean Price | Liquidity | Total Welfare |
|-----------|------------|-------------|-----------|-----------|---------------|
| Baseline | 130 | 65 | 109.33 | 0.724 | 65.60 |
| Demand shock | 150 (+20) | 65 | 113.96 (+4.63) | 0.724 | 87.24 (+21.65) |
| Supply shock | 130 | 85 (+20) | 110.50 (+1.17) | 0.667 | 49.84 (-15.76) |

### Surplus incidence:
| Condition | Buyer Surplus | Seller Surplus | Buyer Share |
|-----------|--------------|----------------|-------------|
| Baseline | 21.40 | 44.19 | 33% |
| Demand shock | 39.07 (+17.67) | 48.18 (+3.99) | 45% |
| Supply shock | 22.16 (+0.76) | 27.67 (-16.52) | 44% |

### Price elasticities:
- Demand shock: 0.275 (weak)
- Supply shock: 0.035 (very weak)
- Asymmetric: demand moves price 4x more than supply

### Key insight:
- Welfare channels are MECHANICAL (value - cost cancels price)
- Price channel is BEHAVIORAL (requires LLM to adjust strategy)
- Strong welfare results reflect experimental design, not agent behavior
- Weak price results reveal LLM anchoring / price stickiness

## Experiment E: Shock Response
- Sessions: 600 (300 per condition × 3 seeds)
- Deal rate: 70.5% (423/600)

### Difference-in-differences:
- No-shock: pre=107.88, post=110.62, diff=+2.75
- With-shock: pre=111.44, post=107.66, diff=-3.78
- **DiD = -6.53** (shock depresses prices)

### Recovery pattern:
- Seed 42: partial recovery
- Seed 123: continued decline
- Seed 456: mild depression, no recovery
- No consistent recovery within 10 ticks

### Liquidity:
- DiD = -0.060 (marginal suppression)

## Cross-Experiment Economic Patterns

### Strong patterns (defensible):
1. **Concave concession curves** — Boulware bargaining (Exp A)
2. **Deadline-induced concession acceleration** — 82% last-2-round deals (Exp C)
3. **Asymmetric concession burden** — buyer concedes 5.65x more (Exp A)
4. **ZOPA utilization bias** — only bottom 28% of ZOPA used (Exp A)
5. **Welfare tracks fundamentals** — but this is an accounting identity (Exp I)

### Moderate patterns (directionally correct):
6. **Surplus-max matching improves efficiency** — +7.2% (Exp H)
7. **Shock price depression** — DiD -6.53 (Exp E)
8. **Price stickiness** — elasticities 0.03-0.28 (Exp I)

### Weak patterns (insufficient evidence):
9. **Price convergence** — no clear trend (Exp D)
10. **Shock recovery** — inconsistent across seeds (Exp E)

### Central insight for discussion:
- Welfare/surplus results look "strong" because they're partly mechanical
- Price results look "weak" because they require genuine LLM behavioral adaptation
- This is the honest interpretation — don't overclaim the welfare results
