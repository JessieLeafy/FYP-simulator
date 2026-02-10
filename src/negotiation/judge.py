"""Consolidated action validation and enforcement.

The ActionJudge owns the full validate-and-enforce pipeline that was
previously scattered across protocol.py (first-round corrections,
auto-correction to REJECT) and constraints.py (domain validation).

Usage:
    judge = ActionJudge(min_price=1.0, max_price=500.0)
    action, risk_event = judge.enforce(role, action, buyer, seller, ...)
"""
from __future__ import annotations

from typing import Optional

from src.core.types import (
    ActionType,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    SellerState,
)
from src.negotiation.constraints import ValidationResult, validate_action


class ActionJudge:
    """Validates negotiation actions and enforces legality.

    Consolidates three concerns into one component:
      1. First-round corrections (COUNTER→OFFER, ACCEPT/REJECT→OFFER)
      2. Constraint validation (budget, cost, bounds, logic)
      3. Enforcement policy (invalid → REJECT + risk event logged)
    """

    def __init__(self, min_price: float = 1.0, max_price: float = 500.0):
        self.min_price = min_price
        self.max_price = max_price

    # ── first-round corrections ───────────────────────────────────────────

    def correct_first_round(
        self,
        action: NegotiationAction,
        role: AgentRole,
        buyer: BuyerState,
        seller: SellerState,
    ) -> NegotiationAction:
        """Correct illegal first-round actions to valid opening offers."""
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
                if role == AgentRole.BUYER
                else round(seller.cost * 1.5, 2)
            )
            action = NegotiationAction(
                ActionType.OFFER,
                action.offer_price or fallback_price,
                "Opening offer.",
                "Corrected from accept/reject on round 0.",
            )
        return action

    # ── constraint validation ─────────────────────────────────────────────

    def validate(
        self,
        role: AgentRole,
        action: NegotiationAction,
        buyer: BuyerState,
        seller: SellerState,
        last_offer: Optional[float],
        item: Item,
        round_number: int,
    ) -> ValidationResult:
        """Check action against all hard constraints."""
        return validate_action(
            role, action, buyer, seller,
            last_offer, item, round_number,
            self.min_price, self.max_price,
        )

    # ── enforce (validate + auto-correct) ─────────────────────────────────

    def enforce(
        self,
        role: AgentRole,
        action: NegotiationAction,
        buyer: BuyerState,
        seller: SellerState,
        last_offer: Optional[float],
        item: Item,
        round_number: int,
        time_step: int = 0,
    ) -> tuple[NegotiationAction, Optional[dict]]:
        """Validate action; if invalid, replace with REJECT and emit risk event.

        Returns:
            (possibly-corrected action, risk_event dict or None)
        """
        # First-round corrections
        if round_number == 0:
            action = self.correct_first_round(action, role, buyer, seller)

        # Constraint validation
        result = self.validate(
            role, action, buyer, seller, last_offer, item, round_number,
        )

        if result.valid:
            return action, None

        risk_event = {
            "round": round_number,
            "role": role.value,
            "violation_type": result.violation_type,
            "reason": result.reason,
            "attempted_action": action.action.value,
            "attempted_price": action.offer_price,
            "time_step": time_step,
        }

        corrected = NegotiationAction(
            ActionType.REJECT,
            None,
            "I cannot continue this negotiation.",
            f"Auto-corrected: {result.reason}",
        )

        return corrected, risk_event
