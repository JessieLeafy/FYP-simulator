"""LLM-powered free-language negotiation agent (AgenticPay-style).

Agents respond in natural language instead of structured JSON.
Prices are extracted via ### PRICE($X) ### tags and deal acceptance
via the ACCEPT_DEAL keyword.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_free_language
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_free_language_prompt

if TYPE_CHECKING:
    from src.core.config import PromptConfig


class LLMFreeLanguageAgent(BaseAgent):
    """Free-language LLM agent: natural text with price tags."""

    def __init__(
        self,
        backend: OllamaLLMBackend,
        prompt_cfg: Optional[PromptConfig] = None,
    ):
        self._backend = backend
        self._prompt_cfg = prompt_cfg

    @property
    def agent_type(self) -> str:
        return "llm_free_language"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_free_language_prompt(ctx, prompt_cfg=self._prompt_cfg)
        return call_llm_free_language(self._backend, prompt, ctx)
