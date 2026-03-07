"""Prompt templates for LLM negotiation agents.

Structured for research-grade interpretability: each prompt explicitly
specifies the negotiation protocol, private constraints, objective
function, time pressure, and output schema.

All prompt builders accept an :class:`AgentContext` and an optional
:class:`PromptConfig` to control which components are included.

Qwen-specific additions (Req 4)
--------------------------------
* ``JSON_GUARD`` — mandatory JSON-only instruction prepended to every
  prompt.  Explicitly tells the model to choose ``"accept"`` when the
  offer meets its requirements.
* :func:`_accept_condition_block` — inserts a concise, number-filled
  ACCEPT CONDITION section so the model can see its threshold, the
  current offer, and the computed utility in one glance.
* ``_FEW_SHOT_EXAMPLES`` — two concrete JSON examples (one ACCEPT, one
  COUNTER) appended after the schema so the model sees correct
  formatting immediately before generating its response.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.core.types import AgentContext, AgentRole, NegotiationTurn
from src.llm.schemas import SCHEMA_DESCRIPTION

if TYPE_CHECKING:
    from src.core.config import PromptConfig


# ═══════════════════════════════════════════════════════════════════════
#  JSON-only guard (prepended before SYSTEM_PROMPT in every prompt)
# ═══════════════════════════════════════════════════════════════════════

JSON_GUARD = (
    "IMPORTANT: You must output VALID JSON ONLY — no extra text, no "
    'markdown. Choose action from: "accept", "counter", "reject". '
    "If the opponent's offer meets your minimum price requirement, "
    'you MUST choose action "accept".'
)


# ═══════════════════════════════════════════════════════════════════════
#  System prompt (shared across all LLM agent types)
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are an autonomous economic agent in a controlled negotiation "
    "experiment. You participate in a bilateral alternating-offers "
    "bargaining protocol. Your objective is to maximise your own "
    "economic surplus while reaching an agreement before the deadline. "
    "You must follow the protocol precisely and respond ONLY with a "
    "JSON object—no extra text, no markdown, no explanation outside "
    "the JSON."
)


# ═══════════════════════════════════════════════════════════════════════
#  Few-shot examples (appended after schema, before final REMINDER)
# ═══════════════════════════════════════════════════════════════════════

_FEW_SHOT_EXAMPLES = """\
EXAMPLES OF CORRECT RESPONSES:
Example 1 – offer within your limits → you MUST accept:
  {"action": "accept", "offer_price": null, "message_public": "Deal!", "rationale_private": "Offer $85 <= my limit $100. Surplus=$15. Accepting."}

Example 2 – offer outside your limits → counter with a new price:
  {"action": "counter", "offer_price": 95, "message_public": "I can offer $95.", "rationale_private": "Offer $120 > my limit $100. Countering at $95."}"""


# ═══════════════════════════════════════════════════════════════════════
#  History helpers
# ═══════════════════════════════════════════════════════════════════════

def summarise_history(history: list[NegotiationTurn], k: int = 6) -> str:
    """Deterministic, non-LLM transcript compressor.

    Returns a compact bullet list of the last *k* turns::

        - R0 buyer OFFER $60.00
        - R1 seller COUNTER $95.00
        ...

    This is intentionally terse to save tokens while preserving the
    price trajectory that drives concession analysis.
    """
    if not history:
        return "(no moves yet)"
    recent = history[-k:] if k else history
    lines: list[str] = []
    for t in recent:
        price_part = f" ${t.action.offer_price:.2f}" if t.action.offer_price is not None else ""
        lines.append(
            f"- R{t.round_number} {t.agent_role.value} "
            f"{t.action.action.value.upper()}{price_part}"
        )
    prefix = ""
    if k and len(history) > k:
        prefix = f"(...{len(history) - k} earlier turns omitted)\n"
    return prefix + "\n".join(lines)


def _format_history(history: list[NegotiationTurn]) -> str:
    """Legacy verbose history formatter (kept for backward compat)."""
    if not history:
        return "  (none yet)"
    lines: list[str] = []
    for turn in history:
        role = turn.agent_role.value
        act = turn.action.action.value
        price = turn.action.offer_price
        msg = turn.action.message_public
        if price is not None:
            lines.append(
                f"  Round {turn.round_number}: {role} {act} "
                f"at ${price:.2f} – \"{msg}\""
            )
        else:
            lines.append(f"  Round {turn.round_number}: {role} {act} – \"{msg}\"")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Accept condition block (Req 4c — computed utility shown to model)
# ═══════════════════════════════════════════════════════════════════════

def _accept_condition_block(ctx: AgentContext) -> str:
    """Return a concise ACCEPT CONDITION section for the current offer.

    Shows the agent's acceptance threshold, the opponent's last offer,
    and the computed utility so the model can make an informed decision
    without needing to do arithmetic itself.  Returns ``""`` when no
    offer has been made yet (round 0).
    """
    if ctx.last_offer is None:
        return ""

    last = ctx.last_offer
    is_buyer = ctx.role == AgentRole.BUYER

    if is_buyer:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        utility = ctx.reservation_price - last
        feasible = last <= cap
        decision = (
            f'→ ${last:.2f} <= ${cap:.2f}: output action="accept" NOW.'
            if feasible
            else f"→ ${last:.2f} > ${cap:.2f}: do NOT accept. Counter lower."
        )
        return (
            f"ACCEPT CONDITION:\n"
            f"  Your max price (threshold): ${cap:.2f}\n"
            f"  Opponent's last offer:      ${last:.2f}\n"
            f"  Your utility if you accept: ${utility:.2f}  "
            f"(= value ${ctx.reservation_price:.2f} - offer ${last:.2f})\n"
            f"  {decision}"
        )
    else:
        cost = ctx.reservation_price
        utility = last - cost
        feasible = last >= cost
        decision = (
            f'→ ${last:.2f} >= ${cost:.2f}: output action="accept" NOW.'
            if feasible
            else f"→ ${last:.2f} < ${cost:.2f}: do NOT accept. Counter higher."
        )
        return (
            f"ACCEPT CONDITION:\n"
            f"  Your min price (threshold): ${cost:.2f}\n"
            f"  Opponent's last offer:      ${last:.2f}\n"
            f"  Your utility if you accept: ${utility:.2f}  "
            f"(= offer ${last:.2f} - cost ${cost:.2f})\n"
            f"  {decision}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Constraint blocks
# ═══════════════════════════════════════════════════════════════════════

def _buyer_constraints(ctx: AgentContext) -> str:
    cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
    opening = round(cap * 0.5, 2)
    step = round(cap * 0.08, 2)
    return (
        f"Your MAXIMUM price (hard ceiling): ${cap:.2f}\n"
        f"NEVER offer above ${cap:.2f}.\n"
        "\n"
        "ACTION RULES (follow these exactly):\n"
        f"- Round 1: use \"offer\" with price around ${opening:.2f}.\n"
        f"- Later rounds: use \"counter\" and increase your price by ~${step:.2f} each time.\n"
        f"- If the seller's last offer is at or below ${cap:.2f}: use \"accept\" (offer_price: null).\n"
        "- NEVER use \"reject\". Always \"counter\" with a higher price instead.\n"
        "- No deal = zero surplus. Getting a deal is always better than no deal."
    )


def _seller_constraints(ctx: AgentContext) -> str:
    cost = ctx.reservation_price
    margin = ctx.target_margin or 0.15
    opening = round(cost * (1 + 2 * margin), 2)
    step = round(cost * 0.08, 2)
    return (
        f"Your MINIMUM price (hard floor): ${cost:.2f}\n"
        f"NEVER accept or offer below ${cost:.2f}.\n"
        "\n"
        "ACTION RULES (follow these exactly):\n"
        f"- Round 1: use \"offer\" with price around ${opening:.2f}.\n"
        f"- Later rounds: use \"counter\" and decrease your price by ~${step:.2f} each time.\n"
        f"- If the buyer's last offer is at or above ${cost:.2f}: use \"accept\" (offer_price: null).\n"
        "- NEVER use \"reject\". Always \"counter\" with a lower price instead.\n"
        "- No deal = zero surplus. Getting a deal is always better than no deal."
    )


# ═══════════════════════════════════════════════════════════════════════
#  Objective function block
# ═══════════════════════════════════════════════════════════════════════

def _buyer_objective(ctx: AgentContext) -> str:
    cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
    return (
        "Objective: maximise buyer_surplus = value - deal_price, "
        f"where deal_price ∈ [seller_offer, {cap:.2f}].\n"
        "If no deal is reached, your surplus is 0."
    )


def _seller_objective(ctx: AgentContext) -> str:
    return (
        "Objective: maximise seller_surplus = deal_price - cost, "
        f"where deal_price >= {ctx.reservation_price:.2f}.\n"
        "If no deal is reached, your surplus is 0."
    )


# ═══════════════════════════════════════════════════════════════════════
#  Deadline salience block
# ═══════════════════════════════════════════════════════════════════════

def _deadline_salience(ctx: AgentContext) -> str:
    """Inject deadline-pressure language when time is running out."""
    remaining = ctx.max_rounds - ctx.round_number - 1
    total = ctx.max_rounds
    is_buyer = ctx.role == AgentRole.BUYER
    if remaining <= 0:
        if is_buyer:
            cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
            return (
                "*** FINAL ROUND — You MUST set action to \"accept\" if the "
                f"seller's last offer is at or below ${cap:.2f}. "
                "Otherwise the negotiation fails and you get NOTHING. ***"
            )
        else:
            cost = ctx.reservation_price
            return (
                "*** FINAL ROUND — You MUST set action to \"accept\" if the "
                f"buyer's last offer is at or above ${cost:.2f}. "
                "Otherwise the negotiation fails and you get NOTHING. ***"
            )
    if remaining <= 2:
        return (
            f"WARNING: Only {remaining} round(s) left out of {total}. "
            "You should accept any offer within your limits NOW. "
            "No deal = zero surplus for both sides."
        )
    if remaining <= total // 3:
        return (
            f"Note: {remaining} rounds remaining out of {total}. "
            "Start making larger concessions to reach a deal."
        )
    return ""


# ═══════════════════════════════════════════════════════════════════════
#  Tone hint
# ═══════════════════════════════════════════════════════════════════════

_TONE_HINTS = {
    "neutral": "",
    "firm": "Adopt a confident, assertive tone in your public message.",
    "friendly": "Be polite and collaborative in your public message.",
}


# ═══════════════════════════════════════════════════════════════════════
#  Core prompt builders
# ═══════════════════════════════════════════════════════════════════════

def build_reactive_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a single-shot reactive prompt.

    The prompt includes (in order):
    1. System preamble (protocol description)
    2. Role + private constraints
    3. Objective equation (optional via config)
    4. Round / deadline info + salience warning
    5. Transcript summary or full history
    6. Schema reminder
    7. Instruction to respond with JSON only

    Args:
        ctx: Agent context with item, role, round, history, constraints.
        prompt_cfg: Optional prompt configuration. Defaults are applied
            when *None*.

    Returns:
        Complete prompt string ready for LLM consumption.
    """
    # defaults
    include_obj = True
    include_deadline = True
    include_summary = True
    history_k = 6
    tone = "neutral"
    if prompt_cfg is not None:
        include_obj = prompt_cfg.include_objective_equations
        include_deadline = prompt_cfg.include_deadline_salience
        include_summary = prompt_cfg.include_history_summary
        history_k = prompt_cfg.history_k
        tone = prompt_cfg.message_tone

    role = ctx.role.value
    is_buyer = ctx.role == AgentRole.BUYER
    constraints = _buyer_constraints(ctx) if is_buyer else _seller_constraints(ctx)
    remaining = ctx.max_rounds - ctx.round_number - 1
    last = (
        f"${ctx.last_offer:.2f}"
        if ctx.last_offer is not None
        else "None (you go first)"
    )

    parts: list[str] = []

    # 1. JSON guard (Qwen-specific) + system + role
    parts.append(JSON_GUARD)
    parts.append("")
    parts.append(SYSTEM_PROMPT)
    parts.append("")
    parts.append(
        f"Role: {role.upper()} negotiating for \"{ctx.item.name}\" "
        f"(reference price ${ctx.item.reference_price:.2f})."
    )

    # 2. Constraints
    parts.append("")
    parts.append(constraints)

    # 3. Objective
    if include_obj:
        parts.append("")
        parts.append(
            _buyer_objective(ctx) if is_buyer else _seller_objective(ctx)
        )

    # 4. Round info + deadline
    parts.append("")
    parts.append(
        f"Round {ctx.round_number + 1} of {ctx.max_rounds} "
        f"({remaining} remaining after this)."
    )
    parts.append(f"Opponent's last offer: {last}")
    if include_deadline:
        sal = _deadline_salience(ctx)
        if sal:
            parts.append("")
            parts.append(sal)

    # 4b. Accept condition (computed utility — Req 4c)
    accept_cond = _accept_condition_block(ctx)
    if accept_cond:
        parts.append("")
        parts.append(accept_cond)

    # 5. History
    parts.append("")
    if include_summary:
        parts.append("Transcript (recent):")
        parts.append(summarise_history(ctx.history, k=history_k))
    else:
        parts.append("History:")
        parts.append(_format_history(ctx.history))

    # 6. Tone
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    # 7. Schema + few-shot examples (Req 4b) + final instruction
    parts.append("")
    parts.append(SCHEMA_DESCRIPTION)
    parts.append("")
    parts.append(_FEW_SHOT_EXAMPLES)
    parts.append("")
    parts.append(
        "REMINDER: NEVER use \"reject\". Use \"counter\" with a new price, "
        "or \"accept\" if the opponent's offer is within your limits. "
        "Change your price each round. Respond with ONLY the JSON object."
    )

    return "\n".join(parts)


def build_deliberative_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a deliberative prompt with structured reasoning instructions.

    Same structure as :func:`build_reactive_prompt` but appends explicit
    reasoning steps that the agent must include in ``rationale_private``:

    1. BELIEFS — estimate opponent's reservation price
    2. TARGET  — ideal price given remaining rounds
    3. STRATEGY — concede / hold / accept / reject
    4. ACTION  — concrete action + price

    Args:
        ctx: Agent context.
        prompt_cfg: Optional prompt configuration.

    Returns:
        Complete deliberative prompt string.
    """
    # defaults
    include_obj = True
    include_deadline = True
    include_summary = True
    history_k = 6
    tone = "neutral"
    if prompt_cfg is not None:
        include_obj = prompt_cfg.include_objective_equations
        include_deadline = prompt_cfg.include_deadline_salience
        include_summary = prompt_cfg.include_history_summary
        history_k = prompt_cfg.history_k
        tone = prompt_cfg.message_tone

    role = ctx.role.value
    is_buyer = ctx.role == AgentRole.BUYER
    constraints = _buyer_constraints(ctx) if is_buyer else _seller_constraints(ctx)
    remaining = ctx.max_rounds - ctx.round_number - 1
    last = (
        f"${ctx.last_offer:.2f}"
        if ctx.last_offer is not None
        else "None (you go first)"
    )

    parts: list[str] = []

    # 1. JSON guard (Qwen-specific) + system + role
    parts.append(JSON_GUARD)
    parts.append("")
    parts.append(SYSTEM_PROMPT)
    parts.append("")
    parts.append(
        f"Role: {role.upper()} negotiating for \"{ctx.item.name}\" "
        f"(reference price ${ctx.item.reference_price:.2f})."
    )

    # 2. Constraints
    parts.append("")
    parts.append(constraints)

    # 3. Objective
    if include_obj:
        parts.append("")
        parts.append(
            _buyer_objective(ctx) if is_buyer else _seller_objective(ctx)
        )

    # 4. Round info + deadline
    parts.append("")
    parts.append(
        f"Round {ctx.round_number + 1} of {ctx.max_rounds} "
        f"({remaining} remaining after this)."
    )
    parts.append(f"Opponent's last offer: {last}")
    if include_deadline:
        sal = _deadline_salience(ctx)
        if sal:
            parts.append("")
            parts.append(sal)

    # 4b. Accept condition (computed utility — Req 4c)
    accept_cond = _accept_condition_block(ctx)
    if accept_cond:
        parts.append("")
        parts.append(accept_cond)

    # 5. History
    parts.append("")
    if include_summary:
        parts.append("Transcript (recent):")
        parts.append(summarise_history(ctx.history, k=history_k))
    else:
        parts.append("History:")
        parts.append(_format_history(ctx.history))

    # 6. Reasoning steps
    parts.append("")
    parts.append(
        "Before deciding, reason through these steps INSIDE your "
        "rationale_private field:"
    )
    parts.append("1. BELIEFS – What is the opponent's likely reservation price?")
    parts.append("2. TARGET  – What price would be ideal given remaining rounds?")
    parts.append("3. STRATEGY – Concede, hold firm, accept, or reject?")
    parts.append("4. ACTION  – Specific action and price.")

    # 7. Tone
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    # 8. Schema + few-shot examples (Req 4b) + final instruction
    parts.append("")
    parts.append(SCHEMA_DESCRIPTION)
    parts.append("")
    parts.append(_FEW_SHOT_EXAMPLES)
    parts.append("")
    parts.append(
        "REMINDER: NEVER use \"reject\". Use \"counter\" with a new price, "
        "or \"accept\" if the opponent's offer is within your limits. "
        "Change your price each round. Respond with ONLY the JSON object. "
        "Put ALL reasoning inside rationale_private."
    )

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
#  Memory context (unchanged API)
# ═══════════════════════════════════════════════════════════════════════

def build_memory_context(memories: list[dict]) -> str:
    """Format past negotiation memories for prompt injection."""
    if not memories:
        return ""
    lines = ["Your past negotiation experiences (most relevant first):"]
    for i, mem in enumerate(memories, 1):
        outcome = "DEAL" if mem.get("deal_made") else "NO DEAL"
        price_str = f" at ${mem['deal_price']:.2f}" if mem.get("deal_price") else ""
        lines.append(
            f"  {i}. Item: {mem.get('item_name', '?')} | "
            f"Outcome: {outcome}{price_str} | "
            f"Rounds: {mem.get('rounds', '?')} | "
            f"Opponent style: {mem.get('opponent_style', 'unknown')}"
        )
    lines.append("")
    return "\n".join(lines)
