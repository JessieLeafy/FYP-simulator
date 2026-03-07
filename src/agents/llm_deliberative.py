"""LLM-powered deliberative negotiation agent with structured reasoning."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_and_parse
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_deliberative_prompt

if TYPE_CHECKING:
    from src.core.config import PromptConfig


class LLMDeliberativeAgent(BaseAgent):
    """Deliberative LLM agent: forces structured belief / target / strategy
    reasoning inside ``rationale_private``."""

    def __init__(
        self,
        backend: OllamaLLMBackend,
        prompt_cfg: Optional[PromptConfig] = None,
    ):
        self._backend = backend
        self._prompt_cfg = prompt_cfg

    @property
    def agent_type(self) -> str:
        return "llm_deliberative"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_deliberative_prompt(ctx, prompt_cfg=self._prompt_cfg)
        return call_llm_and_parse(self._backend, prompt, ctx)
