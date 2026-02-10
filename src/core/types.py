"""Core domain types for the multi-agent negotiation simulation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentRole(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"


class ActionType(str, Enum):
    OFFER = "offer"
    COUNTER = "counter"
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass
class Item:
    item_id: str
    name: str
    reference_price: float


@dataclass
class BuyerState:
    buyer_id: str
    value: float          # max willingness-to-pay
    budget: float
    patience: int         # informational; not enforced by protocol


@dataclass
class SellerState:
    seller_id: str
    cost: float           # reservation price
    target_margin: float
    patience: int


@dataclass
class NegotiationAction:
    action: ActionType
    offer_price: Optional[float]
    message_public: str
    rationale_private: str


@dataclass
class NegotiationTurn:
    round_number: int
    agent_role: AgentRole
    action: NegotiationAction
    timestamp: float = 0.0


class TerminationReason(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    INVALID = "invalid"


@dataclass
class NegotiationResult:
    item: Item
    buyer_id: str
    seller_id: str
    deal_made: bool
    deal_price: Optional[float]
    termination_reason: TerminationReason
    rounds_taken: int
    history: list[NegotiationTurn] = field(default_factory=list)
    buyer_value: float = 0.0
    seller_cost: float = 0.0
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0
    risk_events: list[dict] = field(default_factory=list)
    time_step: int = 0


@dataclass
class Offer:
    """A price offer within a negotiation."""
    price: float
    round_number: int
    proposer_role: AgentRole


@dataclass
class Outcome:
    """Settlement outcome of a negotiation session (non-LLM computed)."""
    status: str                              # "deal" | "no_deal" | "timeout"
    agreed_price: Optional[float] = None
    rounds: int = 0
    buyer_surplus: float = 0.0
    seller_surplus: float = 0.0
    welfare: float = 0.0


@dataclass
class MarketTickStats:
    """Aggregate statistics for one market tick."""
    tick: int
    num_sessions: int
    deals_made: int
    fail_rate: float
    mean_price: float
    price_std: float
    liquidity: float                         # deals / sessions
    buyer_surplus_mean: float
    seller_surplus_mean: float


@dataclass
class AgentContext:
    """Information visible to an agent when making a decision."""
    item: Item
    role: AgentRole
    round_number: int
    max_rounds: int
    history: list[NegotiationTurn]
    last_offer: Optional[float]
    reservation_price: float       # value for buyer, cost for seller
    budget: Optional[float] = None           # buyer only
    target_margin: Optional[float] = None    # seller only
