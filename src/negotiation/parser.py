"""Robust JSON extraction and validation for LLM agent outputs."""
from __future__ import annotations

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[dict[str, Any]]:
    """Extract a JSON object from *text* that may contain extra content.

    Tries, in order:
      1. Direct ``json.loads``
      2. Content inside markdown code fences
      3. First ``{ … }`` substring
      4. Heuristic repair (single quotes, trailing commas, …)
    """
    text = text.strip()

    # 1 – direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2 – markdown code blocks
    for m in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL):
        try:
            obj = json.loads(m.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    # 3 – first { … } span (greedy on closing brace)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # 4 – attempt heuristic repair on that candidate
        repaired = _attempt_repair(candidate)
        if repaired is not None:
            return repaired

    return None


def _attempt_repair(text: str) -> Optional[dict[str, Any]]:
    """Best-effort fixups for common LLM JSON errors."""
    s = text
    # single → double quotes
    s = s.replace("'", '"')
    # trailing commas
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    # unquoted keys
    s = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', s)
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    return None


# ── schema-level validation ─────────────────────────────────────────────────

_VALID_ACTIONS = {"offer", "counter", "accept", "reject"}


def validate_action_json(obj: dict[str, Any]) -> tuple[bool, str]:
    """Check that *obj* conforms to the negotiation action schema.

    Returns ``(True, "")`` on success or ``(False, reason)`` on failure.
    """
    for key in ("action", "offer_price", "message_public"):
        if key not in obj:
            return False, f"Missing required field: {key}"
    # rationale_private is optional; default to empty string if absent
    if "rationale_private" not in obj:
        obj["rationale_private"] = ""

    action = obj["action"]
    if action not in _VALID_ACTIONS:
        return False, f"Invalid action '{action}'. Must be one of {_VALID_ACTIONS}"

    price = obj["offer_price"]

    if action in ("offer", "counter"):
        if price is None:
            return False, f"offer_price must be a number for action '{action}'"
        if not isinstance(price, (int, float)):
            return False, f"offer_price must be numeric, got {type(price).__name__}"
        if price <= 0:
            return False, "offer_price must be positive"

    elif action in ("accept", "reject"):
        # auto-correct price to null
        if price is not None:
            obj["offer_price"] = None

    # coerce string fields
    if not isinstance(obj.get("message_public"), str):
        obj["message_public"] = str(obj.get("message_public", ""))
    if not isinstance(obj.get("rationale_private"), str):
        obj["rationale_private"] = str(obj.get("rationale_private", ""))

    return True, ""


# ── free-language parsing ──────────────────────────────────────────────────

# Matches ### BUYER_PRICE($123.45) ### or ### SELLER_PRICE($123.45) ###
# with optional whitespace variations
_ROLE_PRICE_TAG_RE = re.compile(
    r"###\s*(?:BUYER_PRICE|SELLER_PRICE)\(\s*\$\s*([\d]+(?:\.[\d]+)?)\s*\)\s*###",
    re.IGNORECASE,
)

# Fallback: match bare $123.45 patterns (less reliable)
_BARE_PRICE_RE = re.compile(
    r"\$\s*([\d]+(?:\.[\d]+)?)",
)

_ACCEPT_KEYWORDS = ("ACCEPT_DEAL", "MAKE_DEAL")


def extract_price_from_text(text: str) -> Optional[float]:
    """Extract a price from free-language text.

    Looks for ``### BUYER_PRICE($X) ###`` or ``### SELLER_PRICE($X) ###``
    tags first. Falls back to the last bare ``$X`` pattern if no tag is
    found. Returns None if no price can be extracted.
    """
    # Primary: role-specific tagged price
    matches = _ROLE_PRICE_TAG_RE.findall(text)
    if matches:
        try:
            return float(matches[-1])  # last tag wins
        except ValueError:
            pass

    # Fallback: bare dollar amounts (take the last one as the offer)
    bare = _BARE_PRICE_RE.findall(text)
    if bare:
        try:
            return float(bare[-1])
        except ValueError:
            pass

    return None


def detect_accept_intent(text: str) -> bool:
    """Check if the text contains an acceptance keyword."""
    upper = text.upper()
    return any(kw in upper for kw in _ACCEPT_KEYWORDS)
