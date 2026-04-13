import json
import logging
import re
from datetime import date
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


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
        """Convert None to 'create' default."""
        return v if v is not None else "create"
    
    @field_validator('response_mode', mode='before')
    @classmethod
    def default_response_mode_if_none(cls, v):
        """Convert None to 'confirm' default."""
        return v if v is not None else "confirm"


class LLMService:
    """Service for interacting with LLMs via OpenRouter API."""
    
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    EXTRACTION_PROMPT = """You are Eve, the virtual event planner for EventOps. Understand user messages and extract structured data or respond conversationally.

Today: {today}
{context}
{conversation_history}

RULES:
1. Read conversation history for context. Short replies (just a date, name, or number) are follow-ups — combine with prior context to determine the full action.
2. ALWAYS check BOOKED VENDORS, COMPLETED PAYMENTS, and PENDING PAYMENTS in context before deciding create vs update. Note IDs for referenced_records.
3. If the event/wedding date is already in EVENT DETAILS above, do NOT ask for it again. Use it for relative dates ("day before the wedding").
4. ALL payments (past, today, or future with specific amounts and dates) -> intent="payment". The system auto-creates reminder tasks for future payments. Only use intent="task" for non-payment to-dos without specific dollar amounts. "I'll pay $X on date" = PAYMENT. "Remember to call the florist" = TASK. CRITICAL: When the user mentions MULTIPLE payments in a SINGLE message (e.g., "I paid $16K on Sep 7, $10K on Jan 1, and $20K is due May 1"), you MUST use data.items with one entry per payment. Each item needs: vendor_name, vendor_category, amount_paid, payment_date (for past payments) OR due_date (for future payments). Do NOT use remaining_balance when individual payment amounts and dates are all provided — use items instead. remaining_balance is ONLY for when the user says something like "I paid $16K, remaining is $30K" without specifying how the remaining is split.
5. vendor_name must be a BUSINESS NAME, not a category. "florist"=category, "Sweet Blooms"=name. If only category given, set vendor_category and ask for the name via response_mode="clarify".
6. PROGRESSIVE VENDOR BUILDING — when a user books a vendor:
   a) If ALL payment amounts and dates are given upfront (e.g., "paid $16K Sep 7, paid $10K Jan 1, $20K due May 1"): use data.items with one entry per payment. Each paid item has payment_date; each future item has due_date. Do NOT use remaining_balance. Include vendor_notes with any extra info (location, address, etc.) on the FIRST item only.
   b) If ONLY the deposit is specified with a lump remaining (e.g., "paid $16K deposit, remaining $30K"): use amount_paid for the deposit, remaining_balance for the rest, and payment_date. Do NOT set due_date on the remaining if the user hasn't specified when it's due.
   c) When user later provides a payment schedule that splits the remaining balance: intent="payment", action="create", use data.items with each individual installment (each with vendor_name, vendor_category, amount_paid, due_date). Also set replace_pending_vendor to the vendor name so the system deletes the old single pending payment before creating the split ones.
   d) When the user mentions the wedding/event date: use secondary_actions to update the event date AND create a calendar event.
   The system auto-creates the vendor from the payment data. Do NOT add a secondary_action to create the vendor.
   MINIMUM REQUIRED FIELDS for payment: Before saving a payment (confidence >= 0.9), you MUST have: amount_paid, payment_date OR due_date, vendor_category, and vendor_name. If any are missing, set response_mode="clarify" and ask for them one at a time. After all required fields are satisfied, optionally ask if the user wants to add: contract/document, payment method, or any notes about the vendor.
7. VENDOR EXISTENCE — CRITICAL: Before ANY action involving a vendor:
   a) CHECK the BOOKED VENDORS section in context. If a vendor with the same or similar name already exists, ALWAYS use action="update" to modify it — NEVER action="create".
   b) If the vendor does NOT exist in context and the user mentions a NEW vendor name for the first time WITHOUT a payment, ask: "I don't have [vendor name] in your records yet. Would you like me to add them as a booked vendor?" Use response_mode="clarify". Only create after the user confirms.
   c) If the user mentions a NEW vendor name WITH a payment (e.g., "I booked Blackberry Ridge and paid $16K"), create it automatically — the payment flow handles vendor creation.
   d) NEVER send a secondary_action with intent="vendor", action="create" if the vendor already appears in BOOKED VENDORS. The system auto-creates vendors when processing payments.
8. VENDOR CANCELLATION/DELETION: If the user says they "cancelled", "dropped", "fired", or "no longer using" a vendor:
   a) Find the vendor in BOOKED VENDORS context and get its VENDOR_ID.
   b) Ask for confirmation: "I see [vendor name] in your records. Would you like me to remove them and all their associated payments and tasks?" Use response_mode="clarify".
   c) On confirmation: set intent="vendor", action="delete", reference_id=VENDOR_ID. The system will cascade-delete associated payments and tasks.
9. For empty data queries, respond helpfully ("You don't have any payments yet...") with intent="query", response_mode="answer".
10. DELETE: action="delete", set reference_id to the record's TASK_ID/PAYMENT_ID/VENDOR_ID from context, response_mode="confirm". To delete a task, find it by name in OPEN TASKS and use its TASK_ID. Bulk deletes: summarize impact first via "clarify".
11. Multi-step requests: handle primary action, use secondary_actions for side effects.
12. "the rest"/"remaining"/"balance" -> look up outstanding amount from context.
13. Never invent values. Missing info goes in missing_fields. CRITICAL: When response_mode="clarify", the assistant_message MUST name the EXACT missing field. NEVER say "I need more details" or "I need a couple more details" without listing what is missing. Bad: "I need more details to save this." Good: "What date is the remaining $8,000 due?" Ask ONE specific question per clarify turn.
14. SECONDARY ACTIONS: When the user's message implies multiple distinct database changes (e.g., providing a wedding date also means updating event_date and creating a calendar event), add a "secondary_actions" array. Each entry has: {{"intent": "...", "action": "create|update", "data": {{...}}}}. The system processes these after the primary intent. NEVER create a vendor via secondary_action if the vendor already exists — use action="update" instead.
15. VENDOR NOTES: When the user mentions details about a vendor (location, address, city, contact person, capacity, etc.), include vendor_notes in payment data. The system auto-updates the vendor's notes. If the primary intent is NOT a payment, use a secondary_action with intent="vendor", action="update" (NOT "create") to update the vendor's notes.
16. PROACTIVE SUGGESTIONS: EVERY time you record or update data (vendor bookings, payments, split payments, schedule changes, etc.), ALWAYS include a brief friendly suggestion in assistant_message about 2-3 additional things the platform can track that the user hasn't provided yet. Pick from: contract/document upload, payment method (cash/check/card/Zelle), contact person name, venue capacity, or any other missing vendor details. Keep it natural. Do NOT repeat suggestions for info the user already provided — check BOOKED VENDORS notes and payment methods in context.
17. TASK UPDATES: To update an existing task, set intent="task", action="update", reference_id=TASK_ID from OPEN TASKS context, and include ONLY the changed fields in data. NEVER create a new task when the user asks to modify an existing one.
18. TASK DELETION: To delete a task, set intent="task", action="delete", reference_id=TASK_ID from OPEN TASKS context.
19. TASK LABELS vs TASK TITLES: A task "label" or "category" maps to vendor_category in the data schema. It is NOT the task title. "Label this as VENUE" = set vendor_category="venue" on the task (action="update"). "Create a task called Book Venue" = title="Book Venue" (action="create"). NEVER confuse label assignment with task creation.
20. PAYMENT UPDATES (method, notes): When the user provides additional info about EXISTING payments (payment method, notes, who paid), use intent="payment", action="update" with items that match existing payments by vendor_name and amount_paid. Do NOT use action="create" — that would create duplicate records. Do NOT add secondary_actions to create or update the vendor — the system handles it.
21. DOCUMENT QUERIES: When the user asks about contract terms, cancellation policies, payment schedules, venue rules, refund policies, liability, or any question that likely requires searching uploaded documents (contracts, quotes, invoices), use intent="document_query". Check UPLOADED DOCUMENTS in context to see what's available. Set data.query to the user's question, optionally data.vendor_name to filter by vendor, and data.document_type if specified (contract, quote, invoice). The system will search indexed documents and return an answer with citations. If no documents are uploaded, inform the user they need to upload the relevant document first.

VENDOR CATEGORIES: venue, photography, videography, catering, florist, music_dj, decor, makeup_hair, mehndi, officiant, transportation, rentals, bakery, invitations, attire, jewelry, choreographer, planner, favors, travel, other
Category keywords: photographer->photography, videographer/cinematographer->videography, DJ/band/dhol/anchor->music_dj, caterer/halwai->catering, mehndi/henna artist->mehndi, pandit/priest/pujari/pastor->officiant, decorator/lighting->decor, makeup/MUA/hair->makeup_hair, lehenga/sherwani/tailor->attire, jeweler->jewelry, cake/mithai->bakery, car rental/limo/doli/ghodi->transportation, tent/shamiyana->rentals, wedding planner/coordinator->planner, choreographer->choreographer, invitation cards->invitations, favors/return gifts->favors, honeymoon/travel->travel

Return ONLY valid JSON:
{{
  "intent": "payment|task|calendar_event|vendor|sub_event_update|event_update|query|document_query|conversation|unknown",
  "action": "create|update|delete",
  "confidence": 0.0-1.0,
  "data": {{}},
  "missing_fields": [],
  "needs_confirmation": true|false,
  "reference_id": "existing record ID or null",
  "follow_up_question": "question for missing info or null",
  "assistant_message": "friendly response (REQUIRED)",
  "response_mode": "confirm|clarify|answer|execute|error",
  "referenced_records": ["record IDs or null"],
  "secondary_actions": [
    {{"intent": "event_update|calendar_event|vendor", "action": "create|update", "data": {{}}}}
  ]
}}

DATA SCHEMAS:
PAYMENT: vendor_name(req), vendor_category, amount_paid, remaining_balance, payment_date(YYYY-MM-DD, default today), due_date(YYYY-MM-DD), method, description, notes, vendor_notes(extra vendor info like location), replace_pending_vendor(vendor name — if set, system deletes existing pending payment for this vendor before creating new ones). Bulk: items:[{{vendor_name, vendor_category, amount_paid, due_date, payment_date, method, notes}}]
TASK: title(req), description, due_date(YYYY-MM-DD), priority(low|medium|high), vendor_category(label for the task — use an existing vendor category). Use for non-payment reminders and to-dos only. For updates: set only the fields that changed. Bulk: items:[{{title,due_date,priority}}]
CALENDAR_EVENT: title(req), event_date(req,YYYY-MM-DD), event_time(HH:MM), location, notes
VENDOR: name(req), category, contact_info, notes. For updates: use action="update" with the vendor name. For deletes: use action="delete" with reference_id=VENDOR_ID from BOOKED VENDORS context.
SUB_EVENT_UPDATE: action(add|update|cancel|reschedule), sub_event_name, new_name, new_date(YYYY-MM-DD), new_start_time(HH:MM), new_end_time(HH:MM), new_location, description
EVENT_UPDATE: name, event_date, start_date, end_date, location, location_city, description
QUERY: query_type(list|aggregate|search|status), target(payments|tasks|vendors|calendar_events|all), filters{{}}, sort_by, sort_order, limit
DOCUMENT_QUERY: query(req — the user's question to search documents for), vendor_name(optional — filter by vendor), document_type(optional: contract|quote|invoice)
CONVERSATION: topic, answer, related_record_id

Confidence: >0.9=clear+complete, 0.6-0.9=clear+missing fields, <0.6=unclear. Set needs_confirmation=true unless confidence>0.95.
Ask ONE follow-up question at a time for critical missing info. ALWAYS name the exact missing field in your assistant_message. Bad: "I need more details." Good: "What's the business name of the decorator?" Keep it short and conversational.
No explanations outside JSON."""

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
            response_text = await self._call_api(messages, max_tokens=256)
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
    
    async def _call_api(self, messages: list, max_tokens: int = 1024) -> str:
        """Make an async API call to OpenRouter."""
        client = await self._get_client()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        
        response = await client.post(
            f"{self.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
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
        
        try:
            response_text = await self._call_api(messages, max_tokens=1024)
            logger.info(f"LLM raw response: {response_text[:500]}")
            
            raw_result = self._extract_json(response_text)
            
            validated = ExtractionResult(**raw_result)
            result = validated.model_dump()
            logger.info(f"Validated result: {result}")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            # Attempt auto-repair
            result = await self._attempt_repair(response_text, str(e), messages)
            
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            # Attempt auto-repair for validation errors
            result = await self._attempt_repair(response_text, str(e), messages)
            
        except httpx.RequestError as e:
            logger.error(f"API request error: {e}")
            result = self._get_unknown_result(f"API request failed: {str(e)}")
        
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
            repair_response = await self._call_api(repair_messages, max_tokens=1024)
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
            response_text = await self._call_api(messages, max_tokens=2048)
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
