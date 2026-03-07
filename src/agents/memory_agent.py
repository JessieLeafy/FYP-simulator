"""LLM agents with episodic memory and reputation tracking."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_and_parse
from src.core.types import AgentContext, AgentRole, NegotiationAction, NegotiationResult
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import (
    build_deliberative_prompt,
    build_memory_context,
    build_reputation_context,
)

if TYPE_CHECKING:
    from src.core.config import PromptConfig


class MemoryStore:
    """Simple episodic memory: stores and retrieves past negotiation summaries."""

    def __init__(self, k: int = 5):
        self.memories: list[dict] = []
        self.k = k

    def add(self, summary: dict) -> None:
        self.memories.append(summary)

    def retrieve(self, item_name: Optional[str] = None) -> list[dict]:
        """Return up to *k* most relevant memories.

        Relevance heuristic: prefer same item name, then most recent.
        """
        if not self.memories:
            return []

        if item_name:
            same_item = [
                m for m in self.memories
                if m.get("item_name") == item_name
            ]
            if same_item:
                return same_item[-self.k :]

        # fall back to most recent
        return self.memories[-self.k :]


# ═══════════════════════════════════════════════════════════════════════
#  Reputation tracking (Experiment F)
# ═══════════════════════════════════════════════════════════════════════

class ReputationStore:
    """Tracks per-opponent negotiation history and reputation scores.

    For each opponent ID, records:
    - Number of interactions
    - Deal rate (fraction of interactions resulting in a deal)
    - Average deal price
    - Average concession rate (price change per round)
    - Inferred style label (cooperative / tough / unreliable)
    """

    def __init__(self) -> None:
        self._records: dict[str, list[dict]] = {}  # opponent_id → [outcomes]

    def record(self, opponent_id: str, outcome: dict) -> None:
        """Record an interaction outcome with a specific opponent."""
        if opponent_id not in self._records:
            self._records[opponent_id] = []
        self._records[opponent_id].append(outcome)

    def get_reputation(self, opponent_id: str) -> Optional[dict]:
        """Compute reputation summary for a specific opponent.

        Returns None if no interactions recorded.
        """
        records = self._records.get(opponent_id)
        if not records:
            return None

        n = len(records)
        deals = [r for r in records if r.get("deal_made")]
        deal_rate = len(deals) / n

        avg_price = 0.0
        if deals:
            prices = [r["deal_price"] for r in deals if r.get("deal_price")]
            avg_price = sum(prices) / len(prices) if prices else 0.0

        avg_rounds = sum(r.get("rounds", 0) for r in records) / n

        # infer style from history
        if deal_rate >= 0.8 and avg_rounds <= 3:
            style = "cooperative"
        elif deal_rate >= 0.5:
            style = "moderate"
        elif deal_rate < 0.3:
            style = "unreliable"
        else:
            style = "tough"

        return {
            "opponent_id": opponent_id,
            "interactions": n,
            "deal_rate": round(deal_rate, 2),
            "avg_deal_price": round(avg_price, 2),
            "avg_rounds": round(avg_rounds, 1),
            "style": style,
        }

    @property
    def known_opponents(self) -> list[str]:
        """Return list of opponent IDs with recorded history."""
        return list(self._records.keys())


class MemoryAgent(BaseAgent):
    """Wraps the deliberative prompt with an episodic memory context.

    The agent accumulates summaries of past negotiations and injects the
    most relevant ones into each prompt.
    """

    def __init__(
        self,
        backend: OllamaLLMBackend,
        memory_store: Optional[MemoryStore] = None,
        memory_k: int = 5,
        prompt_cfg: Optional[PromptConfig] = None,
    ):
        self._backend = backend
        self._memory = memory_store or MemoryStore(k=memory_k)
        self._prompt_cfg = prompt_cfg

    @property
    def agent_type(self) -> str:
        return "memory"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        memories = self._memory.retrieve(ctx.item.name)
        memory_text = build_memory_context(memories)
        base_prompt = build_deliberative_prompt(ctx, prompt_cfg=self._prompt_cfg)

        prompt = (
            (memory_text + "\n" + base_prompt) if memory_text else base_prompt
        )
        return call_llm_and_parse(self._backend, prompt, ctx)

    def record_outcome(self, result: NegotiationResult) -> None:
        """Store a negotiation summary for future reference."""
        # infer a rough "opponent style" label
        if result.deal_made and result.rounds_taken <= 3:
            style = "eager"
        elif result.deal_made:
            style = "moderate"
        elif result.termination_reason.value == "timeout":
            style = "stubborn"
        else:
            style = "aggressive"

        self._memory.add({
            "item_name": result.item.name,
            "deal_made": result.deal_made,
            "deal_price": result.deal_price,
            "rounds": result.rounds_taken,
            "opponent_style": style,
        })


class ReputationAgent(BaseAgent):
    """LLM agent with opponent-specific reputation tracking.

    Extends MemoryAgent's episodic memory with per-opponent reputation
    scores.  The agent's prompt includes both general memory and specific
    reputation data about the current opponent.
    """

    def __init__(
        self,
        backend: OllamaLLMBackend,
        memory_store: Optional[MemoryStore] = None,
        reputation_store: Optional[ReputationStore] = None,
        memory_k: int = 5,
        prompt_cfg: Optional[PromptConfig] = None,
        role: AgentRole = AgentRole.BUYER,
    ):
        self._backend = backend
        self._memory = memory_store or MemoryStore(k=memory_k)
        self._reputation = reputation_store or ReputationStore()
        self._prompt_cfg = prompt_cfg
        self._role = role
        self._current_opponent_id: Optional[str] = None

    @property
    def agent_type(self) -> str:
        return "reputation"

    def set_opponent(self, opponent_id: str) -> None:
        """Set the current opponent ID for reputation lookup."""
        self._current_opponent_id = opponent_id

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        # episodic memory
        memories = self._memory.retrieve(ctx.item.name)
        memory_text = build_memory_context(memories)

        # reputation context
        rep_text = ""
        if self._current_opponent_id:
            rep = self._reputation.get_reputation(self._current_opponent_id)
            if rep:
                rep_text = build_reputation_context(rep)

        base_prompt = build_deliberative_prompt(ctx, prompt_cfg=self._prompt_cfg)

        # compose: reputation → memory → base prompt
        prefix_parts = [p for p in [rep_text, memory_text] if p]
        prefix = "\n".join(prefix_parts)
        prompt = (prefix + "\n" + base_prompt) if prefix else base_prompt

        return call_llm_and_parse(self._backend, prompt, ctx)

    def record_outcome(self, result: NegotiationResult) -> None:
        """Store outcome in both episodic memory and reputation store."""
        # episodic memory
        if result.deal_made and result.rounds_taken <= 3:
            style = "eager"
        elif result.deal_made:
            style = "moderate"
        elif result.termination_reason.value == "timeout":
            style = "stubborn"
        else:
            style = "aggressive"

        self._memory.add({
            "item_name": result.item.name,
            "deal_made": result.deal_made,
            "deal_price": result.deal_price,
            "rounds": result.rounds_taken,
            "opponent_style": style,
        })

        # reputation store — identify opponent
        if self._role == AgentRole.BUYER:
            opponent_id = result.seller_id
        else:
            opponent_id = result.buyer_id

        self._reputation.record(opponent_id, {
            "deal_made": result.deal_made,
            "deal_price": result.deal_price,
            "rounds": result.rounds_taken,
            "item_name": result.item.name,
        })
