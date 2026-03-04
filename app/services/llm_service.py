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
    
    intent: Literal["payment", "task", "calendar_event", "vendor", "unknown"]
    action: Literal["create", "update"] = "create"
    confidence: float = Field(ge=0.0, le=1.0)
    data: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    reference_id: Optional[str] = None


class LLMService:
    """Service for interacting with LLMs via OpenRouter API."""
    
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    EXTRACTION_PROMPT = """You are a structured information extraction engine for EventOps AI.

Your task is to analyze user input and extract structured event planning data.

Today's date is: {today}

{context}

Follow these steps internally:

1. Check if context contains relevant existing records
2. Determine the user's intent
3. Determine if this is a NEW record (action="create") or UPDATE to existing (action="update")
4. Extract relevant fields
5. If updating, include reference_id of the record to update
6. Identify missing required fields
7. Estimate confidence
8. Return structured JSON

Never invent values for missing fields.

If user says "the rest", "remaining", "balance" - look at context for the outstanding amount.

If information is missing, list it in the "missing_fields" array.

If intent is unclear, return "intent": "unknown".

Return ONLY valid JSON following this schema:

{{
  "intent": "payment | task | calendar_event | vendor | unknown",
  "action": "create | update",
  "confidence": number between 0.0 and 1.0,
  "data": {{}},
  "missing_fields": [],
  "needs_confirmation": true | false,
  "reference_id": "id of existing record to update, or null for new"
}}

Intent definitions:
- payment: Financial transactions, deposits, balances, due dates
- task: Action items, to-dos, things to complete
- calendar_event: Meetings, appointments, tastings, fittings, scheduled activities
- vendor: Adding or updating vendor/supplier information
- unknown: Cannot determine intent confidently

For PAYMENT intent, extract into data:
- vendor_name: string or null
- amount_paid: number or null (if user says "the rest" or "remaining", use outstanding amount from context)
- remaining_balance: number or null (set to 0 if paying full balance)
- payment_date: "YYYY-MM-DD" or null (when payment was made, default to today if just "paid")
- due_date: "YYYY-MM-DD" or null (when remaining is due)
- method: string or null
- notes: string or null

For TASK intent, extract into data:
- title: string (required)
- description: string or null
- due_date: "YYYY-MM-DD" or null
- priority: "low" | "medium" | "high"

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

Confidence guidelines:
- > 0.90: All required fields present, intent is clear
- 0.60 - 0.90: Intent clear but some fields missing or ambiguous
- < 0.60: Intent unclear or critical information missing

Set needs_confirmation = true unless confidence > 0.95 and no missing required fields.

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
        }
        if error:
            result["error"] = error
        return result
    
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
    ) -> dict:
        """
        Extract intent and structured data from natural language input.
        
        Args:
            user_input: The natural language text from user
            context: Optional context string with existing records info
        
        Returns a validated dict with:
        - intent: payment | task | calendar_event | vendor | unknown
        - action: create | update
        - confidence: 0.0 to 1.0
        - data: intent-specific fields
        - missing_fields: list of required but missing fields
        - needs_confirmation: whether user must confirm
        - reference_id: ID of existing record to update (if action=update)
        """
        today = date.today().isoformat()
        context_str = context or "No existing records for context."
        system_prompt = self.EXTRACTION_PROMPT.format(today=today, context=context_str)
        
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
            result = self._get_unknown_result("Failed to parse LLM response")
            
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            result = self._get_unknown_result("LLM response failed schema validation")
            
        except httpx.RequestError as e:
            logger.error(f"API request error: {e}")
            result = self._get_unknown_result(f"API request failed: {str(e)}")
        
        return result
    
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
