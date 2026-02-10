"""JSON schemas and format instructions for LLM agent outputs."""

SCHEMA_DESCRIPTION = """\
You MUST respond with ONLY a JSON object (no markdown, no extra text) matching this schema:
{
  "action": "offer" | "counter" | "accept" | "reject",
  "offer_price": <number or null>,
  "message_public": "<message to opponent>",
  "rationale_private": "<your private reasoning>"
}
Rules:
- action must be one of: "offer", "counter", "accept", "reject"
- If action is "offer" or "counter", offer_price must be a positive number
- If action is "accept" or "reject", offer_price must be null
- message_public is shown to your opponent
- rationale_private is private and NOT shown to anyone"""

FORMAT_ERROR_PROMPT = """\
Your previous response was NOT valid JSON. You MUST respond with ONLY a valid JSON object.
Do NOT wrap it in markdown code blocks. Do NOT include any text before or after the JSON.

Required format:
{
  "action": "offer" | "counter" | "accept" | "reject",
  "offer_price": <number or null>,
  "message_public": "<string>",
  "rationale_private": "<string>"
}"""
