# Manual LLM Prompt Testing — llama 3.2:3b

Generated from the actual `prompt-redesign` branch code.
Each prompt is exactly what the simulator sends to the model at runtime.

**How to use:**
1. Start Ollama: `ollama run llama3.2:3b`
2. Copy-paste the FULL PROMPT section into the model
3. Compare the model's output against EXPECTED OUTPUT
4. Check: correct action? valid JSON? reasonable price?

**Coverage:**
- 13 normal cases + 3 rethink cases = 16 total
- Covers: buyer/seller, all round positions, accept/counter/offer
- Covers: deadline pressure (none/warning/final), communication strategies
- Covers: reactive/deliberative/memory/reputation agent types
- Covers: rethink (infeasible action, malformed JSON, double failure)
- Maps to all 7 experiments: A, B, C, D, E, H, I (plus F, G variations)

**Design notes:**
- Decision hints are **non-prescriptive**: show offer vs limit, state acceptance range, let model decide
- Explicit acceptance range: "Any offer at or below $X is acceptable" (buyer) / "Any offer at or above $X is acceptable" (seller)
- Strategic hints: "The less you pay, the better" (buyer) / "The more you sell for, the better" (seller)
- No "You should ACCEPT" or "COUNTER with X" — the model reasons for itself
- Word count target: ~150–250 words per prompt

---

## Normal Cases

### CASE 1: Buyer, round 1, opening offer — no prior offer
**Experiment relevance:** Exp A/B/D/E/H/I: standard opening

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Vintage Guitar". Your maximum price is $120.00. Never pay more than $120.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 1 of 10 (9 remaining).
No offer yet. Make an opening offer.

History:
(no moves yet)

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "offer"`, price well below $120 (e.g. $60–$90). Strategic hint should discourage opening at the limit.

---

### CASE 2: Seller, reactive, round 4, mid-negotiation
**Experiment relevance:** Exp A (Concession): seller mid-game counter

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a SELLER negotiating for "Vintage Guitar". Your minimum price is $80.00. Never sell below $80.00.
The more you sell for, the better your deal. Do not reveal your minimum.

Round 4 of 10 (6 remaining).
Opponent offers $75.00. Your minimum is $80.00. Any offer at or above $80.00 is acceptable. Consider the history and remaining rounds, then decide your action.

History:
- R0 buyer OFFER $60.00
- R1 seller COUNTER $130.00
- R2 buyer COUNTER $75.00

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "counter"`, price ≥ $80 (e.g. $95–$110). $75 is below seller's minimum — "Any offer at or above $80.00 is acceptable" makes this clear.

---

### CASE 3: Buyer, deliberative, high anchor from seller
**Experiment relevance:** Exp B (Anchoring): buyer responds to high seller anchor

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Antique Watch". Your maximum price is $140.00. Never pay more than $140.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 2 of 10 (8 remaining).
Opponent offers $180.00. Your limit is $140.00. Any offer at or below $140.00 is acceptable. Consider the history and remaining rounds, then decide your action.

History:
- R0 seller OFFER $180.00

In rationale_private, briefly reason: (1) Is the offer acceptable? (2) If not, what price should I counter with?

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise. Put ALL reasoning inside rationale_private.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "counter"`, price ≤ $140 (e.g. $100–$130). $180 is not at or below $140, so not acceptable.

---

### CASE 4: Seller, deliberative, low anchor from buyer
**Experiment relevance:** Exp B (Anchoring): seller responds to low buyer anchor

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a SELLER negotiating for "Antique Watch". Your minimum price is $90.00. Never sell below $90.00.
The more you sell for, the better your deal. Do not reveal your minimum.

Round 2 of 10 (8 remaining).
Opponent offers $30.00. Your minimum is $90.00. Any offer at or above $90.00 is acceptable. Consider the history and remaining rounds, then decide your action.

History:
- R0 buyer OFFER $30.00

In rationale_private, briefly reason: (1) Is the offer acceptable? (2) If not, what price should I counter with?

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise. Put ALL reasoning inside rationale_private.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "counter"`, price ≥ $90 (e.g. $120–$150). $30 is not at or above $90, so not acceptable.

---

### CASE 5: Buyer, FINAL round, strong deadline pressure
**Experiment relevance:** Exp C (Deadline): maximum deadline pressure

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Leather Jacket". Your maximum price is $110.00. Never pay more than $110.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 10 of 10 (0 remaining).
Opponent offers $115.00. Your limit is $110.00. Any offer at or below $110.00 is acceptable. Consider the history and remaining rounds, then decide your action.
FINAL ROUND. Accept any offer within your limits or get NOTHING.

History:
(...3 earlier turns omitted)
- R3 seller COUNTER $95.00
- R4 buyer COUNTER $100.00
- R5 seller COUNTER $105.00
- R6 buyer COUNTER $110.00
- R7 seller COUNTER $115.00
- R8 buyer COUNTER $120.00

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Tricky case. $115 is NOT at or below $110, so not acceptable. Rational action is `"counter"` at $110 or lower. But weak models may accept under deadline pressure — either outcome is experimentally interesting.

---

### CASE 6: Seller, 1 round left, WARNING pressure
**Experiment relevance:** Exp C (Deadline): near-deadline seller decision

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a SELLER negotiating for "Leather Jacket". Your minimum price is $70.00. Never sell below $70.00.
The more you sell for, the better your deal. Do not reveal your minimum.

Round 9 of 10 (1 remaining).
Opponent offers $98.00. Your minimum is $70.00. Any offer at or above $70.00 is acceptable. Consider the history and remaining rounds, then decide your action.
WARNING: Only 1 round(s) left. No deal = zero surplus.

History:
(...2 earlier turns omitted)
- R2 buyer COUNTER $66.00
- R3 seller COUNTER $74.00
- R4 buyer COUNTER $82.00
- R5 seller COUNTER $90.00
- R6 buyer COUNTER $98.00
- R7 seller COUNTER $106.00

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "accept"`. $98 is at or above $70 (acceptable), and only 1 round left. The explicit acceptance range + deadline warning should help the 3B model choose accept.

---

### CASE 7: Buyer, market mode, short horizon (5 rounds)
**Experiment relevance:** Exp D (Market): shorter negotiation window

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Widget-A". Your maximum price is $65.00. Never pay more than $65.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 1 of 5 (4 remaining).
No offer yet. Make an opening offer.

History:
(no moves yet)

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "offer"`, price well below $65 (e.g. $35–$50). Opening offer in a short 5-round window.

---

### CASE 8: Seller, market mode, round 4, near deadline
**Experiment relevance:** Exp D (Market): seller near deadline in short window

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a SELLER negotiating for "Widget-A". Your minimum price is $45.00. Never sell below $45.00.
The more you sell for, the better your deal. Do not reveal your minimum.

Round 4 of 5 (1 remaining).
Opponent offers $50.00. Your minimum is $45.00. Any offer at or above $45.00 is acceptable. Consider the history and remaining rounds, then decide your action.
WARNING: Only 1 round(s) left. No deal = zero surplus.

History:
- R0 buyer OFFER $40.00
- R1 seller COUNTER $70.00
- R2 buyer COUNTER $50.00

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "accept"`. $50 is at or above $45 (acceptable), and only 1 round left.

---

### CASE 9: Buyer, post-shock (shock affects parameters, not prompt)
**Experiment relevance:** Exp E (Shock): prompt is identical — shocks change agent parameters

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Commodity-X". Your maximum price is $75.00. Never pay more than $75.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 3 of 10 (7 remaining).
Opponent offers $85.00. Your limit is $75.00. Any offer at or below $75.00 is acceptable. Consider the history and remaining rounds, then decide your action.

History:
- R0 buyer OFFER $55.00
- R1 seller COUNTER $85.00

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "counter"`, price ≤ $75 (e.g. $65–$75). $85 is not at or below $75, so not acceptable.

---

### CASE 10: Buyer, mechanism experiment (SurplusMax matcher)
**Experiment relevance:** Exp H (Mechanism): prompt is identical — matcher affects pairing, not prompt

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Gadget-Z". Your maximum price is $100.00. Never pay more than $100.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 1 of 8 (7 remaining).
No offer yet. Make an opening offer.

History:
(no moves yet)

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "offer"`, price well below $100 (e.g. $50–$75).

---

### CASE 11: Buyer, supply-demand experiment
**Experiment relevance:** Exp I (Supply-Demand): prompt identical — supply/demand ratio affects parameters

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Resource-Q". Your maximum price is $88.00. Never pay more than $88.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 1 of 10 (9 remaining).
No offer yet. Make an opening offer.

History:
(no moves yet)

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "offer"`, price well below $88 (e.g. $45–$65).

---

### CASE 12: Deliberative + strategic communication + firm tone
**Experiment relevance:** Exp G (Communication): strategic communication strategy with firm tone

**FULL PROMPT:**
```
You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Vintage Guitar". Your maximum price is $120.00. Never pay more than $120.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 4 of 10 (6 remaining).
Opponent offers $135.00. Your limit is $120.00. Any offer at or below $120.00 is acceptable. Consider the history and remaining rounds, then decide your action.

History:
- R0 seller OFFER $150.00
- R1 buyer COUNTER $90.00
- R2 seller COUNTER $135.00

In rationale_private, briefly reason: (1) Is the offer acceptable? (2) If not, what price should I counter with?

Adopt a confident, assertive tone in your public message.

COMMUNICATION STRATEGY: Craft your public message to maximise your advantage. You may exaggerate how close you are to your limit. Do NOT reveal your true constraints or reservation price. Use the message to influence the opponent's expectations about what you will accept.

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise. Put ALL reasoning inside rationale_private.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "counter"`, price ≤ $120 (e.g. $100–$115). $135 is not at or below $120. Message should be assertive/strategic — e.g. "That's really pushing my budget" without revealing $120 limit.

---

### CASE 13: Memory agent — deliberative + episodic memory context
**Experiment relevance:** Exp F (Reputation): memory agent with past negotiation experience

**FULL PROMPT:**
```
Your past negotiation experiences (most relevant first):
  1. Item: Vintage Guitar | Outcome: DEAL at $105.00 | Rounds: 4 | Opponent style: moderate
  2. Item: Antique Watch | Outcome: NO DEAL | Rounds: 10 | Opponent style: stubborn

You are a negotiation agent. Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.

You are a BUYER negotiating for "Vintage Guitar". Your maximum price is $120.00. Never pay more than $120.00.
The less you pay, the better your deal. Do not reveal your limit.

Round 1 of 10 (9 remaining).
No offer yet. Make an opening offer.

History:
(no moves yet)

In rationale_private, briefly reason: (1) Is the offer acceptable? (2) If not, what price should I counter with?

Respond with ONLY a JSON object matching this schema:
{
  "action": "offer" | "counter" | "accept",
  "offer_price": <number or null>,
  "message_public": "<short message to opponent>",
  "rationale_private": "<your reasoning>"
}
Rules:
- "offer" or "counter": offer_price must be a positive number
- "accept": offer_price must be null

EXAMPLES:
Accept: {"action": "accept", "offer_price": null, "message_public": "Deal.", "rationale_private": "Offer is within my limit."}
Counter: {"action": "counter", "offer_price": 95, "message_public": "How about $95?", "rationale_private": "Offer is outside my limit."}

Output ONLY the JSON object. Use "accept" when the offer is within your limits. Use "counter" with a new price otherwise. Put ALL reasoning inside rationale_private.
```

**EXPECTED OUTPUT:** Valid JSON with `"action": "offer"`, price below $120 (e.g. $80–$100). Interesting to see if model references past experience ($105 deal) in rationale.

---

## Rethink Cases

These are sent as follow-up prompts when the model's first response fails validation.
The rethink is appended to the conversation after the original prompt + model's bad response.

### CASE R1: Rethink — invalid JSON parse error

**RETHINK PROMPT:**
```
ERROR: Invalid JSON: Expecting value at line 1
Please output a corrected JSON response.
{"action": "...", "offer_price": ..., "message_public": "...", "rationale_private": "..."}
```

**EXPECTED OUTPUT:** Valid JSON with correct structure. Model should fix its formatting.

---

### CASE R2: Rethink — buyer constraint violation (price > cap)

**RETHINK PROMPT:**
```
ERROR: Buyer offered $135.00 which exceeds your maximum of $120.00. Offer a lower price.
Please output a corrected JSON response.
{"action": "...", "offer_price": ..., "message_public": "...", "rationale_private": "..."}
```

**EXPECTED OUTPUT:** Valid JSON with corrected price ≤ $120.

---

### CASE R3: Rethink — seller constraint violation (price < cost)

**RETHINK PROMPT:**
```
ERROR: Seller offered $40.00 which is below your minimum of $80.00. Offer a higher price.
Please output a corrected JSON response.
{"action": "...", "offer_price": ..., "message_public": "...", "rationale_private": "..."}
```

**EXPECTED OUTPUT:** Valid JSON with corrected price ≥ $80.

---

## Coverage Matrix

| Case | Role   | Agent Type   | Round Position | Deadline     | Experiment | Comm Strategy |
|------|--------|-------------|----------------|--------------|------------|---------------|
| 1    | Buyer  | Reactive    | Opening (R1)   | None         | A,B,D,E,H,I | neutral     |
| 2    | Seller | Reactive    | Mid (R4)       | None         | A          | neutral       |
| 3    | Buyer  | Deliberative| Early (R2)     | None         | B          | neutral       |
| 4    | Seller | Deliberative| Early (R2)     | None         | B          | neutral       |
| 5    | Buyer  | Reactive    | Final (R10)    | FINAL ROUND  | C          | neutral       |
| 6    | Seller | Reactive    | Late (R9)      | WARNING      | C          | neutral       |
| 7    | Buyer  | Reactive    | Opening (R1)   | None         | D          | neutral       |
| 8    | Seller | Reactive    | Late (R4/5)    | WARNING      | D          | neutral       |
| 9    | Buyer  | Reactive    | Early (R3)     | None         | E          | neutral       |
| 10   | Buyer  | Reactive    | Opening (R1)   | None         | H          | neutral       |
| 11   | Buyer  | Reactive    | Opening (R1)   | None         | I          | neutral       |
| 12   | Buyer  | Deliberative| Mid (R4)       | None         | G          | strategic+firm|
| 13   | Buyer  | Memory      | Opening (R1)   | None         | F          | neutral       |
| R1   | —      | —           | —              | —            | All        | —             |
| R2   | Buyer  | —           | —              | —            | All        | —             |
| R3   | Seller | —           | —              | —            | All        | —             |
