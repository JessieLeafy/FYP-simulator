"""LLM-powered deliberative negotiation agent with structured reasoning."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_and_parse
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_deliberative_prompt


class LLMDeliberativeAgent(BaseAgent):
    """Deliberative LLM agent: forces structured belief / target / strategy
    reasoning inside ``rationale_private``."""

    def __init__(self, backend: OllamaLLMBackend):
        self._backend = backend

    @property
    def agent_type(self) -> str:
        return "llm_deliberative"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_deliberative_prompt(ctx)
        return call_llm_and_parse(self._backend, prompt, ctx)
