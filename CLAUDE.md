# Project Context

This repository contains a Final Year Project on:

LLM-powered multi-agent negotiation simulation.

Agents negotiate prices through alternating-offer bargaining in simulated markets.

Experiments evaluate:

- concession curves
- anchoring effects
- deadline pressure
- market equilibrium
- shock response
- reputation dynamics
- communication strategies
- market mechanisms

# Paper Writing Length
- aim 50-60 pages for the whole paper, plan each section accordingly



The thesis should be revised as a **defensible FYP report grounded in the implemented system and actual experiment evidence**, not as an overstated claim that the project proves economic theorems.

The target framing is:

> This project designs and evaluates a multi-agent LLM negotiation simulator for language-mediated buyer–seller markets, with emphasis on how simulator design, protocol design, and market conditions affect negotiation outcomes and aggregate behavior.

## Thesis file structure

The thesis files are located in `paper/`:

- `paper/main.tex` — root LaTeX file
- `paper/intro.tex`
- `paper/related_work.tex`
- `paper/method.tex`
- `paper/experiments.tex`
- `paper/results.tex`
- `paper/discussion.tex`
- `paper/conclusion.tex`
- `paper/abstract.tex`
- `paper/refs.bib`

The final revision should preserve a coherent LaTeX structure and update section organization, content, and cross-references carefully.

## Available subagents

The repository includes four subagents under `.claude/agents/`:

- `section-architect.md`
- `draft-writer.md`
- `critical-reviewer.md`
- `evidence-latex-auditor.md`

Use them deliberately and efficiently:

### section-architect
Use for:
- mapping current thesis sections to the new target structure
- proposing revised section/subsection organization
- improving chapter flow and transitions
- identifying what content should move, split, merge, or be rewritten

### draft-writer
Use for:
- rewriting thesis sections in formal academic English
- improving clarity, defensibility, and coherence
- producing polished LaTeX-ready prose that matches the project’s actual claims

### critical-reviewer
Use for:
- stress-testing claims
- identifying overclaiming, hidden confounds, vague statements, or weak logic
- checking whether a section is defensible for an examiner
- flagging places where thesis language should be softened

### evidence-latex-auditor
Use for:
- checking whether claims are supported by actual code, outputs, tables, figures, and experiment results
- checking LaTeX consistency, terminology consistency, references, labels, and section linkage
- ensuring no invented evidence, fake robustness, or unsupported causal wording appears

## Non-negotiable revision principles

### 1. Be faithful to the repository
Do not invent:
- experiments that were not run
- ablations that do not exist
- robustness that is not demonstrated
- code architecture that is not in the repo
- result interpretations unsupported by actual outputs

All claims must be grounded in the actual simulator implementation, actual experiment reports, and actual thesis materials.

### 2. Prioritize defensibility over hype
Prefer careful language such as:
- economically interpretable patterns
- directionally consistent behavior
- suggests
- indicates
- under selected simulator settings
- sensitive to protocol design
- within the limits of this simulator

Avoid language such as:
- proves
- confirms economic theory
- faithfully reproduces real markets
- demonstrates true human-like negotiation
- robustly establishes
unless directly supported.

### 3. Central thesis positioning
The report should be framed around two layers:

1. **System contribution**  
   A configurable multi-agent buyer–seller negotiation simulator with private constraints, alternating-offers interaction, action extraction, settlement logic, market-level execution, and economic metrics.

2. **Research/methodological contribution**  
   A study of how simulator and protocol design choices affect observed negotiation outcomes and whether economically meaningful micro- and macro-level patterns emerge.

### 4. Gate design is a central methodological issue
The thesis must clearly distinguish:
- agent private constraints
- pre-LLM feasibility gate
- post-LLM override / action judge
- settlement logic

Do not bury this issue.

The report should explicitly discuss that feasibility enforcement may improve constraint satisfaction while also confounding measurement of raw LLM negotiation capability.

### 5. Micro–macro tension should be treated seriously
A likely core discussion insight is:

> Designs that preserve raw agent behavior may weaken aggregate market regularity, while stronger enforcement can stabilize outcomes but partially replace agent decision-making.

Use this idea where supported by repository evidence.

### 6. Keep the thesis as an FYP, not a top-tier paper imitation
The final report should read like a strong final year project:
- solid system design
- careful literature positioning
- honest experiments
- critical analysis of limitations and confounds
- credible future work

Not like an exaggerated claim of broad scientific proof.

## Target chapter logic

The revised thesis should align as closely as practical to this structure:

1. Introduction
2. Literature Review
3. Problem Formulation
4. Simulator Architecture
5. Methodology and Experimental Design
6. Results
7. Discussion
8. Conclusion
9. Future Work

This does not require renaming every `.tex` file, but the content inside them should map clearly to this logic.

A practical mapping may be:

- `intro.tex` → Introduction
- `related_work.tex` → Literature Review
- `method.tex` → Problem Formulation + Simulator Architecture
- `experiments.tex` → Methodology and Experimental Design
- `results.tex` → Results
- `discussion.tex` → Discussion
- `conclusion.tex` → Conclusion + Future Work
- `abstract.tex` → updated last, after thesis reframing is stable

## Specific content expectations

### Introduction
Must include:
- motivation for interactive LLM-agent negotiation
- why static benchmarks are insufficient
- project problem statement
- research objectives
- contributions
- a restrained and defensible framing

### Literature Review
Must include:
- traditional ABM vs LLM-based simulation
- generative agents / agent architecture ideas where relevant
- LLM negotiation literature
- buyer–seller / market negotiation systems
- a clear research gap tied to simulator design validity and protocol confounds

### Problem Formulation / Simulator Architecture
Must include:
- buyer, seller, item, rounds, offers, actions, outcomes
- private constraints and feasibility
- surplus and welfare definitions if used
- actual simulator pipeline from the codebase
- actual agent variants implemented
- actual enforcement and settlement logic

### Methodology and Experimental Design
Must include:
- experiment families grouped into micro-level and macro-level
- manipulated variables and measured outcomes
- controls and confounds
- gate status, prompt wording, round limits, and seed issues where applicable

### Results
Must begin with sanity checks before higher-level claims.

Organize results into:
- agent validity / action validity
- micro-level findings
- macro-level findings
- sensitivity / ablation / gate-related findings if available

Messy results should be reported honestly and interpreted cautiously.

### Discussion
Must include:
- what the simulator successfully demonstrates
- why some experiments fail or become ambiguous
- simulator-design confounds
- micro–macro tension
- comparison with prior work
- explicit limitations

### Conclusion / Future Work
Must conclude conservatively and recommend:
- fuller gate ablation
- prompt ablation
- more seeds
- stronger baselines
- human comparison
- broader mechanisms

## Required workflow for thesis revision

When revising the thesis, follow this order:

1. Inspect the thesis files and map current content to the target structure.
2. Inspect simulator code, prompts, result folders, and experiment reports before rewriting claims.
3. Produce a concise revision plan before making major changes.
4. Revise section by section.
5. After each major section rewrite, audit it for:
   - overclaiming
   - unsupported evidence
   - terminology inconsistency
   - weak transitions
6. Update abstract only after the main body is stable.
7. Preserve compilability of the LaTeX project.

## Terminology consistency rules

Use terminology consistently across the thesis:
- negotiation session
- buyer / seller agent
- private constraints
- feasibility enforcement
- settlement logic
- action judge
- final price
- buyer surplus
- seller surplus
- welfare
- micro-level experiments
- macro-level experiments

Do not casually switch between inconsistent terms for the same concept.

## Style requirements

Write in:
- formal academic English
- restrained, defensible tone
- code-grounded, evidence-based style
- clear chapter-to-chapter progression

Avoid:
- inflated novelty claims
- vague claims without operational meaning
- unnecessary grand statements
- claiming realism beyond what the simulator supports

## Deliverables expected from Claude Code

When revising the thesis, provide:
1. a revision plan,
2. updated thesis sections/files,
3. a summary of major structural changes,
4. a list of softened or removed claims,
5. a list of weak-evidence areas still needing attention.

## Final instruction

The most important rule is:

**Do not make the thesis sound more impressive by becoming less truthful.**
A careful, honest, well-structured thesis is better than an ambitious but fragile one.
