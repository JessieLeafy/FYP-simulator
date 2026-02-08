"""Abstract base class for negotiation agents."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.types import AgentContext, NegotiationAction


class BaseAgent(ABC):
    """Every agent must implement *decide* and expose *agent_type*."""

    @abstractmethod
    def decide(self, ctx: AgentContext) -> NegotiationAction:
        """Return the next negotiation action given the current context."""
        ...

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """A short identifier for this agent class."""
        ...
