"""LLM agent with lightweight episodic memory."""
from __future__ import annotations

import logging
from typing import Optional

from src.agents.base import BaseAgent
from src.agents.llm_reactive import _fallback_action, _to_action
from src.core.types import AgentContext, NegotiationAction, NegotiationResult
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_deliberative_prompt, build_memory_context
from src.llm.schemas import FORMAT_ERROR_PROMPT
from src.negotiation.parser import extract_json, validate_action_json

logger = logging.getLogger(__name__)


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
    ):
        self._backend = backend
        self._memory = memory_store or MemoryStore(k=memory_k)

    @property
    def agent_type(self) -> str:
        return "memory"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        memories = self._memory.retrieve(ctx.item.name)
        memory_text = build_memory_context(memories)
        base_prompt = build_deliberative_prompt(ctx)

        prompt = (
            (memory_text + "\n" + base_prompt) if memory_text else base_prompt
        )
        return self._call_and_parse(prompt, ctx)

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

    # ── internal ─────────────────────────────────────────────────────────

    def _call_and_parse(
        self, prompt: str, ctx: AgentContext
    ) -> NegotiationAction:
        raw = self._backend.generate(prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)
            logger.warning("Memory agent JSON validation failed: %s", reason)
        else:
            logger.warning("Memory agent: could not extract JSON")

        retry_prompt = prompt + "\n\n" + FORMAT_ERROR_PROMPT
        raw = self._backend.generate(retry_prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)

        logger.error("Memory agent: LLM failed after retry – using fallback")
        return _fallback_action(ctx)
