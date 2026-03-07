"""LLM-powered reactive negotiation agent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.agents.base import BaseAgent
from src.agents.llm_utils import (
    call_llm_and_parse,
    fallback_action,
    to_action,
)
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_reactive_prompt

if TYPE_CHECKING:
    from src.core.config import PromptConfig


class LLMReactiveAgent(BaseAgent):
    """Single-shot LLM agent: prompt -> JSON action."""

    def __init__(
        self,
        backend: OllamaLLMBackend,
        prompt_cfg: Optional[PromptConfig] = None,
    ):
        self._backend = backend
        self._prompt_cfg = prompt_cfg

    @property
    def agent_type(self) -> str:
        return "llm_reactive"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_reactive_prompt(ctx, prompt_cfg=self._prompt_cfg)
        return call_llm_and_parse(self._backend, prompt, ctx)


# ── backwards-compatible aliases ──────────────────────────────────────────────
_to_action = to_action
_fallback_action = fallback_action
