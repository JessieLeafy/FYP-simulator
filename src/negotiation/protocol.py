"""Alternating-offers negotiation protocol."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    NegotiationResult,
    NegotiationTurn,
    SellerState,
    TerminationReason,
)
from src.negotiation.constraints import validate_action

if TYPE_CHECKING:
    from src.agents.base import BaseAgent
    from src.core.logging import EventLogger


def run_negotiation(
    buyer_agent: BaseAgent,
    seller_agent: BaseAgent,
    item: Item,
    buyer: BuyerState,
    seller: SellerState,
    max_rounds: int = 10,
    min_price: float = 1.0,
    max_price: float = 500.0,
    event_logger: Optional[EventLogger] = None,
    time_step: int = 0,
) -> NegotiationResult:
    """Run a complete alternating-offers negotiation.

    Even rounds → buyer moves; odd rounds → seller moves.
    """
    history: list[NegotiationTurn] = []
    risk_events: list[dict] = []
    last_offer: Optional[float] = None

    for round_num in range(max_rounds):
        # ── select active agent ──────────────────────────────────────────
        if round_num % 2 == 0:
            current_role = AgentRole.BUYER
            current_agent = buyer_agent
            ctx = AgentContext(
                item=item,
                role=AgentRole.BUYER,
                round_number=round_num,
                max_rounds=max_rounds,
                history=list(history),
                last_offer=last_offer,
                reservation_price=buyer.value,
                budget=buyer.budget,
            )
        else:
            current_role = AgentRole.SELLER
            current_agent = seller_agent
            ctx = AgentContext(
                item=item,
                role=AgentRole.SELLER,
                round_number=round_num,
                max_rounds=max_rounds,
                history=list(history),
                last_offer=last_offer,
                reservation_price=seller.cost,
                target_margin=seller.target_margin,
            )

        # ── get action ───────────────────────────────────────────────────
        action = current_agent.decide(ctx)

        # ── first-round corrections ─────────────────────────────────────
        if round_num == 0:
            if action.action == ActionType.COUNTER:
                action = NegotiationAction(
                    ActionType.OFFER,
                    action.offer_price,
                    action.message_public,
                    action.rationale_private,
                )
            if action.action in (ActionType.ACCEPT, ActionType.REJECT):
                fallback_price = (
                    round(buyer.value * 0.5, 2)
                    if current_role == AgentRole.BUYER
                    else round(seller.cost * 1.5, 2)
                )
                action = NegotiationAction(
                    ActionType.OFFER,
                    action.offer_price or fallback_price,
                    "Opening offer.",
                    "Corrected from accept/reject on round 0.",
                )

        # ── constraint check ─────────────────────────────────────────────
        validation = validate_action(
            current_role, action, buyer, seller,
            last_offer, item, round_num, min_price, max_price,
        )

        if not validation.valid:
            risk_events.append({
                "round": round_num,
                "role": current_role.value,
                "violation_type": validation.violation_type,
                "reason": validation.reason,
                "attempted_action": action.action.value,
                "attempted_price": action.offer_price,
                "time_step": time_step,
            })
            action = NegotiationAction(
                ActionType.REJECT,
                None,
                "I cannot continue this negotiation.",
                f"Auto-corrected: {validation.reason}",
            )

        # ── record turn ──────────────────────────────────────────────────
        turn = NegotiationTurn(
            round_number=round_num,
            agent_role=current_role,
            action=action,
            timestamp=time.time(),
        )
        history.append(turn)

        if event_logger:
            event_logger.log_turn(
                turn, time_step, item.item_id,
                buyer.buyer_id, seller.seller_id,
            )

        # ── check termination ────────────────────────────────────────────
        if action.action == ActionType.ACCEPT:
            deal_price = last_offer  # accepting the opponent's last offer
            return NegotiationResult(
                item=item,
                buyer_id=buyer.buyer_id,
                seller_id=seller.seller_id,
                deal_made=True,
                deal_price=deal_price,
                termination_reason=TerminationReason.ACCEPTED,
                rounds_taken=round_num + 1,
                history=history,
                buyer_value=buyer.value,
                seller_cost=seller.cost,
                buyer_surplus=(buyer.value - deal_price) if deal_price else 0,
                seller_surplus=(deal_price - seller.cost) if deal_price else 0,
                risk_events=risk_events,
                time_step=time_step,
            )

        if action.action == ActionType.REJECT:
            return NegotiationResult(
                item=item,
                buyer_id=buyer.buyer_id,
                seller_id=seller.seller_id,
                deal_made=False,
                deal_price=None,
                termination_reason=TerminationReason.REJECTED,
                rounds_taken=round_num + 1,
                history=history,
                buyer_value=buyer.value,
                seller_cost=seller.cost,
                risk_events=risk_events,
                time_step=time_step,
            )

        # ── update last offer ────────────────────────────────────────────
        if action.offer_price is not None:
            last_offer = action.offer_price

    # ── timeout ──────────────────────────────────────────────────────────
    return NegotiationResult(
        item=item,
        buyer_id=buyer.buyer_id,
        seller_id=seller.seller_id,
        deal_made=False,
        deal_price=None,
        termination_reason=TerminationReason.TIMEOUT,
        rounds_taken=max_rounds,
        history=history,
        buyer_value=buyer.value,
        seller_cost=seller.cost,
        risk_events=risk_events,
        time_step=time_step,
    )
