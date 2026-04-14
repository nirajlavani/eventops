import json
import logging
import re
import time
from datetime import date
from enum import Enum
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    """Selects which model tier to use for a given LLM call."""
    FAST = "fast"
    BALANCED = "balanced"
    STRONG = "strong"


class ExtractionResult(BaseModel):
    """Validated extraction result from LLM."""
    
    intent: Literal["payment", "task", "calendar_event", "vendor", "sub_event_update", "event_update", "query", "document_query", "conversation", "unknown"]
    action: Literal["create", "update", "delete"] = "create"
    confidence: float = Field(ge=0.0, le=1.0)
    data: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    reference_id: Optional[str] = None
    follow_up_question: Optional[str] = None
    assistant_message: Optional[str] = None
    response_mode: Literal["confirm", "clarify", "answer", "execute", "error"] = "confirm"
    referenced_records: Optional[list[str]] = None
    secondary_actions: Optional[list[dict]] = None
    
    @field_validator('action', mode='before')
    @classmethod
    def default_action_if_none(cls, v):
        """Normalize action to a valid enum value."""
        if v is None or v not in ("create", "update", "delete"):
            return "create"
        return v
    
    @field_validator('response_mode', mode='before')
    @classmethod
    def default_response_mode_if_none(cls, v):
        """Convert None to 'confirm' default."""
        return v if v is not None else "confirm"


class LLMService:
    """Service for interacting with LLMs via OpenRouter API."""
    
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    EXTRACTION_PROMPT = """You are Eve, EventOps virtual event planner. Extract structured data from user messages or respond conversationally.

TONE: Write assistant_message in warm, conversational English — like a friendly planner confirming what they heard. NEVER reply with just "OK." or "Done." Instead, reflect back the key details naturally. Examples:
- "Got it! I've recorded your $10,000 payment to Rani Events for decor, and the remaining $10,000 is due by October 28th."
- "Added a venue site tour to your task list for May 13th at noon!"
- "I've set up Lauren Vaughan Photography as your photographer. Exciting!"
Keep it to 1-2 sentences. Don't over-explain or repeat every field — just confirm the highlights.

Today: {today}
{context}
{conversation_history}

RULES:
1. Short replies (date, name, number) providing missing data are follow-ups — combine with conversation history. But simple acknowledgments ("yep", "cool", "sounds good", "great", "ok", "thanks", etc.) are NOT follow-ups — they are conversation. Use intent="conversation".
2. Check BOOKED VENDORS/PAYMENTS in context before deciding create vs update. Note IDs in referenced_records.
3. Don't re-ask for event date if already in EVENT DETAILS. Use it for relative dates.
4. Money with amounts/dates = intent="payment". System auto-creates reminder tasks for future payments. Non-payment to-dos = intent="task". Multiple payments in one message: use data.items array, one entry per payment with vendor_name, vendor_category, amount_paid, payment_date or due_date. Only use remaining_balance when user gives a lump sum remainder without splitting. When creating records (task, payment, calendar_event, vendor), ALWAYS use response_mode="execute" — never "answer".
5. vendor_name must be a business name, not a category. Category only → set vendor_category, response_mode="clarify", ask for business name. EXCEPTION: if user says something like "no vendor", "just for records", "no specific vendor", or gives a placeholder name (e.g. "India", "DIY", "self") — accept it as-is. Not every purchase has a formal vendor.
6. Payment required fields (for confidence>=0.9): amount_paid, payment_date OR due_date, vendor_category, vendor_name. Missing any → response_mode="clarify". Deposit+remaining: use amount_paid + remaining_balance. Later split: use items + replace_pending_vendor=vendor name. If user explicitly says "just for record keeping" or similar, lower the bar — accept whatever they gave and don't push for missing optional fields.
7. Vendor existence: if vendor in BOOKED VENDORS → action="update". New vendor without payment → ask to confirm via "clarify". New vendor with payment → auto-create. Never duplicate via secondary_action.
8. Vendor deletion ("cancelled","dropped","fired"): find VENDOR_ID, confirm via "clarify", then intent="vendor", action="delete", reference_id=VENDOR_ID. Cascade-deletes payments/tasks.
9. Empty data queries → respond helpfully with intent="query", response_mode="answer". Acknowledgments and dismissals after a completed action ("yes", "yep", "yep all good", "cool", "sounds good", "perfect", "great", "thanks", "ok", "no", "nope", "nothing", "that's it", "just save it", "save as is", "done", "good", "awesome", "nice") → intent="conversation", response_mode="answer". Respond warmly and briefly. NEVER interpret these as a create or update action.
10. DELETE: action="delete", reference_id from context, response_mode="confirm". Bulk → summarize via "clarify".
11. Multi-step: primary action + secondary_actions array for side effects. Wedding date → secondary_actions for event_update + calendar_event. Never create vendor via secondary_action if already exists. When a task has a specific date+time (e.g. "venue tour on May 13 at 12pm"), create the task as primary AND add a secondary_action with intent="calendar_event" to put it on the calendar.
12. "the rest"/"remaining"/"balance" → look up outstanding from context.
13. Never invent values. Missing → missing_fields. Clarify must name the EXACT missing field. Ask ONE question per turn. EXCEPTION for tasks: derive the title from the user's description — e.g. "I have a venue site tour on May 13th at 12pm" → title="Venue site tour", due_date="2026-05-13". Do NOT ask for a title or date when the user already described them in natural language. Only clarify truly missing info.
14. Vendor notes (location, address, capacity, etc.) → vendor_notes in payment data or secondary_action with intent="vendor", action="update".
15. After recording data, you may briefly mention 1-2 optional things the user could add (contract, payment method, etc.) BUT only once. If the user declines, says "no", "nope", "that's it", "save it", "nothing else", or anything dismissive — STOP ASKING and confirm the save with intent="conversation", response_mode="answer". Never re-ask for something the user already declined. Respect the user's intent to be done.
16. Task updates: action="update", reference_id=TASK_ID, only changed fields. Task label/category = vendor_category (not title). Deletion: action="delete", reference_id=TASK_ID.
17. Payment updates (method, notes): action="update" with items matching by vendor_name+amount_paid. Never action="create" for existing payments.
18. Document queries: If the user asks ANYTHING about a contract, document, quote, invoice, agreement, or uploaded file → intent="document_query". This includes questions about terms, pricing, line items, costs, policies, copyright, ownership, cancellation, what's included, timelines, or any factual detail. Keywords that ALWAYS trigger document_query: "contract", "document", "quote", "invoice", "agreement", "what does it say", "does the contract mention". Match loosely: "photography contract" matches a doc named "LAUREN VAUGHAN PHOTOGRAPHY Contract.pdf". Set data.query=the user's question, data.vendor_name=vendor if identifiable from the DOCS list. Check DOCS in context — if ANY docs exist, use document_query. No docs at all → tell user to upload first. NEVER respond with intent="unknown" or intent="conversation" when the user is asking about a document.

CATEGORIES: venue|photography|videography|catering|florist|music_dj|decor|makeup_hair|mehndi|officiant|transportation|rentals|bakery|invitations|attire|jewelry|choreographer|planner|favors|travel|other
Aliases: photographer→photography, DJ/band/dhol→music_dj, caterer/halwai→catering, henna→mehndi, pandit/priest→officiant, decorator/lighting→decor, MUA→makeup_hair, lehenga/sherwani→attire, cake/mithai→bakery, limo/doli→transportation, tent/shamiyana→rentals

Return ONLY valid JSON:
{{"intent":"payment|task|calendar_event|vendor|sub_event_update|event_update|query|document_query|conversation|unknown","action":"create|update|delete","confidence":0.0-1.0,"data":{{}},"missing_fields":[],"needs_confirmation":true|false,"reference_id":null,"follow_up_question":null,"assistant_message":"(REQUIRED — must be a warm, conversational sentence confirming what you did. NEVER just 'OK.' or 'Done.')","response_mode":"confirm|clarify|answer|execute|error","referenced_records":null,"secondary_actions":null}}

SCHEMAS:
PAYMENT: vendor_name*, vendor_category, amount_paid, remaining_balance, payment_date(YYYY-MM-DD), due_date, method, description, notes, vendor_notes, replace_pending_vendor. Bulk: items:[{{vendor_name,vendor_category,amount_paid,due_date,payment_date,method,notes}}]
TASK: title*, description, due_date, priority(low|medium|high), vendor_category. Updates: only changed fields. Bulk: items:[{{title,due_date,priority}}]
CALENDAR_EVENT: title*, event_date*(YYYY-MM-DD), event_time(HH:MM), location, notes
VENDOR: name*, category, contact_info, notes. Delete: reference_id=VENDOR_ID
SUB_EVENT_UPDATE: action(add|update|cancel|reschedule), sub_event_name, new_name, new_date, new_start_time, new_end_time, new_location, description
EVENT_UPDATE: name, event_date, start_date, end_date, location, location_city, description
QUERY: query_type(list|aggregate|search|status), target(payments|tasks|vendors|calendar_events|all), filters{{}}, sort_by, sort_order, limit
DOCUMENT_QUERY: query*, vendor_name, document_type(contract|quote|invoice)
CONVERSATION: topic, answer, related_record_id

Confidence: >0.9=complete, 0.6-0.9=missing fields, <0.6=unclear. needs_confirmation=false only if confidence>0.95.
No explanations outside JSON.

REMINDER: assistant_message must sound like a friendly human planner — e.g. "I've added your meeting with DJ Chirag to the calendar for Wednesday at 5pm!" NEVER "OK." or "Done." This is critical."""

    PLANNING_PROMPT = """You are Eve, the virtual event planner for EventOps.

Today's date is: {today}

Your task is to analyze the user's event data and provide prioritized recommendations.

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "Brief overview of the current state and priorities",
  "priority_items": [
    {{
      "category": "payment | task | calendar_event",
      "title": "Item title",
      "reason": "Why this is a priority",
      "urgency": "immediate | this_week | upcoming",
      "due_date": "YYYY-MM-DD or null"
    }}
  ],
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2"
  ]
}}

Focus on:
1. Overdue items (highest priority)
2. Items due this week
3. High-priority tasks
4. Upcoming payments
5. Calendar events that need preparation

Be concise and actionable. Limit to top 5-7 priority items and 3-5 recommendations."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model
        self.client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                timeout=60.0,
                trust_env=False,
            )
        return self.client

    def _resolve_model(self, tier: ModelTier) -> str:
        """Pick the model identifier based on the requested tier."""
        if tier == ModelTier.FAST and settings.llm_model_fast:
            return settings.llm_model_fast
        if tier == ModelTier.STRONG and settings.llm_model_strong:
            return settings.llm_model_strong
        return self.model
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        
        if text.startswith("{") and text.endswith("}"):
            return json.loads(text)
        
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            return json.loads(text[brace_start:brace_end + 1])
        
        raise json.JSONDecodeError("No JSON found", text, 0)
    
    def _get_unknown_result(self, error: Optional[str] = None) -> dict:
        """Return a safe unknown result instead of hallucinating."""
        result = {
            "intent": "unknown",
            "action": "create",
            "confidence": 0.0,
            "data": {},
            "missing_fields": [],
            "needs_confirmation": True,
            "reference_id": None,
            "follow_up_question": None,
            "assistant_message": "I'm not sure I understood that. Could you rephrase or give me more details?",
            "response_mode": "error",
            "referenced_records": None,
        }
        if error:
            result["error"] = error
        return result
    
    ROUTING_PROMPT = """You are a fast intent classifier for an event planning app.

Classify the user's message into one of these intents:
- payment: Recording a payment that WAS MADE (past tense)
- task: Creating a to-do item or future payment reminder
- calendar_event: Scheduling a meeting or event
- vendor: Adding or updating vendor info
- sub_event_update: Modifying wedding sub-events (ceremony, reception, etc.)
- event_update: Changing event details (date, location, name)
- query: Asking a question about existing data
- conversation: Follow-up, clarification, or general chat
- unknown: Unclear intent

Also determine the action:
- create: Adding something new
- update: Modifying existing record
- delete: Removing a record

Today's date: {today}

Return ONLY this JSON:
{{"intent": "...", "action": "...", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

    async def route_intent(
        self,
        user_input: str,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        Fast intent routing step (Step 1 of two-step processing).
        
        This is a lightweight classification that determines intent and action
        before the full extraction step.
        
        Args:
            user_input: The user's message
            conversation_history: Recent conversation context
            
        Returns:
            Dict with intent, action, confidence, and reasoning
        """
        today = date.today().isoformat()
        
        messages = [
            {"role": "system", "content": self.ROUTING_PROMPT.format(today=today)},
        ]
        
        # Add conversation context if available
        if conversation_history:
            for msg in conversation_history[-4:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        messages.append({"role": "user", "content": user_input})
        
        try:
            response_text, _usage = await self._call_api(
                messages, max_tokens=256, tier=ModelTier.FAST,
            )
            result = self._extract_json(response_text)
            return {
                "intent": result.get("intent", "unknown"),
                "action": result.get("action", "create"),
                "confidence": result.get("confidence", 0.5),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Routing error: {e}")
            return {
                "intent": "unknown",
                "action": "create",
                "confidence": 0.0,
                "reasoning": "Routing failed",
            }
    
    async def _call_api(
        self,
        messages: list,
        max_tokens: int = 1024,
        tier: ModelTier = ModelTier.BALANCED,
    ) -> tuple[str, dict]:
        """Make an async API call to OpenRouter.

        Returns (content, usage_dict) where usage_dict contains token counts
        and latency so callers can record metrics.
        """
        client = await self._get_client()
        resolved_model = self._resolve_model(tier)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        logger.info("LLM call: tier=%s model=%s max_tokens=%d", tier.value, resolved_model, max_tokens)
        t0 = time.perf_counter()
        response = await client.post(
            f"{self.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        response.raise_for_status()

        data = response.json()
        usage = data.get("usage", {})
        usage_dict = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "latency_ms": latency_ms,
            "model": data.get("model", resolved_model),
            "tier": tier.value,
        }
        return data["choices"][0]["message"]["content"], usage_dict
    
    async def _call_api_stream(
        self,
        messages: list,
        max_tokens: int = 1024,
        tier: ModelTier = ModelTier.BALANCED,
    ):
        """Stream tokens from OpenRouter, yielding each content delta.

        Yields (delta_text, None) for intermediate chunks and
        ("", usage_dict) for the final chunk.
        """
        client = await self._get_client()
        resolved_model = self._resolve_model(tier)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
        }

        logger.info("LLM stream: tier=%s model=%s max_tokens=%d", tier.value, resolved_model, max_tokens)
        t0 = time.perf_counter()
        async with client.stream(
            "POST",
            f"{self.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload_str = line[6:]
                if payload_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    yield text, None

        latency_ms = int((time.perf_counter() - t0) * 1000)
        yield "", {"latency_ms": latency_ms, "model": resolved_model, "tier": tier.value}

    async def extract_intent_and_data(
        self,
        user_input: str,
        context: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        Extract intent and structured data from natural language input.
        
        Args:
            user_input: The natural language text from user
            context: Optional context string with existing records info
            conversation_history: Optional list of recent conversation messages
        
        Returns a validated dict with:
        - intent: payment | task | calendar_event | vendor | conversation | unknown
        - action: create | update
        - confidence: 0.0 to 1.0
        - data: intent-specific fields
        - missing_fields: list of required but missing fields
        - needs_confirmation: whether user must confirm
        - reference_id: ID of existing record to update (if action=update)
        - assistant_message: natural response message
        """
        today = date.today().isoformat()
        context_str = context or "No existing records for context."
        
        history_str = ""
        if conversation_history and len(conversation_history) > 0:
            history_lines = ["Recent conversation (for context):"]
            for msg in conversation_history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    history_lines.append(f"User: {content}")
                else:
                    history_lines.append(f"Assistant: {content}")
            history_str = "\n".join(history_lines)
        else:
            history_str = "No previous conversation."
        
        system_prompt = self.EXTRACTION_PROMPT.format(
            today=today, 
            context=context_str,
            conversation_history=history_str
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        
        usage_info: dict = {}
        try:
            response_text, usage_info = await self._call_api(
                messages, max_tokens=1024, tier=ModelTier.BALANCED,
            )
            logger.info(f"LLM raw response: {response_text[:500]}")

            raw_result = self._extract_json(response_text)

            validated = ExtractionResult(**raw_result)
            result = validated.model_dump()
            logger.info(f"Validated result: {result}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            result = await self._attempt_repair(response_text, str(e), messages)

        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            result = await self._attempt_repair(response_text, str(e), messages)

        except httpx.RequestError as e:
            logger.error(f"API request error: {e}")
            result = self._get_unknown_result(f"API request failed: {str(e)}")

        result["_usage"] = usage_info
        return result
    
    async def _attempt_repair(
        self, 
        invalid_response: str, 
        error_message: str,
        original_messages: list
    ) -> dict:
        """
        Attempt to repair an invalid LLM response by asking the model to fix it.
        
        Args:
            invalid_response: The malformed response text
            error_message: The error that occurred
            original_messages: The original conversation messages
        
        Returns:
            Repaired result dict or unknown result if repair fails
        """
        logger.info("Attempting auto-repair of invalid response")
        
        repair_prompt = f"""Your previous response was invalid. Error: {error_message}

Invalid response:
{invalid_response[:1000]}

Please fix your response and return ONLY valid JSON with these required fields:
- intent: one of (payment, task, calendar_event, vendor, sub_event_update, event_update, query, conversation, unknown)
- action: one of (create, update, delete)
- confidence: number between 0.0 and 1.0
- data: object with extracted fields
- missing_fields: array of strings
- needs_confirmation: boolean
- reference_id: string or null
- follow_up_question: string or null
- assistant_message: string (REQUIRED - friendly message for user)
- response_mode: one of (confirm, clarify, answer, execute, error)
- referenced_records: array of strings or null
- secondary_actions: array of objects or null (each with intent, action, data)

Return ONLY the corrected JSON, no explanations."""

        repair_messages = original_messages + [
            {"role": "assistant", "content": invalid_response},
            {"role": "user", "content": repair_prompt}
        ]
        
        try:
            repair_response, _usage = await self._call_api(
                repair_messages, max_tokens=1024, tier=ModelTier.BALANCED,
            )
            logger.info(f"Repair response: {repair_response[:500]}")

            raw_result = self._extract_json(repair_response)
            validated = ExtractionResult(**raw_result)
            result = validated.model_dump()
            logger.info("Auto-repair successful")
            return result

        except Exception as repair_error:
            logger.error(f"Auto-repair failed: {repair_error}")
            return self._get_unknown_result("Response could not be repaired")
    
    async def generate_planning_response(
        self,
        query: str,
        context: dict,
    ) -> dict:
        """
        Generate AI planning recommendations based on event context.
        
        Args:
            query: User's planning query
            context: Dict containing tasks, payments, calendar_events data
        
        Returns:
            Dict with summary, priority_items, and recommendations
        """
        today = date.today().isoformat()
        system_prompt = self.PLANNING_PROMPT.format(today=today)
        
        context_str = json.dumps(context, indent=2, default=str)
        user_message = f"""Query: {query}

Event Context:
{context_str}

Based on this context, what should I focus on?"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        try:
            response_text, _usage = await self._call_api(
                messages, max_tokens=2048, tier=ModelTier.STRONG,
            )
            result = self._extract_json(response_text)
        except json.JSONDecodeError:
            result = {
                "summary": "Unable to generate planning recommendations at this time.",
                "priority_items": [],
                "recommendations": ["Please try again or check your event data."],
            }
        except httpx.RequestError as e:
            result = {
                "summary": f"API request failed: {str(e)}",
                "priority_items": [],
                "recommendations": ["Please check your network connection and try again."],
            }

        return result
    
    async def close(self):
        """Close the HTTP client."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()


def get_llm_service() -> LLMService:
    """Get LLM service instance."""
    return LLMService()
