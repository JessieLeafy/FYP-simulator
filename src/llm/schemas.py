"""JSON schemas and format instructions for LLM agent outputs."""

SCHEMA_DESCRIPTION = """\
Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null"""

FORMAT_ERROR_PROMPT = """\
Your previous response was NOT valid JSON. Respond with ONLY a valid JSON object.
Do NOT wrap it in markdown. Do NOT include any text outside the JSON.
{"action": "...", "offer_price": ..., "message_public": "...", "rationale_private": "..."}"""


FREE_LANGUAGE_RETRY_HINT = """\
Your previous response did not include a valid price offer.
You MUST include exactly one price in the format: ### BUYER_PRICE($X) ### or ### SELLER_PRICE($X) ###
If you want to accept the deal, include the word MAKE_DEAL.
Please respond again:"""


def build_rethink_prompt(error_reason: str) -> str:
    """Build a short corrective prompt for one rethink attempt.

    Args:
        error_reason: A concise description of what was wrong
            (e.g., "Price $50 is below your minimum of $80").

    Returns:
        A short prompt asking the model to correct its output.
    """
    return (
        f"ERROR: {error_reason}\n"
        "Please output a corrected JSON response.\n"
        '{"action": "...", "offer_price": ..., "message_public": "...", '
        '"rationale_private": "..."}'
    )
