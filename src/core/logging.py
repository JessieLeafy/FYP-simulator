"""Event-level JSONL logging and run output management."""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from src.core.types import NegotiationResult, NegotiationTurn


class EventLogger:
    """Writes structured events as newline-delimited JSON."""

    def __init__(self, run_dir: str):
        self.run_dir = run_dir
        os.makedirs(run_dir, exist_ok=True)
        self._events_path = os.path.join(run_dir, "events.jsonl")
        self._file = open(self._events_path, "a")

    def log_turn(
        self,
        turn: NegotiationTurn,
        time_step: int,
        item_id: str,
        buyer_id: str,
        seller_id: str,
        *,
        llm_action: Optional[str] = None,
        effective_action: Optional[str] = None,
        override_flag: bool = False,
        override_reason: str = "",
        utility: Optional[float] = None,
        threshold: Optional[float] = None,
        offer_received: Optional[float] = None,
    ) -> None:
        """Write a ``turn`` event to the JSONL log.

        Research-grade fields (all keyword-only, backwards-compatible):
            llm_action: raw action string from the agent/LLM, or
                ``"skipped"`` when the settlement gate bypassed the call.
            effective_action: action actually executed by the simulator
                (may differ from *llm_action* when an override fired).
            override_flag: ``True`` when the simulator overrode the LLM.
            override_reason: explanation of the override, e.g.
                ``"gate: utility=20.00 (offer $80 <= cap $100)"``.
            utility: surplus the agent gains by accepting *offer_received*
                (``None`` when no prior offer exists).
            threshold: the agent's acceptance boundary — max price for a
                buyer, min price for a seller.
            offer_received: the opponent's last offer being evaluated.
        """
        event: dict[str, Any] = {
            "event": "turn",
            "time_step": time_step,
            "item_id": item_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "round": turn.round_number,
            "role": turn.agent_role.value,
            "action": turn.action.action.value,
            "offer_price": turn.action.offer_price,
            "message_public": turn.action.message_public,
            "timestamp": turn.timestamp,
            # Research metadata — always present for consistent downstream parsing.
            "offer_received": offer_received,
            "utility": utility,
            "threshold": threshold,
            "llm_action": llm_action,
            "effective_action": (
                effective_action if effective_action is not None
                else turn.action.action.value
            ),
            "override_flag": override_flag,
            "override_reason": override_reason,
        }
        self._file.write(json.dumps(event) + "\n")

    def log_result(self, result: NegotiationResult) -> None:
        event: dict[str, Any] = {
            "event": "result",
            "time_step": result.time_step,
            "item_id": result.item.item_id,
            "buyer_id": result.buyer_id,
            "seller_id": result.seller_id,
            "deal_made": result.deal_made,
            "deal_price": result.deal_price,
            "termination": result.termination_reason.value,
            "rounds_taken": result.rounds_taken,
            "buyer_value": result.buyer_value,
            "seller_cost": result.seller_cost,
            "buyer_surplus": result.buyer_surplus,
            "seller_surplus": result.seller_surplus,
            "risk_events_count": len(result.risk_events),
        }
        self._file.write(json.dumps(event) + "\n")

    def log_risk_event(self, event_data: dict[str, Any]) -> None:
        record = dict(event_data)
        record["event"] = "risk"
        self._file.write(json.dumps(record) + "\n")

    def log_tick_stats(self, stats: Any) -> None:
        """Write a tick_end event with market-level aggregate stats."""
        event = {
            "event": "tick_end",
            "tick": stats.tick,
            "num_sessions": stats.num_sessions,
            "deals_made": stats.deals_made,
            "fail_rate": stats.fail_rate,
            "mean_price": stats.mean_price,
            "price_std": stats.price_std,
            "liquidity": stats.liquidity,
            "buyer_surplus_mean": stats.buyer_surplus_mean,
            "seller_surplus_mean": stats.seller_surplus_mean,
        }
        self._file.write(json.dumps(event) + "\n")

    def close(self) -> None:
        self._file.flush()
        self._file.close()
