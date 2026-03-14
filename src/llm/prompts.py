"""Prompt templates for LLM negotiation agents.

Designed for weak local models (3B parameter class). Prompts are short,
pattern-based, and avoid hard-coded concession schedules. Behaviour is
guided through role constraints, accept hints, and compact examples.

All prompt builders accept an :class:`AgentContext` and an optional
:class:`PromptConfig` to control which components are included.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.core.types import AgentContext, AgentRole, NegotiationTurn
from src.llm.schemas import SCHEMA_DESCRIPTION

if TYPE_CHECKING:
    from src.core.config import PromptConfig


# ═══════════════════════════════════════════════════════════════════════
#  System instruction (shared, kept short)
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are a negotiation agent. Respond with ONLY a JSON object. "
    "No markdown, no explanation outside the JSON."
)


# ═══════════════════════════════════════════════════════════════════════
#  Few-shot examples (compact, one accept + one counter)
# ═══════════════════════════════════════════════════════════════════════

_FEW_SHOT_EXAMPLES_BUYER = """\
EXAMPLES (buyer):
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 85, "message_public": "How about $85?", "rationale_private": "I want a lower price. My counter must be BELOW the opponent's offer."}"""

_FEW_SHOT_EXAMPLES_SELLER = """\
EXAMPLES (seller):
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is above my minimum."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "I want a higher price. My counter must be ABOVE the opponent's offer."}"""


# ═══════════════════════════════════════════════════════════════════════
#  History helper
# ═══════════════════════════════════════════════════════════════════════

def summarise_history(history: list[NegotiationTurn], k: int = 6) -> str:
    """Compact bullet list of the last *k* turns."""
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
#  Accept / counter hint (concise decision guidance)
# ═══════════════════════════════════════════════════════════════════════

def _decision_hint(ctx: AgentContext) -> str:
    """Directional hint: tells model when to accept vs counter, and counter direction."""
    if ctx.last_offer is None:
        return "No offer yet. Make an opening offer."

    last = ctx.last_offer
    if ctx.role == AgentRole.BUYER:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        if last <= cap:
            return (
                f"Opponent offers ${last:.2f}. Your limit is ${cap:.2f}. "
                f"This offer is WITHIN your limit and you would gain "
                f"${cap - last:.2f} surplus. Accept if the price is reasonable "
                f"or time is short. If the opponent's offer is already very "
                f"close to the price you would counter with, prefer accepting "
                f"over making a tiny counteroffer. If you counter, you MUST "
                f"counter BELOW ${last:.2f}. NEVER counter above the opponent's price."
            )
        else:
            return (
                f"Opponent offers ${last:.2f}. Your limit is ${cap:.2f}. "
                f"This offer EXCEEDS your limit — you must counter below ${cap:.2f}."
            )
    else:
        cost = ctx.reservation_price
        if last >= cost:
            return (
                f"Opponent offers ${last:.2f}. Your minimum is ${cost:.2f}. "
                f"This offer is ABOVE your minimum and you would gain "
                f"${last - cost:.2f} surplus. Accept if the price is reasonable "
                f"or time is short. If the opponent's offer is already very "
                f"close to the price you would counter with, prefer accepting "
                f"over making a tiny counteroffer. If you counter, you MUST "
                f"counter ABOVE ${last:.2f}. NEVER counter below the opponent's price."
            )
        else:
            return (
                f"Opponent offers ${last:.2f}. Your minimum is ${cost:.2f}. "
                f"This offer is BELOW your minimum — you must counter above ${cost:.2f}."
            )


# ═══════════════════════════════════════════════════════════════════════
#  Deadline hint (compact)
# ═══════════════════════════════════════════════════════════════════════

def _deadline_hint(ctx: AgentContext) -> str:
    """Short deadline pressure when time is running out."""
    remaining = ctx.max_rounds - ctx.round_number - 1
    if remaining <= 0:
        return "FINAL ROUND. Accept any offer within your limits or get NOTHING."
    if remaining <= 2:
        return f"WARNING: Only {remaining} round(s) left. No deal = zero surplus."
    if remaining <= ctx.max_rounds // 3:
        return f"{remaining} rounds left. Consider conceding to reach a deal."
    return ""


# ═══════════════════════════════════════════════════════════════════════
#  Tone and communication strategy (unchanged API)
# ═══════════════════════════════════════════════════════════════════════

_TONE_HINTS = {
    "neutral": "",
    "firm": "Adopt a confident, assertive tone in your public message.",
    "friendly": "Be polite and collaborative in your public message.",
}

_COMMUNICATION_STRATEGIES = {
    "neutral": "",
    "assertive": (
        "COMMUNICATION STRATEGY: Be assertive and firm in your public "
        "message. State your position clearly. Emphasise your constraints "
        "and signal that you will not concede easily. Do not reveal "
        "weakness or eagerness to settle."
    ),
    "collaborative": (
        "COMMUNICATION STRATEGY: Be cooperative and friendly in your "
        "public message. Signal willingness to find a mutually beneficial "
        "outcome. Acknowledge the other party's interests. Suggest "
        "compromises when possible."
    ),
    "strategic": (
        "COMMUNICATION STRATEGY: Craft your public message to maximise "
        "your advantage. You may exaggerate how close you are to your "
        "limit. Do NOT reveal your true constraints or reservation price. "
        "Use the message to influence the opponent's expectations about "
        "what you will accept."
    ),
}


# ═══════════════════════════════════════════════════════════════════════
#  Core prompt builders
# ═══════════════════════════════════════════════════════════════════════

def build_reactive_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a compact single-shot prompt for weak LLMs.

    Structure (kept short for 3B-class models):
    1. System instruction (1 line)
    2. Role + private constraint (2 lines)
    3. Round context + decision hint (2-3 lines)
    4. Deadline pressure (0-1 line)
    5. Transcript (compact)
    6. Tone / communication strategy (optional)
    7. Schema + examples + final reminder
    """
    # ── config defaults ────────────────────────────────────────────────
    include_deadline = True
    include_summary = True
    history_k = 6
    tone = "neutral"
    comm_strategy = "neutral"
    if prompt_cfg is not None:
        include_deadline = prompt_cfg.include_deadline_salience
        include_summary = prompt_cfg.include_history_summary
        history_k = prompt_cfg.history_k
        tone = prompt_cfg.message_tone
        comm_strategy = prompt_cfg.communication_strategy

    is_buyer = ctx.role == AgentRole.BUYER
    remaining = ctx.max_rounds - ctx.round_number - 1

    parts: list[str] = []

    # 1. System
    parts.append(SYSTEM_PROMPT)

    # 2. Role + constraint
    parts.append("")
    if is_buyer:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        parts.append(
            f"You are a BUYER negotiating for \"{ctx.item.name}\". "
            f"Your maximum price is ${cap:.2f}. Never pay more than ${cap:.2f}."
        )
        parts.append("The less you pay, the better your deal. Do not reveal your limit.")
    else:
        cost = ctx.reservation_price
        parts.append(
            f"You are a SELLER negotiating for \"{ctx.item.name}\". "
            f"Your minimum price is ${cost:.2f}. Never sell below ${cost:.2f}."
        )
        parts.append("The more you sell for, the better your deal. Do not reveal your minimum.")

    # 3. Round context + decision hint
    parts.append("")
    parts.append(
        f"Round {ctx.round_number + 1} of {ctx.max_rounds} "
        f"({remaining} remaining)."
    )
    parts.append(_decision_hint(ctx))

    # 4. Deadline
    if include_deadline:
        dl = _deadline_hint(ctx)
        if dl:
            parts.append(dl)

    # 5. History
    parts.append("")
    if include_summary:
        parts.append("History:")
        parts.append(summarise_history(ctx.history, k=history_k))
    else:
        parts.append("History:")
        parts.append(_format_history(ctx.history))

    # 6. Tone / communication strategy
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    comm_hint = _COMMUNICATION_STRATEGIES.get(comm_strategy, "")
    if comm_hint:
        parts.append("")
        parts.append(comm_hint)

    # 7. Schema + examples + reminder
    parts.append("")
    parts.append(SCHEMA_DESCRIPTION)
    parts.append("")
    parts.append(_FEW_SHOT_EXAMPLES_BUYER if is_buyer else _FEW_SHOT_EXAMPLES_SELLER)
    parts.append("")
    parts.append(
        "Output ONLY the JSON object. "
        "Use \"accept\" when the offer is within your limits. "
        "If you counter, your price must be LOWER than the opponent's last offer (buyer) "
        "or HIGHER than the opponent's last offer (seller)."
    )

    return "\n".join(parts)


def build_deliberative_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a compact deliberative prompt with a short reasoning scaffold.

    Same structure as :func:`build_reactive_prompt` but adds a brief
    reasoning instruction for the ``rationale_private`` field.
    """
    # ── config defaults ────────────────────────────────────────────────
    include_deadline = True
    include_summary = True
    history_k = 6
    tone = "neutral"
    comm_strategy = "neutral"
    if prompt_cfg is not None:
        include_deadline = prompt_cfg.include_deadline_salience
        include_summary = prompt_cfg.include_history_summary
        history_k = prompt_cfg.history_k
        tone = prompt_cfg.message_tone
        comm_strategy = prompt_cfg.communication_strategy

    is_buyer = ctx.role == AgentRole.BUYER
    remaining = ctx.max_rounds - ctx.round_number - 1

    parts: list[str] = []

    # 1. System
    parts.append(SYSTEM_PROMPT)

    # 2. Role + constraint
    parts.append("")
    if is_buyer:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        parts.append(
            f"You are a BUYER negotiating for \"{ctx.item.name}\". "
            f"Your maximum price is ${cap:.2f}. Never pay more than ${cap:.2f}."
        )
        parts.append("The less you pay, the better your deal. Do not reveal your limit.")
    else:
        cost = ctx.reservation_price
        parts.append(
            f"You are a SELLER negotiating for \"{ctx.item.name}\". "
            f"Your minimum price is ${cost:.2f}. Never sell below ${cost:.2f}."
        )
        parts.append("The more you sell for, the better your deal. Do not reveal your minimum.")

    # 3. Round context + decision hint
    parts.append("")
    parts.append(
        f"Round {ctx.round_number + 1} of {ctx.max_rounds} "
        f"({remaining} remaining)."
    )
    parts.append(_decision_hint(ctx))

    # 4. Deadline
    if include_deadline:
        dl = _deadline_hint(ctx)
        if dl:
            parts.append(dl)

    # 5. History
    parts.append("")
    if include_summary:
        parts.append("History:")
        parts.append(summarise_history(ctx.history, k=history_k))
    else:
        parts.append("History:")
        parts.append(_format_history(ctx.history))

    # 6. Short reasoning scaffold
    parts.append("")
    parts.append(
        "In rationale_private, briefly reason: "
        "(1) Is the offer acceptable? "
        "(2) If not, what price should I counter with?"
    )

    # 7. Tone / communication strategy
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    comm_hint = _COMMUNICATION_STRATEGIES.get(comm_strategy, "")
    if comm_hint:
        parts.append("")
        parts.append(comm_hint)

    # 8. Schema + examples + reminder
    parts.append("")
    parts.append(SCHEMA_DESCRIPTION)
    parts.append("")
    parts.append(_FEW_SHOT_EXAMPLES_BUYER if is_buyer else _FEW_SHOT_EXAMPLES_SELLER)
    parts.append("")
    parts.append(
        "Output ONLY the JSON object. "
        "Use \"accept\" when the offer is within your limits. "
        "If you counter, your price must be LOWER than the opponent's last offer (buyer) "
        "or HIGHER than the opponent's last offer (seller). "
        "Put ALL reasoning inside rationale_private."
    )

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
#  Free-language prompt builders (AgenticPay-style)
# ═══════════════════════════════════════════════════════════════════════

def _format_free_language_history(history: list[NegotiationTurn]) -> str:
    """Format conversation history as full natural-language transcript."""
    if not history:
        return "(no conversation yet)"
    lines: list[str] = []
    for turn in history:
        role = turn.agent_role.value.upper()
        msg = turn.action.message_public
        lines.append(f"[Round {turn.round_number + 1}] {role}: {msg}")
    return "\n".join(lines)


def _free_language_decision_hint(ctx: AgentContext) -> str:
    """Dynamic per-turn feasibility signal for free-language prompts.

    Mirrors :func:`_decision_hint` but uses MAKE_DEAL terminology and
    natural-language phrasing suited to the free-language pipeline.
    """
    if ctx.last_offer is None:
        return ""

    last = ctx.last_offer
    if ctx.role == AgentRole.BUYER:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        if last <= cap:
            return (
                f"CURRENT STATUS: The seller's last price is ${last:.2f}. "
                f"Your maximum is ${cap:.2f}. This price is WITHIN your limit "
                f"and you would gain ${cap - last:.2f} surplus. "
                f"Consider accepting with MAKE_DEAL if it is close to "
                f"what you would counter with."
            )
        else:
            return (
                f"CURRENT STATUS: The seller's last price is ${last:.2f}. "
                f"Your maximum is ${cap:.2f}. This price EXCEEDS your limit — "
                f"you must counter below ${cap:.2f}."
            )
    else:
        cost = ctx.reservation_price
        if last >= cost:
            return (
                f"CURRENT STATUS: The buyer's last offer is ${last:.2f}. "
                f"Your minimum is ${cost:.2f}. This offer is ABOVE your minimum "
                f"and you would gain ${last - cost:.2f} surplus. "
                f"Consider accepting with MAKE_DEAL if it is close to "
                f"what you would counter with."
            )
        else:
            return (
                f"CURRENT STATUS: The buyer's last offer is ${last:.2f}. "
                f"Your minimum is ${cost:.2f}. This offer is BELOW your minimum — "
                f"you must counter above ${cost:.2f}."
            )


def build_free_language_buyer_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a free-language buyer prompt (AgenticPay-style).

    The agent responds in natural language with an embedded price tag
    ``### BUYER_PRICE($X) ###`` and a ``MAKE_DEAL`` keyword for acceptance.
    """
    include_deadline = True
    comm_strategy = "neutral"
    tone = "neutral"
    if prompt_cfg is not None:
        include_deadline = prompt_cfg.include_deadline_salience
        comm_strategy = prompt_cfg.communication_strategy
        tone = prompt_cfg.message_tone

    cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
    ref = ctx.item.reference_price
    remaining = ctx.max_rounds - ctx.round_number - 1

    parts: list[str] = []

    # Role description
    parts.append(
        f"You are Buyer, a buyer looking for a good deal on \"{ctx.item.name}\". "
        "You are polite, strategic, and want to get the best price within your budget."
    )

    # Product info
    parts.append("")
    if ref > 0:
        parts.append(f"Product: {ctx.item.name} (market reference price: ${ref:.2f})")
    else:
        parts.append(f"Product: {ctx.item.name}")

    # State
    parts.append("")
    parts.append(f"Round {ctx.round_number + 1} of {ctx.max_rounds} ({remaining} remaining).")

    # Conversation history
    parts.append("")
    parts.append("Conversation History:")
    parts.append(_format_free_language_history(ctx.history))

    # Decision hint (dynamic per-turn feasibility signal)
    hint = _free_language_decision_hint(ctx)
    if hint:
        parts.append("")
        parts.append(hint)

    # Strategy instruction
    parts.append("")
    parts.append("NEGOTIATION STRATEGY:")
    parts.append("- As a buyer, your goal is to pay as LITTLE as possible.")
    parts.append("- Start with a LOW opening offer and gradually increase if needed.")
    parts.append(
        "- Each counter-offer you make should be HIGHER than your previous offer "
        "(concede upward toward agreement)."
    )
    parts.append("- NEVER offer MORE than the seller's last asking price. "
                 "If the seller asks $90, your offer must be below $90.")
    parts.append("- If the opponent's offer is already very close to the price you would "
                 "counter with, prefer accepting with MAKE_DEAL over making a tiny counteroffer.")
    parts.append("- Never offer more than you need to. Make small concessions.")

    # Respond naturally instruction
    parts.append("")
    parts.append("Please respond naturally as Buyer would. Be strategic but realistic in your negotiation.")

    # Core instructions
    parts.append("")
    parts.append("IMPORTANT:")
    parts.append(f"- Your maximum acceptable price is ${cap:.2f} (confidential, do not reveal).")

    # Deadline pressure
    if include_deadline:
        dl = _deadline_hint(ctx)
        if dl:
            parts.append(f"- {dl}")

    # Price format instruction
    parts.append(
        "- CRITICAL: In each turn, you MUST make exactly ONE price offer "
        "using the format:\n  ### BUYER_PRICE($X) ###"
    )
    parts.append('- Example: "I can offer ### BUYER_PRICE($50.00) ### for this."')
    parts.append('- Example: "How about ### BUYER_PRICE($65.00) ###?"')
    parts.append(
        "- This specific format is required for the system to correctly "
        "extract your offer price."
    )
    parts.append("- NEVER reveal your maximum acceptable price to the seller.")
    parts.append("- Keep communication short (150 words or less), clear, and focused on negotiation.")

    # Deal acceptance instruction
    parts.append("")
    parts.append("DEAL AGREEMENT INSTRUCTION:")
    parts.append("- MAKE_DEAL means you ACCEPT the seller's last price exactly as offered.")
    parts.append("- When you say MAKE_DEAL, do NOT include a new price tag. Just accept.")
    parts.append("- If you want a different price, make a counter-offer WITHOUT saying MAKE_DEAL.")
    parts.append('- Example acceptance: "I accept your offer of $88.75. MAKE_DEAL"')
    parts.append('- Example counter: "How about ### BUYER_PRICE($85.00) ###?"')

    # Tone / communication strategy
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    comm_hint = _COMMUNICATION_STRATEGIES.get(comm_strategy, "")
    if comm_hint:
        parts.append("")
        parts.append(comm_hint)

    parts.append("")
    parts.append("Now, respond as Buyer:")

    return "\n".join(parts)


def build_free_language_seller_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Build a free-language seller prompt (AgenticPay-style).

    The agent responds in natural language with an embedded price tag
    ``### SELLER_PRICE($X) ###`` and a ``MAKE_DEAL`` keyword for acceptance.
    """
    include_deadline = True
    comm_strategy = "neutral"
    tone = "neutral"
    if prompt_cfg is not None:
        include_deadline = prompt_cfg.include_deadline_salience
        comm_strategy = prompt_cfg.communication_strategy
        tone = prompt_cfg.message_tone

    cost = ctx.reservation_price
    margin = ctx.target_margin or 0.15
    ref = ctx.item.reference_price
    # Initial asking price: well above reference to leave room for negotiation.
    # When no anchor (ref <= 0), derive from cost instead.
    if ref > 0:
        initial_price = ref * (1 + margin + 0.3)
    else:
        initial_price = cost * (1 + 2 * margin)
    remaining = ctx.max_rounds - ctx.round_number - 1

    parts: list[str] = []

    # Role description
    parts.append(
        f"You are Seller, a seller trying to maximize profit on \"{ctx.item.name}\" "
        "while being reasonable. You are professional, friendly, and want to "
        "close a deal that benefits both parties."
    )

    # Product info
    parts.append("")
    if ref > 0:
        parts.append(f"Product: {ctx.item.name} (market reference price: ${ref:.2f})")
    else:
        parts.append(f"Product: {ctx.item.name}")

    # State
    parts.append("")
    parts.append(f"Round {ctx.round_number + 1} of {ctx.max_rounds} ({remaining} remaining).")

    # Conversation history
    parts.append("")
    parts.append("Conversation History:")
    parts.append(_format_free_language_history(ctx.history))

    # Decision hint (dynamic per-turn feasibility signal)
    hint = _free_language_decision_hint(ctx)
    if hint:
        parts.append("")
        parts.append(hint)

    # Strategy instruction
    parts.append("")
    parts.append("NEGOTIATION STRATEGY:")
    parts.append("- As a seller, your goal is to sell for as HIGH a price as possible.")
    parts.append("- Start with a HIGH opening price and gradually lower if needed.")
    parts.append(
        "- Each counter-offer you make should be LOWER than your previous offer "
        "(concede downward toward agreement)."
    )
    parts.append("- NEVER offer LESS than the buyer's last offer. "
                 "If the buyer offers $87, your counter must be above $87.")
    parts.append("- If the opponent's offer is already very close to the price you would "
                 "counter with, prefer accepting with MAKE_DEAL over making a tiny counteroffer.")
    parts.append("- Never drop your price more than you need to. Make small concessions.")

    # Respond naturally instruction
    parts.append("")
    parts.append("Please respond naturally as Seller would. Be strategic but realistic in your negotiation.")

    # Core instructions
    parts.append("")
    parts.append("IMPORTANT REMINDERS:")
    parts.append(f"- Your initial asking price is ${initial_price:.2f}.")
    parts.append(f"- Your minimum acceptable price (confidential) is ${cost:.2f}. Never reveal it.")

    # Deadline pressure
    if include_deadline:
        dl = _deadline_hint(ctx)
        if dl:
            parts.append(f"- {dl}")

    # Price format instruction
    parts.append(
        "- CRITICAL: In each turn, you MUST make exactly ONE price offer "
        "using the format:\n  ### SELLER_PRICE($X) ###"
    )
    parts.append('- Example: "I can offer ### SELLER_PRICE($120.00) ### for this product."')
    parts.append('- Example: "How about ### SELLER_PRICE($95.00) ###?"')
    parts.append(
        "- This specific format is required for the system to correctly "
        "extract your offer price."
    )
    parts.append("- NEVER reveal your minimum acceptable price to the buyer.")
    parts.append("- Keep communication short (150 words or less), professional, and negotiation-focused.")

    # Deal acceptance instruction
    parts.append("")
    parts.append("DEAL AGREEMENT INSTRUCTION:")
    parts.append("- MAKE_DEAL means you ACCEPT the buyer's last price exactly as offered.")
    parts.append("- When you say MAKE_DEAL, do NOT include a new price tag. Just accept.")
    parts.append("- If you want a different price, make a counter-offer WITHOUT saying MAKE_DEAL.")
    parts.append('- Example acceptance: "I accept your offer of $85.00. MAKE_DEAL"')
    parts.append('- Example counter: "How about ### SELLER_PRICE($95.00) ###?"')

    # Tone / communication strategy
    tone_hint = _TONE_HINTS.get(tone, "")
    if tone_hint:
        parts.append("")
        parts.append(tone_hint)

    comm_hint = _COMMUNICATION_STRATEGIES.get(comm_strategy, "")
    if comm_hint:
        parts.append("")
        parts.append(comm_hint)

    parts.append("")
    parts.append("Now, respond as Seller:")

    return "\n".join(parts)


def build_free_language_prompt(
    ctx: AgentContext,
    prompt_cfg: Optional[PromptConfig] = None,
) -> str:
    """Dispatch to role-specific free-language prompt builder."""
    if ctx.role == AgentRole.BUYER:
        return build_free_language_buyer_prompt(ctx, prompt_cfg)
    else:
        return build_free_language_seller_prompt(ctx, prompt_cfg)


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


def build_reputation_context(reputation: dict) -> str:
    """Format opponent reputation data for prompt injection."""
    if not reputation:
        return ""
    oid = reputation.get("opponent_id", "unknown")
    interactions = reputation.get("interactions", 0)
    deal_rate = reputation.get("deal_rate", 0)
    avg_price = reputation.get("avg_deal_price", 0)
    avg_rounds = reputation.get("avg_rounds", 0)
    style = reputation.get("style", "unknown")

    lines = [
        f"OPPONENT HISTORY (you have negotiated with {oid} before):",
        f"  Past interactions: {interactions}",
        f"  Deal rate: {deal_rate:.0%}",
        f"  Average deal price: ${avg_price:.2f}",
        f"  Average rounds to close: {avg_rounds:.1f}",
        f"  Opponent style: {style}",
        "",
        "Use this information to calibrate your strategy.",
        "",
    ]
    return "\n".join(lines)
