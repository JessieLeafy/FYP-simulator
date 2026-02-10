"""Configuration loading and defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class LLMConfig:
    model: str = "qwen2.5:3b"
    temperature: float = 0.2
    max_tokens: int = 256
    timeout_sec: float = 30.0
    max_retries: int = 3
    base_url: str = "http://localhost:11434"
    debug: bool = False


@dataclass
class MarketConfig:
    buyer_value_min: float = 50.0
    buyer_value_max: float = 150.0
    seller_cost_min: float = 30.0
    seller_cost_max: float = 120.0
    buyer_budget_min: float = 80.0
    buyer_budget_max: float = 200.0
    seller_margin_min: float = 0.05
    seller_margin_max: float = 0.30
    buyer_patience_min: int = 3
    buyer_patience_max: int = 10
    seller_patience_min: int = 3
    seller_patience_max: int = 10
    item_ref_price_min: float = 40.0
    item_ref_price_max: float = 130.0
    num_item_types: int = 5


@dataclass
class NegotiationConfig:
    max_rounds: int = 10
    min_price: float = 1.0
    max_price: float = 500.0


@dataclass
class ShockConfig:
    enabled: bool = False
    demand_multiplier_min: float = 0.8
    demand_multiplier_max: float = 1.2
    supply_multiplier_min: float = 0.8
    supply_multiplier_max: float = 1.2
    shock_probability: float = 0.1


@dataclass
class FixedScenarioConfig:
    """Parameters for fixed-value scenario mode.

    Each field accepts a single number or a list of numbers.
    Lists are drawn from via ``selection`` strategy ("cycle" or "random").
    """
    buyer_value: Any = None            # float | list[float] | None
    buyer_budget: Any = None
    buyer_patience: Any = None         # int | list[int] | None
    seller_cost: Any = None
    seller_target_margin: Any = None
    seller_patience: Any = None
    item_reference_price: Any = None   # float | list[float] | None
    selection: str = "cycle"           # "cycle" | "random"


@dataclass
class SimulationConfig:
    agent_type: str = "rule_based"
    buyer_agent_type: Optional[str] = None
    seller_agent_type: Optional[str] = None
    steps: int = 30
    buyers_per_step: int = 50
    sellers_per_step: int = 50
    seed: int = 42
    output_dir: str = "outputs/runs"
    scenario_mode: str = "distribution"   # "distribution" | "fixed"
    mode: str = "session"                 # "session" | "market"
    matching: str = "random"              # "random" (extensible)
    llm: LLMConfig = field(default_factory=LLMConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    negotiation: NegotiationConfig = field(default_factory=NegotiationConfig)
    shock: ShockConfig = field(default_factory=ShockConfig)
    fixed: FixedScenarioConfig = field(default_factory=FixedScenarioConfig)
    memory_k: int = 5


def load_config(path: str) -> SimulationConfig:
    """Load configuration from a YAML (or JSON) file."""
    with open(path, "r") as f:
        raw = f.read()

    if HAS_YAML:
        data = yaml.safe_load(raw) or {}
    else:
        import json
        data = json.loads(raw)

    return _dict_to_config(data)


_NESTED = {
    "llm": LLMConfig,
    "market": MarketConfig,
    "negotiation": NegotiationConfig,
    "shock": ShockConfig,
    "fixed": FixedScenarioConfig,
}

_TOP_SCALARS = (
    "agent_type", "buyer_agent_type", "seller_agent_type",
    "steps", "buyers_per_step", "sellers_per_step",
    "seed", "output_dir", "memory_k", "scenario_mode",
    "mode", "matching",
)


def _dict_to_config(data: dict[str, Any]) -> SimulationConfig:
    cfg = SimulationConfig()
    for key in _TOP_SCALARS:
        if key in data:
            setattr(cfg, key, data[key])
    for section, cls in _NESTED.items():
        if section in data and isinstance(data[section], dict):
            obj = getattr(cfg, section)
            for k, v in data[section].items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
    return cfg


def resolve_fixed_params(cfg: SimulationConfig) -> dict[str, Any]:
    """Return a JSON-serialisable dict of the resolved fixed-mode parameters.

    For enumerated (list) values the raw lists are included so callers
    can see the full set; individual draws are logged per-negotiation.
    """
    if cfg.scenario_mode != "fixed":
        return {}
    f = cfg.fixed
    resolved: dict[str, Any] = {"selection": f.selection}
    for key in (
        "buyer_value", "buyer_budget", "buyer_patience",
        "seller_cost", "seller_target_margin", "seller_patience",
        "item_reference_price",
    ):
        val = getattr(f, key)
        if val is not None:
            resolved[key] = val
    return resolved
