"""Context retrieval service for injecting relevant data into LLM prompts."""

import json
import re
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vendor import Vendor
from app.models.payment import Payment
from app.models.task import Task
from app.models.calendar_event import CalendarEvent


class ContextService:
    """Service for retrieving contextual data to enhance LLM extractions."""
    
    async def get_payment_context(
        self,
        event_id: str,
        db: AsyncSession,
        vendor_hint: Optional[str] = None,
    ) -> dict:
        """
        Get payment context for an event, optionally filtered by vendor.
        
        Returns outstanding balances, recent payments, and vendor info
        to help the LLM understand references like "the rest" or "remaining".
        """
        context = {
            "outstanding_payments": [],
            "recent_payments": [],
            "vendors": [],
        }
        
        vendors_query = select(Vendor).where(Vendor.event_id == event_id)
        vendors_result = await db.execute(vendors_query)
        vendors = vendors_result.scalars().all()
        
        for vendor in vendors:
            context["vendors"].append({
                "id": vendor.id,
                "name": vendor.name,
                "category": vendor.category,
            })
        
        payments_query = (
            select(Payment)
            .where(Payment.event_id == event_id)
            .order_by(Payment.created_at.desc())
        )
        payments_result = await db.execute(payments_query)
        payments = payments_result.scalars().all()
        
        for payment in payments:
            vendor_name = None
            if payment.vendor_id:
                for v in vendors:
                    if v.id == payment.vendor_id:
                        vendor_name = v.name
                        break
            
            if not vendor_name and payment.notes:
                for keyword in ["decorator", "florist", "caterer", "photographer", "venue", "dj", "band"]:
                    if keyword in (payment.notes or "").lower():
                        vendor_name = keyword.title()
                        break
            
            outstanding_balance = 0
            if payment.notes and "REMAINING_BALANCE:" in payment.notes:
                match = re.search(r"REMAINING_BALANCE:\s*(\d+(?:\.\d+)?)", payment.notes)
                if match:
                    outstanding_balance = float(match.group(1))
            
            payment_info = {
                "id": payment.id,
                "vendor_id": payment.vendor_id,
                "vendor_name": vendor_name or "Unknown",
                "amount_paid": float(payment.amount) if payment.amount else 0,
                "outstanding_balance": outstanding_balance,
                "due_date": payment.due_date.isoformat() if payment.due_date else None,
                "paid_date": payment.paid_date.isoformat() if payment.paid_date else None,
            }
            
            if payment.due_date and outstanding_balance > 0:
                context["outstanding_payments"].append(payment_info)
            
            if payment.paid_date:
                context["recent_payments"].append(payment_info)
        
        if vendor_hint:
            vendor_hint_lower = vendor_hint.lower()
            context["outstanding_payments"] = [
                p for p in context["outstanding_payments"]
                if vendor_hint_lower in (p.get("vendor_name") or "").lower()
                or vendor_hint_lower in (p.get("notes") or "").lower()
            ]
        
        return context
    
    async def get_outstanding_for_vendor(
        self,
        event_id: str,
        vendor_name: str,
        db: AsyncSession,
    ) -> Optional[dict]:
        """
        Find outstanding payment for a specific vendor.
        
        Used when user says things like "paid the decorator the rest".
        """
        vendor_result = await db.execute(
            select(Vendor).where(
                and_(
                    Vendor.event_id == event_id,
                    Vendor.name.ilike(f"%{vendor_name}%"),
                )
            )
        )
        vendor = vendor_result.scalar_one_or_none()
        
        if vendor:
            payment_result = await db.execute(
                select(Payment).where(
                    and_(
                        Payment.event_id == event_id,
                        Payment.vendor_id == vendor.id,
                        Payment.due_date.isnot(None),
                    )
                ).order_by(Payment.due_date.desc())
            )
            payment = payment_result.scalar_one_or_none()
            
            if payment:
                return {
                    "payment_id": payment.id,
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "amount_due": float(payment.amount),
                    "due_date": payment.due_date.isoformat() if payment.due_date else None,
                    "original_paid": float(payment.amount) if payment.paid_date else 0,
                }
        
        payments_result = await db.execute(
            select(Payment).where(
                and_(
                    Payment.event_id == event_id,
                    Payment.due_date.isnot(None),
                )
            ).order_by(Payment.created_at.desc())
        )
        payments = payments_result.scalars().all()
        
        vendor_name_lower = vendor_name.lower()
        for payment in payments:
            notes = (payment.notes or "").lower()
            if vendor_name_lower in notes or any(
                keyword in notes for keyword in ["decorator", "florist", "caterer", "photographer", "venue"]
                if keyword in vendor_name_lower
            ):
                return {
                    "payment_id": payment.id,
                    "vendor_id": payment.vendor_id,
                    "vendor_name": vendor_name,
                    "amount_due": float(payment.amount),
                    "due_date": payment.due_date.isoformat() if payment.due_date else None,
                }
        
        return None
    
    def format_context_for_prompt(self, context: dict) -> str:
        """Format payment context as a string for LLM prompt injection."""
        if not context.get("outstanding_payments") and not context.get("recent_payments"):
            return "No existing payment records for this event."
        
        lines = ["EXISTING PAYMENT RECORDS FOR THIS EVENT:"]
        
        if context.get("outstanding_payments"):
            lines.append("\n=== OUTSTANDING BALANCES (use these for 'the rest' or 'remaining') ===")
            for p in context["outstanding_payments"]:
                outstanding = p.get('outstanding_balance', p.get('amount_paid', 0))
                lines.append(
                    f"  PAYMENT_ID: {p['id']}"
                )
                lines.append(
                    f"  Vendor: {p['vendor_name']}"
                )
                lines.append(
                    f"  Outstanding balance: ${outstanding:.2f}"
                    + (f" due by {p['due_date']}" if p.get('due_date') else "")
                )
                lines.append("")
        
        if context.get("recent_payments"):
            lines.append("\n=== RECENT PAYMENTS ===")
            for p in context["recent_payments"][:5]:
                lines.append(
                    f"  PAYMENT_ID: {p['id']} - {p['vendor_name']}: ${p.get('amount_paid', 0):.2f} paid"
                    + (f" on {p['paid_date']}" if p.get('paid_date') else "")
                )
        
        lines.append("\n=== INSTRUCTIONS ===")
        lines.append("- If user says 'the rest', 'remaining', or 'balance', use the Outstanding balance amount above")
        lines.append("- If this is a follow-up payment to an existing record, set action='update' and reference_id to the PAYMENT_ID")
        lines.append("- For new payments to new vendors, set action='create'")
        
        return "\n".join(lines)


def get_context_service() -> ContextService:
    """Get context service instance."""
    return ContextService()
