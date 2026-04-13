# EventOps — AI Latency Optimizations

Six optimizations implemented to reduce AI response latency from ~10.7s average (23s+ tails) to significantly faster response times.

---

## A. Model Swap

The default model was `minimax/minimax-m2.5`, which is a capable but slower model on OpenRouter. Switching to `google/gemini-2.0-flash-001` targets a model specifically optimized for speed — it handles structured JSON extraction just as well but responds 2-5x faster. This is the single biggest latency reduction with zero code complexity.

**Files changed:** `app/config.py`

---

## B. Prompt Trimming

Every token in the system prompt costs time — the LLM has to "read" (prefill) the entire prompt before generating a single output token. The original prompt was ~3,500 tokens of verbose, repetitive rules (e.g., rules 4, 6, and 7 all explained vendor/payment logic in different ways with long examples). The condensed version preserves every behavioral rule but expresses them in ~1,400 tokens — tighter sentences, compact schema notation (`field*` instead of `field(req)`), and collapsed category aliases. Fewer input tokens means faster prefill.

**Files changed:** `app/services/llm_service.py`

---

## C. Split Dashboard Metrics

The AI Ops dashboard was showing a single "Avg Latency" of ~10,700ms, but this averaged together three very different operations: extractions (~3-12s), RAG queries (~7s), and embeddings (~471ms). The blended number made it impossible to tell what was actually slow. Now the dashboard shows per-type breakdowns (Extraction, RAG Query, Embedding) so you can pinpoint exactly where time is being spent and track improvements accurately.

**Files changed:** `app/schemas/admin.py`, `app/routers/admin.py`, `frontend/static/js/app.js`

---

## D. Compact Context Mode

Every extraction call injected the full event context into the prompt — up to 10 vendors with notes and contact info, 10 paid payments, 10 pending payments, completed tasks, sub-event times, and 15 document entries with metadata. Most of this detail is unnecessary for the LLM to make create-vs-update decisions. Compact mode sends only IDs and essential fields (name, category, amount, date) in a terse `ID|name|category` format, cutting context size by roughly 40-50% while preserving all the information the LLM actually needs.

**Files changed:** `app/services/context_service.py`, `app/routers/capture.py`

---

## E. Query Cache

When a user asks "show my payments" or "what vendors do I have", the system was making a full LLM API call every time — even if the same question was asked 30 seconds ago. The cache stores responses for read-only intents (`query` and `conversation`) for 5 minutes, keyed on the event ID and normalized input text. Repeated or identical questions return instantly from cache. State-changing intents (payments, tasks, vendors) are never cached since the underlying data changes.

**Files changed:** `app/routers/capture.py`

---

## F. SSE Streaming

Without streaming, the user stared at fake rotating "Working on it..." messages for 5-10 seconds with no real feedback. The new streaming endpoint uses OpenRouter's `stream: true` mode, sending Server-Sent Events as tokens arrive. The frontend shows "Eve is typing..." as soon as the first token arrives (~200-500ms), giving the user immediate confirmation that the system is working. The full structured result is sent as a final event once generation completes. If streaming fails for any reason, it automatically falls back to the standard non-streaming endpoint.

**Files changed:** `app/services/llm_service.py`, `app/routers/capture.py`, `frontend/static/js/app.js`
