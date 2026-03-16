# Thesis Revision Plan — Free-Language Experiments Integration

## Critical Context

The current thesis reports results from the **OLD pipeline**:
- Model: llama3.2:3b (Ollama)
- Gate: ENABLED (drives ~40% of acceptances)
- Agent types: rule_based, llm_reactive, llm_deliberative
- Experiment B (Anchoring): included

The NEW free-language experiments use a **fundamentally different pipeline**:
- Model: Qwen/Qwen2.5-14B-Instruct (HuggingFace)
- Gate: DISABLED
- Agent type: llm_free_language (natural language with price tag extraction)
- Experiment B: NOT re-run (anchoring was a null result)
- 6 experiments: A, C, D, E, H, I — 2,171 sessions total, 100% parse success

## What Changes Between Old and New Results

### Experiment A (Concession Curves)
- OLD: Gate fires at round 2, only 2 data points, 100% deal rate (all gate-driven), 3 agent types compared
- NEW: Full 10-round trajectories, 97.2% deal rate, ALL LLM-driven acceptances, rule_based vs llm_free_language
- NEW findings: Concave (Boulware) concession curves, 5.65:1 buyer/seller concession ratio, buyer captures 80.5% of surplus, seller anchoring weakness

### Experiment C (Deadline Pressure)
- OLD: Null result — all settle at round 3 regardless of deadline (gate-driven)
- NEW: Strong deadline effect — 82% last-2-round share under 6-round deadline vs 11% under 20 rounds
- NEW findings: Concession rate 25% higher under tight deadline ($2.73/round vs $2.18/round), directionally correct

### Experiment D (Market Dynamics)
- OLD: Single seed, exploratory
- NEW: 3 seeds, 300 sessions, 82.3% deal rate
- NEW findings: Stable liquidity ~81%, mild downward price drift, NO price convergence (high dispersion persists)

### Experiment E (Shock Response)
- OLD: Single seed, exploratory
- NEW: 3 seeds, 600 sessions, 70.5% deal rate
- NEW findings: DiD estimate -6.53 price impact, persistent depression (no recovery), cross-seed variance dominates

### Experiment H (Mechanism Comparison)
- OLD: 3 seeds with gate-on
- NEW: 3 seeds, 335 sessions, 83.9% deal rate, only random + surplus_max
- NEW findings: SurplusMax +7.2% total surplus, lower dispersion, directionally correct

### Experiment I (Supply-Demand)
- OLD: 3 seeds with gate-on
- NEW: 3 seeds, 576 sessions, 70.5% deal rate
- NEW findings: Demand elasticity 0.275, supply elasticity 0.035, extreme price stickiness, welfare tracks fundamentals (accounting identity), asymmetric incidence

### Experiment B (Anchoring)
- NOT re-run in free-language phase
- Keep in thesis as historical result with gate-on caveat, OR remove entirely
- Recommendation: KEEP but clearly mark as gate-on result, discuss confound

## Revision Strategy

### Option A: Replace old results entirely with new
- Pros: Clean, coherent narrative
- Cons: Loses the gate-on vs gate-off comparison; experiment B disappears

### Option B: Present both as gate-on vs gate-off comparison (RECOMMENDED)
- Frame as: "Phase 1 (gate-on, structured agents) → Phase 2 (gate-off, free-language)"
- The comparison itself IS a finding: gate masks deadline effects, gate drives settlements
- Experiment B stays as gate-on-only result with honest confound discussion

### Option C: Present only new, mention old as preliminary
- Quick to write but wastes valid old data

## RECOMMENDED: Option B — Two-Phase Narrative

### Structure for results.tex:
1. Sanity checks (updated for new pipeline: 100% parse, 0% retry, 0 overrides)
2. Micro-level results
   - Exp A: NEW data primary, old data as comparison point
   - Exp B: OLD data only (gate-on), with confound discussion
   - Exp C: NEW data primary (this is the breakthrough — deadline effect NOW visible)
3. Macro-level results
   - Exp D: NEW data (3 seeds now)
   - Exp E: NEW data (3 seeds now)
   - Exp I: NEW data with surplus analysis
   - Exp H: NEW data
4. Cross-experiment synthesis (rewrite with new patterns)

## Key Tables Needed

1. Pipeline comparison table (old vs new: model, gate, agent type, sessions)
2. Exp A: Concession trajectories by round (rule_based vs llm_free_language)
3. Exp C: Deadline outcomes (6/12/20 rounds) with deal rate, timing, price
4. Exp D: Tick stats (mean price, std, liquidity over 10 ticks)
5. Exp H: Mechanism comparison (random vs surplus_max)
6. Exp I: Supply-demand surplus decomposition
7. Exp E: Shock DiD analysis
8. Summary table: all experiments, deal rate, key finding, pattern strength

## Key Figures Needed (optional but recommended)

1. Concession curves (buyer + seller price by round, rule_based vs LLM)
2. Deadline deal timing histogram (6 vs 12 vs 20 rounds)
3. Market dynamics price time series (3 seeds)
4. Supply-demand surplus bar chart

## Section-by-Section Update Plan

### experiments.tex
- Update common setup: model → Qwen2.5-14B, gate → disabled, agent → llm_free_language
- Add "Two-Phase Design" subsection explaining gate-on → gate-off transition
- Update session counts and seed info
- Keep experiment B description but note it was not re-run gate-off

### results.tex (HEAVIEST LIFT)
- Complete rewrite of sanity checks
- Complete rewrite of Exp A, C results with new data
- Major update to Exp D, E, H, I with new data
- Exp B: minor edit to mark as gate-on-only
- New cross-experiment synthesis with economic patterns

### discussion.tex
- Add price stickiness as central finding
- Add surplus analysis insight (welfare = accounting identity, price = behavioral)
- Update micro-macro tension with new evidence
- Revise limitations (gate confound now RESOLVED for most experiments)

### intro.tex
- Update session count (2,171 + old sessions)
- Update contribution claims (gate-off results now available)
- Tone down gate confound concern (partially resolved)

### abstract.tex
- Update last (after body is stable)

### conclusion.tex
- Update future work (gate ablation partially done; focus on remaining gaps)

## Writing Style (per AgenticPay reference)

- Bold finding headers (like AgenticPay's "Proprietary Models Dominate...")
- Tables with clear column headers and condition comparisons
- Concise paragraphs: finding → evidence → interpretation → caveat
- Cross-references between related findings
- Honest about limitations inline, not just in limitations section
