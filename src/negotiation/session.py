"""First-class NegotiationSession wrapping the alternating-offers protocol.

Replaces the bare ``run_negotiation`` function with a stateful session
object that owns transcript, last_offer, round counter, and the Judge.

Usage:
    session = NegotiationSession(buyer_agent, seller_agent, item, buyer,
                                 seller, max_rounds=10)
    result = session.run()

Settlement Gate
---------------
Each round the session runs a deterministic *feasibility check* before
and after calling the agent.  This is the primary fix for the weak-LLM
acceptance problem:

1. **Pre-LLM gate** — if the opponent's standing offer is already
   acceptable (non-negative surplus, within budget/cost), the session
   settles immediately without calling the agent at all.

2. **Post-LLM override** — if the agent returns ``COUNTER``/``REJECT``
   but the standing offer is feasible, the simulator overrides to
   ``ACCEPT``.  This is a defensive fallback; the pre-LLM gate should
   normally catch all feasible cases first.

Both ``llm_action`` (what the model said) and ``effective_action``
(what the simulator executed) are written to the JSONL event log with
an ``override_flag`` and ``override_reason`` for research analysis.
"""
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
from src.negotiation.feasibility import compute_utility, is_offer_feasible
from src.negotiation.judge import ActionJudge

if TYPE_CHECKING:
    from src.agents.base import BaseAgent
    from src.core.logging import EventLogger


class NegotiationSession:
    """Encapsulates a single buyer-seller negotiation.

    Owns session state (transcript, last_offer, round counter) and
    delegates validation to :class:`ActionJudge`.

    Attributes:
        transcript: list of NegotiationTurn recorded during the session.
        risk_events: list of constraint-violation dicts.
        last_offer: the most recent proposed price (or None).
        is_complete: True after :meth:`run` has finished.
    """

    def __init__(
        self,
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
    ):
        self.buyer_agent = buyer_agent
        self.seller_agent = seller_agent
        self.item = item
        self.buyer = buyer
        self.seller = seller
        self.max_rounds = max_rounds
        self.event_logger = event_logger
        self.time_step = time_step

        self.judge = ActionJudge(min_price, max_price)

        # ── session state ─────────────────────────────────────────────────
        self.transcript: list[NegotiationTurn] = []
        self.risk_events: list[dict] = []
        self.last_offer: Optional[float] = None
        self.current_round: int = 0
        self.is_complete: bool = False
        self._result: Optional[NegotiationResult] = None

    # ── main loop ─────────────────────────────────────────────────────────

    def run(self) -> NegotiationResult:
        """Execute the full negotiation and return the result."""
        for round_num in range(self.max_rounds):
            self.current_round = round_num

            # ── select active agent ───────────────────────────────────────
            if round_num % 2 == 0:
                role = AgentRole.BUYER
                agent = self.buyer_agent
                ctx = AgentContext(
                    item=self.item,
                    role=AgentRole.BUYER,
                    round_number=round_num,
                    max_rounds=self.max_rounds,
                    history=list(self.transcript),
                    last_offer=self.last_offer,
                    reservation_price=self.buyer.value,
                    budget=self.buyer.budget,
                )
            else:
                role = AgentRole.SELLER
                agent = self.seller_agent
                ctx = AgentContext(
                    item=self.item,
                    role=AgentRole.SELLER,
                    round_number=round_num,
                    max_rounds=self.max_rounds,
                    history=list(self.transcript),
                    last_offer=self.last_offer,
                    reservation_price=self.seller.cost,
                    target_margin=self.seller.target_margin,
                )

            # ── pre-compute feasibility for this turn ─────────────────────
            # offer_received is the opponent's last standing offer, which
            # the current agent is deciding whether to accept.
            offer_received = self.last_offer
            if offer_received is not None:
                utility = compute_utility(
                    role, offer_received, self.buyer, self.seller,
                )
                threshold = (
                    min(self.buyer.value, self.buyer.budget)
                    if role == AgentRole.BUYER
                    else self.seller.cost
                )
                feasible, accept_reason = is_offer_feasible(
                    role, offer_received, self.buyer, self.seller,
                )
            else:
                utility = threshold = None
                feasible, accept_reason = False, ""

            # ── Req 3a: pre-LLM settlement gate ──────────────────────────
            # If the standing offer is already acceptable, settle without
            # calling the agent.  This is the primary fix for weak LLMs
            # that fail to output "accept" when they should.
            if feasible:
                action = NegotiationAction(
                    ActionType.ACCEPT,
                    None,
                    "I accept your offer.",
                    f"Settlement gate: {accept_reason}",
                )
                turn = NegotiationTurn(
                    round_number=round_num,
                    agent_role=role,
                    action=action,
                    timestamp=time.time(),
                )
                self.transcript.append(turn)
                if self.event_logger:
                    self.event_logger.log_turn(
                        turn, self.time_step, self.item.item_id,
                        self.buyer.buyer_id, self.seller.seller_id,
                        llm_action="skipped",
                        effective_action="accept",
                        override_flag=True,
                        override_reason=f"gate: {accept_reason}",
                        utility=utility,
                        threshold=threshold,
                        offer_received=offer_received,
                    )
                self._result = self._settle(
                    offer_received, round_num + 1, TerminationReason.ACCEPTED,
                )
                self.is_complete = True
                return self._result

            # ── get action from agent ─────────────────────────────────────
            raw_action = agent.decide(ctx)
            llm_action = raw_action.action.value

            # ── judge: validate + enforce ─────────────────────────────────
            action, risk_event = self.judge.enforce(
                role, raw_action, self.buyer, self.seller,
                self.last_offer, self.item, round_num, self.time_step,
            )
            if risk_event:
                self.risk_events.append(risk_event)
                if self.event_logger:
                    self.event_logger.log_risk_event(risk_event)

            # ── Req 3b: post-LLM feasibility override (defensive) ─────────
            # The pre-LLM gate should have caught all feasible cases above.
            # This override is a safety net in case a future code path
            # bypasses the gate (e.g., if the gate threshold is ever tightened).
            effective_action = action.action.value
            override_flag = False
            override_reason = ""
            if action.action != ActionType.ACCEPT and offer_received is not None:
                f2, reason2 = is_offer_feasible(
                    role, offer_received, self.buyer, self.seller,
                )
                if f2:
                    action = NegotiationAction(
                        ActionType.ACCEPT,
                        None,
                        "I accept your offer.",
                        f"Feasibility override: {reason2}",
                    )
                    effective_action = "accept"
                    override_flag = True
                    override_reason = f"post_llm: {reason2}"

            # ── record turn ───────────────────────────────────────────────
            turn = NegotiationTurn(
                round_number=round_num,
                agent_role=role,
                action=action,
                timestamp=time.time(),
            )
            self.transcript.append(turn)

            if self.event_logger:
                self.event_logger.log_turn(
                    turn, self.time_step, self.item.item_id,
                    self.buyer.buyer_id, self.seller.seller_id,
                    llm_action=llm_action,
                    effective_action=effective_action,
                    override_flag=override_flag,
                    override_reason=override_reason,
                    utility=utility,
                    threshold=threshold,
                    offer_received=offer_received,
                )

            # ── check termination ─────────────────────────────────────────
            if action.action == ActionType.ACCEPT:
                self._result = self._settle(
                    self.last_offer, round_num + 1, TerminationReason.ACCEPTED,
                )
                self.is_complete = True
                return self._result

            if action.action == ActionType.REJECT:
                self._result = self._build_result(
                    deal_made=False, deal_price=None,
                    rounds=round_num + 1,
                    reason=TerminationReason.REJECTED,
                )
                self.is_complete = True
                return self._result

            # ── update last offer ─────────────────────────────────────────
            if action.offer_price is not None:
                self.last_offer = action.offer_price

        # ── timeout ───────────────────────────────────────────────────────
        self._result = self._build_result(
            deal_made=False, deal_price=None,
            rounds=self.max_rounds,
            reason=TerminationReason.TIMEOUT,
        )
        self.is_complete = True
        return self._result

    # ── settlement ────────────────────────────────────────────────────────

    def _settle(
        self,
        deal_price: Optional[float],
        rounds: int,
        reason: TerminationReason,
    ) -> NegotiationResult:
        """Compute surplus and build a deal result."""
        buyer_surplus = (self.buyer.value - deal_price) if deal_price else 0
        seller_surplus = (deal_price - self.seller.cost) if deal_price else 0
        return self._build_result(
            deal_made=True, deal_price=deal_price, rounds=rounds,
            reason=reason, buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
        )

    def _build_result(
        self,
        deal_made: bool,
        deal_price: Optional[float],
        rounds: int,
        reason: TerminationReason,
        buyer_surplus: float = 0.0,
        seller_surplus: float = 0.0,
    ) -> NegotiationResult:
        return NegotiationResult(
            item=self.item,
            buyer_id=self.buyer.buyer_id,
            seller_id=self.seller.seller_id,
            deal_made=deal_made,
            deal_price=deal_price,
            termination_reason=reason,
            rounds_taken=rounds,
            history=self.transcript,
            buyer_value=self.buyer.value,
            seller_cost=self.seller.cost,
            buyer_surplus=buyer_surplus,
            seller_surplus=seller_surplus,
            risk_events=self.risk_events,
            time_step=self.time_step,
        )

    @property
    def result(self) -> Optional[NegotiationResult]:
        """The session result, or None if not yet complete."""
        return self._result
