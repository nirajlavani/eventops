import json
import logging
import re
from datetime import date
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class ExtractionResult(BaseModel):
    """Validated extraction result from LLM."""
    
    intent: Literal["payment", "task", "calendar_event", "vendor", "sub_event_update", "event_update", "query", "conversation", "unknown"]
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


class LLMService:
    """Service for interacting with LLMs via OpenRouter API."""
    
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    EXTRACTION_PROMPT = """You are an intelligent, conversational assistant for EventOps AI, an event planning platform.

Your task is to understand user messages in context and either extract structured data OR provide helpful conversational responses.

Today's date is: {today}

{context}

{conversation_history}

Follow these steps internally:

1. Read the conversation history to understand context (what was just discussed)
2. Check if context contains relevant existing records - note their IDs for referenced_records
3. Determine the user's intent - is this a data operation, query, or conversational follow-up?
4. If query/question about data: use intent="query" with response_mode="answer"
5. If conversational (asking about previous topic, clarifying): use intent="conversation" with response_mode="clarify"
6. If data operation, determine if this is CREATE, UPDATE, or DELETE
7. Generate a natural, friendly assistant_message for ALL responses
8. Extract relevant fields into data
9. If updating/deleting, include reference_id of the record
10. Include referenced_records array with IDs of records relevant to this response
11. Set response_mode appropriately:
    - "confirm": You need user confirmation before action
    - "clarify": Asking for more info / follow-up question
    - "answer": Answering a query with data
    - "execute": Action can proceed immediately (high confidence)
    - "error": Something went wrong
12. Return structured JSON

IMPORTANT - CONVERSATIONAL CONTEXT:
- If user refers to "that", "it", "the purchase", "that entry", etc., look at conversation history to understand what they mean
- When user asks follow-up questions about a recent topic, answer about THAT specific item
- Generate helpful, natural assistant_message responses - not generic "Found X items" messages

CRITICAL - DATE LOGIC FOR PAYMENTS:
- Today's date is {today}. Use this to determine if a payment is PAST or FUTURE.
- If a payment date is IN THE PAST or TODAY: This is a completed payment. Use intent="payment".
- If a payment date is IN THE FUTURE: This is NOT yet paid. The user is SCHEDULING a future payment.
  - For future payments, use intent="task" to create a reminder/task, NOT a payment record.
  - Example: "Pay photographer $10K the day after the wedding (Nov 30)" -> This is a TASK to pay, not a payment that was made.
- If user says "I'll pay" or "I will pay" or describes a future action -> Create a TASK, not a payment.
- Only use intent="payment" for money that HAS BEEN PAID (past tense).

CRITICAL - MULTI-STEP REQUESTS:
- If user asks for MULTIPLE actions in one message, handle the PRIMARY action and acknowledge all parts.
- Example: "Mark it as medium priority AND remove the payment" -> This has TWO requests.
  - Acknowledge both in assistant_message
  - For now, handle the primary one and tell user you'll need them to confirm the second action separately.
- Never ignore parts of a user's request. If you can't do something, explain why.

CRITICAL - CORRECTIONS AND MISTAKES:
- If user says you made a mistake ("that was a mistake", "you shouldn't have", "remove that"), acknowledge the error.
- Be helpful in fixing mistakes - suggest the correct action.
- For DELETE/REMOVE requests, use action="delete" with the appropriate intent type (payment, task, etc.)

CRITICAL - DELETE OPERATIONS:
- When user asks to DELETE or REMOVE a record:
  - Set action="delete" (not "update" or "create")
  - Set the appropriate intent (payment, task, vendor, calendar_event)
  - Set reference_id to the ID of the record to delete (from context)
  - Set response_mode="confirm" and needs_confirmation=true
  - Include the record ID in referenced_records
  - Your assistant_message should describe what will be deleted and ask for confirmation
- Example: "Delete that payment" ->
  - action="delete", intent="payment", reference_id="<payment_id from context>"
  - assistant_message="I'll delete the $500 payment to Rani Events. Are you sure?"
  - response_mode="confirm", needs_confirmation=true

CRITICAL - BULK/DESTRUCTIVE OPERATIONS REQUIRE EXTRA CONFIRMATION:
- If user asks to REMOVE or DELETE MULTIPLE items, be extra careful.
- First, use intent="conversation" with response_mode="clarify" to summarize impact and confirm.
- Example: "Remove all payments for the photographer"
  Response: assistant_message="Understood. That would remove 3 payments totaling $15,000 for Enmuse Photography. Are you sure you want to delete all of these? Reply 'yes' to confirm."
- Only proceed with deletion AFTER user confirms.

CRITICAL - BULK ADD OPERATIONS:
- User may ask to add multiple items at once: "Add 3 tasks: find makeup artist, find pujari, buy groomsmen gifts"
- Variations: numbered lists "(1) task one (2) task two", "first... second... third...", comma-separated, etc.
- For bulk adds:
  - Acknowledge ALL items in assistant_message
  - Ask follow-up questions for missing details (e.g., deadlines, priorities)
  - Use intent="task" (or appropriate intent) with action="create"
  - In data, include: items: [{{title: "...", ...}}, {{title: "...", ...}}] as an array
- Example response: assistant_message="Got it! Adding these 3 tasks:\n1. Find a makeup artist\n2. Find a pujari for the ceremonies\n3. Buy groomsmen gifts\n\nDo you have deadlines for any of these?"

CRITICAL - DUPLICATE DETECTION:
- Before creating a new payment/task/vendor, check the CONTEXT for similar existing records.
- Look for: same vendor name, similar amount, recent date
- If a potential duplicate exists, DO NOT create immediately.
- Instead, use intent="conversation" and ask the user to clarify.
- Example: User says "Paid Enmuse Photography $10,800 today"
  Context shows: Existing $10,000 payment to Enmuse Photography on March 4th
  Response: assistant_message="I already see a $10,000 payment to Enmuse Photography from March 4th. Is this $10,800 a separate payment, or were you adding to that existing entry?"
- Wait for user clarification before creating the record.
- If user confirms it's separate, create the new entry.
- If user says it's the same/duplicate, acknowledge and don't create.

Never invent values for missing fields.

If user says "the rest", "remaining", "balance" - look at context for the outstanding amount.

If information is missing, list it in the "missing_fields" array.

If intent is unclear, return "intent": "unknown".

Return ONLY valid JSON following this schema:

{{
  "intent": "payment | task | calendar_event | vendor | sub_event_update | event_update | query | conversation | unknown",
  "action": "create | update | delete",
  "confidence": number between 0.0 and 1.0,
  "data": {{}},
  "missing_fields": [],
  "needs_confirmation": true | false,
  "reference_id": "id of existing record to update/delete, or null for new",
  "follow_up_question": "question to ask user for missing critical info, or null",
  "assistant_message": "natural, friendly response message to show the user (REQUIRED for all intents)",
  "response_mode": "confirm | clarify | answer | execute | error",
  "referenced_records": ["list of record IDs used in this response, or null"]
}}

Response modes:
- confirm: You're about to do something and need user confirmation
- clarify: You need more information from the user
- answer: You're answering a question with data from context
- execute: Action can be executed immediately (high confidence, no confirmation needed)
- error: Something went wrong or request cannot be fulfilled

Intent definitions:
- payment: Financial transactions, deposits, balances, due dates
- task: Action items, to-dos, things to complete
- calendar_event: Meetings, appointments, tastings, fittings, scheduled activities
- vendor: Adding or updating vendor/supplier information
- sub_event_update: Adding, updating, cancelling, or rescheduling sub-events (e.g., "cancel the reception", "add a sangeet", "move mehndi to 6pm")
- event_update: Updating main event details (date range, location, name)
- query: User is asking a QUESTION about their data (e.g., "Show me all payments", "What's my largest expense?", "How much have I spent on catering?", "Show me pending tasks")
- conversation: User is having a conversational follow-up, asking clarifying questions, or asking about something just discussed. Use this when user refers to "that", "it", "the purchase" etc. and is asking questions or requesting info rather than creating/updating data.
- unknown: Cannot determine intent confidently

For CONVERSATION intent:
- Use when user asks follow-up questions about recent topic (e.g., "Is a payment type recorded for that?", "What details do I have for it?")
- Look at conversation history to understand what "that", "it", "the entry" refers to
- Provide a helpful, specific answer in assistant_message based on the context
- data can include: topic (what they're asking about), answer (the response), related_record_id (if referencing a specific record)

Examples of conversation responses:
- User: "Is a payment method recorded for that purchase?" (after discussing Blackberry Ridge)
  Response: assistant_message="Looking at your Blackberry Ridge payment, I see it was recorded as $16,000 via bank account on March 4th. No payment method details are missing for this one!"
- User: "Update that entry. It's my venue, blackberry ridge"
  Response: (This is actually a payment UPDATE, not conversation) assistant_message="Got it! I've updated that payment to associate it with your venue, Blackberry Ridge. Feel free to share more details about Blackberry Ridge and I'll save it under the Vendors tab."

For QUERY intent, extract into data:
- query_type: "list" | "aggregate" | "search" | "status"
- target: "payments" | "tasks" | "vendors" | "calendar_events" | "all"
- filters: object with filter conditions (e.g., {{"vendor_name": "decorator", "status": "pending"}})
- sort_by: string or null (e.g., "amount", "date", "due_date")
- sort_order: "asc" | "desc" or null
- limit: number or null

IMPORTANT FOR QUERIES:
- Use response_mode: "answer" for query responses
- Set needs_confirmation: false (queries don't need confirmation)
- Include referenced_records with IDs from context that match the query
- Your assistant_message should summarize what data will be shown, NOT make up data
- The backend will execute the actual database query - your job is to describe WHAT to query

Query examples:
- "Show me all payments" -> query_type: "list", target: "payments"
- "What's my largest expense?" -> query_type: "aggregate", target: "payments", sort_by: "amount", sort_order: "desc", limit: 1
- "How much have I paid the photographer?" -> query_type: "aggregate", target: "payments", filters: {{"vendor_name": "photographer"}}
- "Show me pending tasks" -> query_type: "list", target: "tasks", filters: {{"status": "pending"}}
- "What's due this week?" -> query_type: "list", target: "all", filters: {{"due_date_range": "this_week"}}

For PAYMENT intent (ONLY for payments that HAVE BEEN MADE - past tense):
- vendor_name: string or null
- amount_paid: number or null (if user says "the rest" or "remaining", use outstanding amount from context)
- remaining_balance: number or null (set to 0 if paying full balance)
- payment_date: "YYYY-MM-DD" or null (when payment was made, default to today if just "paid")
  - IMPORTANT: payment_date must be TODAY or in the PAST. Never set a future date as payment_date.
- due_date: "YYYY-MM-DD" or null (when remaining balance is due)
- method: string or null
- notes: string or null

IMPORTANT: If the payment is SCHEDULED FOR THE FUTURE, use TASK intent instead, NOT payment intent.

For TASK intent, extract into data:
- title: string (required) - e.g., "Pay $10,000 to Enmuse Photography"
- description: string or null
- due_date: "YYYY-MM-DD" or null - the date when this needs to be done
- priority: "low" | "medium" | "high"

Use TASK for:
- Future payments that haven't been made yet
- Reminders to pay someone
- Any action items or to-dos

For CALENDAR_EVENT intent, extract into data:
- title: string (required)
- event_date: "YYYY-MM-DD" (required)
- event_time: "HH:MM" or null
- location: string or null
- notes: string or null

For VENDOR intent, extract into data:
- name: string (required)
- category: string or null
- contact_info: string or null
- notes: string or null

Action guidelines:
- action="create": New payment, task, event, or vendor
- action="update": Follow-up payment on existing record, or modifying existing record
  - If updating, set reference_id to the existing record's ID from context

For SUB_EVENT_UPDATE intent, extract into data:
- action: "add" | "update" | "cancel" | "reschedule" (required)
- sub_event_name: string (the target sub-event name, e.g., "reception", "mehndi", "haldi")
- new_name: string or null (if renaming, e.g., changing "reception" to "sangeet")
- new_date: "YYYY-MM-DD" or null (if rescheduling or adding)
- new_start_time: "HH:MM" or null (if changing/setting time)
- new_end_time: "HH:MM" or null
- new_location: string or null (if changing venue)
- description: string or null

Examples:
- "Cancel the reception" -> action: "cancel", sub_event_name: "reception"
- "Add a sangeet at 6pm the day before the wedding" -> action: "add", new_name: "sangeet", new_start_time: "18:00"
- "Move mehndi to Saturday at 4pm" -> action: "reschedule", sub_event_name: "mehndi", new_start_time: "16:00"
- "Change reception to sangeet" -> action: "update", sub_event_name: "reception", new_name: "sangeet"

For EVENT_UPDATE intent, extract into data:
- name: string or null (new event name)
- start_date: "YYYY-MM-DD" or null
- end_date: "YYYY-MM-DD" or null
- location: string or null
- location_city: string or null
- description: string or null

Confidence guidelines:
- > 0.90: All required fields present, intent is clear
- 0.60 - 0.90: Intent clear but some fields missing or ambiguous
- < 0.60: Intent unclear or critical information missing

Set needs_confirmation = true unless confidence > 0.95 and no missing required fields.

FOLLOW-UP QUESTIONS:
If critical information is missing that would help create a more complete record, set "follow_up_question" to a natural, conversational question asking for that info.

Examples of when to ask follow-up questions:
- Payment without method: "How did you pay for this? (card, cash, check, etc.)"
- Vendor without contact: "Do you have contact info for [vendor_name]?"
- Task without due date for time-sensitive items: "When does this need to be done by?"
- Calendar event without time: "What time is this scheduled for?"

Keep follow-up questions SHORT and CONVERSATIONAL. Only ask for ONE piece of missing info at a time, prioritizing the most important field.

Do not include explanations outside the JSON."""

    PLANNING_PROMPT = """You are an AI planning assistant for EventOps, an event planning platform.

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
