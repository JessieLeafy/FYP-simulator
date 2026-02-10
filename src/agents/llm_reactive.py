"""LLM-powered reactive negotiation agent."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.agents.llm_utils import (
    call_llm_and_parse,
    fallback_action,
    to_action,
)
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_reactive_prompt


class LLMReactiveAgent(BaseAgent):
    """Single-shot LLM agent: prompt → JSON action."""

    def __init__(self, backend: OllamaLLMBackend):
        self._backend = backend

    @property
    def agent_type(self) -> str:
        return "llm_reactive"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_reactive_prompt(ctx)
        return call_llm_and_parse(self._backend, prompt, ctx)


# ── backwards-compatible aliases ──────────────────────────────────────────────
# These were previously private helpers imported by llm_deliberative and
# memory_agent.  New code should import from src.agents.llm_utils directly.
_to_action = to_action
_fallback_action = fallback_action
