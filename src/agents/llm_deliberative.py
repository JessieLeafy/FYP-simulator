"""LLM-powered deliberative negotiation agent with structured reasoning."""
from __future__ import annotations

import logging

from src.agents.base import BaseAgent
from src.agents.llm_reactive import _fallback_action, _to_action
from src.core.types import AgentContext, NegotiationAction
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_deliberative_prompt
from src.llm.schemas import FORMAT_ERROR_PROMPT
from src.negotiation.parser import extract_json, validate_action_json

logger = logging.getLogger(__name__)


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
        return self._call_and_parse(prompt, ctx)

    def _call_and_parse(
        self, prompt: str, ctx: AgentContext
    ) -> NegotiationAction:
        # first attempt
        raw = self._backend.generate(prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)
            logger.warning("Deliberative JSON validation failed: %s", reason)
        else:
            logger.warning(
                "Deliberative agent: failed to extract JSON from response"
            )

        # retry
        retry_prompt = prompt + "\n\n" + FORMAT_ERROR_PROMPT
        raw = self._backend.generate(retry_prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)

        logger.error(
            "Deliberative agent: LLM failed after retry – using fallback"
        )
        return _fallback_action(ctx)
