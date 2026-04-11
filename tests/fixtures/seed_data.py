"""
Seed data for deep prompting tests.

This module creates a fully populated wedding event with:
- 5 sub-events (Mehndi, Sangeet, Haldi, Ceremony, Reception)
- 15 vendors across various categories
- 20+ payments (mix of full, partial, pending)
- 10 tasks (mix of completed, pending, overdue)

This provides a "mid-way starting point" for testing advanced operations
like updates, deletes, queries, and complex multi-entity interactions.
"""
from datetime import date, time, timedelta
from decimal import Decimal
import uuid


def get_seed_data():
    """
    Returns seed data for a fully populated wedding event.
    
    Event: "Priya & Rahul's Wedding" - August 15, 2026
    
    This represents a wedding that's already been planned for several months,
    with various payments made, tasks completed, and more work to do.
    """
    
    event_id = str(uuid.uuid4())
    today = date(2026, 3, 9)  # Test date
    wedding_date = date(2026, 8, 15)
    
    # =========================================================================
    # SUB-EVENTS
    # =========================================================================
    sub_events = [
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Mehndi",
            "date": date(2026, 8, 12),
            "start_time": time(16, 0),
            "end_time": time(21, 0),
            "location": "The Grand Pavilion - Garden Area",
            "description": "Traditional mehndi ceremony with music and food"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Sangeet",
            "date": date(2026, 8, 13),
            "start_time": time(18, 0),
            "end_time": time(23, 0),
            "location": "The Grand Pavilion - Ballroom",
            "description": "Dance performances and celebration"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Haldi",
            "date": date(2026, 8, 14),
            "start_time": time(10, 0),
            "end_time": time(13, 0),
            "location": "The Grand Pavilion - Pool Area",
            "description": "Intimate haldi ceremony"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Wedding Ceremony",
            "date": date(2026, 8, 15),
            "start_time": time(11, 0),
            "end_time": time(14, 0),
            "location": "The Grand Pavilion - Mandap",
            "description": "Traditional Hindu wedding ceremony"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Reception",
            "date": date(2026, 8, 15),
            "start_time": time(19, 0),
            "end_time": time(1, 0),
            "location": "The Grand Pavilion - Grand Ballroom",
            "description": "Evening reception with dinner and dancing"
        },
    ]
    
    # =========================================================================
    # VENDORS
    # =========================================================================
    vendors = [
        # Venue
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "The Grand Pavilion",
            "category": "venue",
            "contact_info": "555-100-1000",
            "notes": "All 5 events booked here"
        },
        # Photography
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Enmuse Photography",
            "category": "photography",
            "contact_info": "enmuse@email.com",
            "notes": "Candid + traditional coverage"
        },
        # Videography
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Video Vihaar",
            "category": "videography",
            "contact_info": "555-200-2000",
            "notes": "Cinematic wedding film"
        },
        # Catering
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Royal Feast Caterers",
            "category": "catering",
            "contact_info": "royalfeast@email.com",
            "notes": "250 guests, vegetarian menu"
        },
        # Florist
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Petals & Blooms",
            "category": "florist",
            "contact_info": "555-300-3000",
            "notes": "All floral arrangements"
        },
        # DJ/Music
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "DJ Krish",
            "category": "music_dj",
            "contact_info": "djkrish@email.com",
            "notes": "Sangeet and Reception"
        },
        # Decor
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Celebrations Decor",
            "category": "decor",
            "contact_info": "555-400-4000",
            "notes": "Mandap, stage, and all event decor"
        },
        # Makeup/Hair
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Glow by Neha",
            "category": "makeup_hair",
            "contact_info": "glowneha@email.com",
            "notes": "Bridal makeup for all events"
        },
        # Mehndi
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Henna by Priya",
            "category": "mehndi",
            "contact_info": "555-500-5000",
            "notes": "Bride + family mehndi"
        },
        # Officiant
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Pandit Sharma",
            "category": "officiant",
            "contact_info": "555-600-6000",
            "notes": "Wedding ceremony"
        },
        # Choreographer
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Dance With Me Studio",
            "category": "choreographer",
            "contact_info": "dancewithme@email.com",
            "notes": "6 sangeet performances"
        },
        # Attire - Bridal
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Sabyasachi",
            "category": "attire",
            "contact_info": "N/A",
            "notes": "Bridal lehenga"
        },
        # Attire - Groom
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Manyavar",
            "category": "attire",
            "contact_info": "555-700-7000",
            "notes": "Groom's sherwani"
        },
        # Invitations
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Paper Trail Studios",
            "category": "invitations",
            "contact_info": "papertrail@email.com",
            "notes": "250 invitations + RSVP cards"
        },
        # Transportation
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "name": "Classic Rides",
            "category": "transportation",
            "contact_info": "555-800-8000",
            "notes": "Vintage car for wedding day"
        },
    ]
    
    # Create vendor lookup by name
    vendor_by_name = {v["name"]: v["id"] for v in vendors}
    
    # =========================================================================
    # PAYMENTS (Mix of completed and pending)
    # =========================================================================
    payments = [
        # Venue - $45,000 total, $15,000 paid, $30,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["The Grand Pavilion"],
            "amount": Decimal("15000"),
            "paid_date": date(2026, 1, 15),
            "due_date": None,
            "method": "bank_transfer",
            "notes": "Initial deposit - 1/3 of total"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["The Grand Pavilion"],
            "amount": Decimal("15000"),
            "paid_date": None,
            "due_date": date(2026, 6, 1),
            "method": None,
            "notes": "Second installment due"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["The Grand Pavilion"],
            "amount": Decimal("15000"),
            "paid_date": None,
            "due_date": date(2026, 8, 1),
            "method": None,
            "notes": "Final payment due"
        },
        
        # Photography - $12,000 total, paid in full
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Enmuse Photography"],
            "amount": Decimal("12000"),
            "paid_date": date(2026, 2, 10),
            "due_date": None,
            "method": "bank_transfer",
            "notes": "Paid in full - all events coverage"
        },
        
        # Videography - $8,000 total, $4,000 paid, $4,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Video Vihaar"],
            "amount": Decimal("4000"),
            "paid_date": date(2026, 2, 20),
            "due_date": None,
            "method": "credit_card",
            "notes": "50% deposit"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Video Vihaar"],
            "amount": Decimal("4000"),
            "paid_date": None,
            "due_date": date(2026, 8, 10),
            "method": None,
            "notes": "Remaining 50% due before wedding"
        },
        
        # Catering - $35,000 total, $10,000 paid, $25,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Royal Feast Caterers"],
            "amount": Decimal("10000"),
            "paid_date": date(2026, 2, 1),
            "due_date": None,
            "method": "check",
            "notes": "Booking deposit"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Royal Feast Caterers"],
            "amount": Decimal("25000"),
            "paid_date": None,
            "due_date": date(2026, 8, 1),
            "method": None,
            "notes": "Final payment - 250 guests @ $140/head"
        },
        
        # Florist - $7,500 total, paid in full
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Petals & Blooms"],
            "amount": Decimal("7500"),
            "paid_date": date(2026, 3, 1),
            "due_date": None,
            "method": "credit_card",
            "notes": "Paid in full"
        },
        
        # DJ - $3,500 total, $1,500 paid, $2,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["DJ Krish"],
            "amount": Decimal("1500"),
            "paid_date": date(2026, 2, 25),
            "due_date": None,
            "method": "venmo",
            "notes": "Booking fee"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["DJ Krish"],
            "amount": Decimal("2000"),
            "paid_date": None,
            "due_date": date(2026, 8, 12),
            "method": None,
            "notes": "Balance due day before sangeet"
        },
        
        # Decor - $18,000 total, $6,000 paid, $12,000 pending (2 payments)
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Celebrations Decor"],
            "amount": Decimal("6000"),
            "paid_date": date(2026, 1, 20),
            "due_date": None,
            "method": "bank_transfer",
            "notes": "1/3 deposit"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Celebrations Decor"],
            "amount": Decimal("6000"),
            "paid_date": None,
            "due_date": date(2026, 6, 15),
            "method": None,
            "notes": "Second installment"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Celebrations Decor"],
            "amount": Decimal("6000"),
            "paid_date": None,
            "due_date": date(2026, 8, 10),
            "method": None,
            "notes": "Final payment"
        },
        
        # Makeup - $4,000 total, $1,500 paid, $2,500 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Glow by Neha"],
            "amount": Decimal("1500"),
            "paid_date": date(2026, 3, 5),
            "due_date": None,
            "method": "cash",
            "notes": "Deposit after trial"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Glow by Neha"],
            "amount": Decimal("2500"),
            "paid_date": None,
            "due_date": date(2026, 8, 11),
            "method": None,
            "notes": "Balance due day before mehndi"
        },
        
        # Mehndi - $2,500 total, $500 paid, $2,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Henna by Priya"],
            "amount": Decimal("500"),
            "paid_date": date(2026, 2, 15),
            "due_date": None,
            "method": "venmo",
            "notes": "Booking deposit"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Henna by Priya"],
            "amount": Decimal("2000"),
            "paid_date": None,
            "due_date": date(2026, 8, 11),
            "method": None,
            "notes": "Pay day before mehndi ceremony"
        },
        
        # Pandit - $1,500 paid in full
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Pandit Sharma"],
            "amount": Decimal("1500"),
            "paid_date": date(2026, 3, 1),
            "due_date": None,
            "method": "check",
            "notes": "Full fee for ceremony"
        },
        
        # Choreographer - $2,000 total, $800 paid, $1,200 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Dance With Me Studio"],
            "amount": Decimal("800"),
            "paid_date": date(2026, 2, 1),
            "due_date": None,
            "method": "credit_card",
            "notes": "For 2 initial sessions"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Dance With Me Studio"],
            "amount": Decimal("1200"),
            "paid_date": None,
            "due_date": date(2026, 8, 1),
            "method": None,
            "notes": "Remaining sessions + event day"
        },
        
        # Bridal Lehenga - $15,000 total, $10,000 paid, $5,000 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Sabyasachi"],
            "amount": Decimal("10000"),
            "paid_date": date(2026, 1, 10),
            "due_date": None,
            "method": "credit_card",
            "notes": "Order confirmation payment"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Sabyasachi"],
            "amount": Decimal("5000"),
            "paid_date": None,
            "due_date": date(2026, 7, 15),
            "method": None,
            "notes": "Balance due at pickup"
        },
        
        # Groom Sherwani - $4,000 paid in full
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Manyavar"],
            "amount": Decimal("4000"),
            "paid_date": date(2026, 2, 20),
            "due_date": None,
            "method": "credit_card",
            "notes": "Sherwani + accessories"
        },
        
        # Invitations - $1,800 paid in full
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Paper Trail Studios"],
            "amount": Decimal("1800"),
            "paid_date": date(2026, 1, 25),
            "due_date": None,
            "method": "credit_card",
            "notes": "250 custom invitations"
        },
        
        # Transportation - $1,200 total, $400 paid, $800 pending
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Classic Rides"],
            "amount": Decimal("400"),
            "paid_date": date(2026, 3, 1),
            "due_date": None,
            "method": "credit_card",
            "notes": "Reservation deposit"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "vendor_id": vendor_by_name["Classic Rides"],
            "amount": Decimal("800"),
            "paid_date": None,
            "due_date": date(2026, 8, 14),
            "method": None,
            "notes": "Balance due day before wedding"
        },
    ]
    
    # =========================================================================
    # TASKS
    # =========================================================================
    tasks = [
        # Completed tasks
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Book venue",
            "description": "Finalize The Grand Pavilion for all events",
            "due_date": date(2026, 1, 15),
            "status": "completed",
            "priority": "high"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Hire photographer",
            "description": "Book Enmuse Photography",
            "due_date": date(2026, 2, 1),
            "status": "completed",
            "priority": "high"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Order invitations",
            "description": "Design and order 250 invitations",
            "due_date": date(2026, 2, 1),
            "status": "completed",
            "priority": "high"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Book caterer",
            "description": "Finalize Royal Feast Caterers",
            "due_date": date(2026, 2, 15),
            "status": "completed",
            "priority": "high"
        },
        
        # Pending tasks
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Finalize guest list",
            "description": "Confirm final headcount for catering",
            "due_date": date(2026, 4, 15),
            "status": "pending",
            "priority": "high"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Book hotel rooms for guests",
            "description": "Reserve room block at Marriott",
            "due_date": date(2026, 5, 1),
            "status": "pending",
            "priority": "medium"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Schedule menu tasting",
            "description": "Tasting with Royal Feast",
            "due_date": date(2026, 4, 1),
            "status": "pending",
            "priority": "medium"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Pick up bridal lehenga",
            "description": "Final fitting and pickup from Sabyasachi",
            "due_date": date(2026, 7, 20),
            "status": "pending",
            "priority": "high"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Arrange airport pickups",
            "description": "Coordinate transport for out-of-town guests",
            "due_date": date(2026, 8, 10),
            "status": "pending",
            "priority": "low"
        },
        {
            "id": str(uuid.uuid4()),
            "event_id": event_id,
            "title": "Create seating chart",
            "description": "Assign tables for reception",
            "due_date": date(2026, 8, 1),
            "status": "pending",
            "priority": "medium"
        },
    ]
    
    # =========================================================================
    # SUMMARY STATISTICS
    # =========================================================================
    total_paid = sum(p["amount"] for p in payments if p["paid_date"])
    total_pending = sum(p["amount"] for p in payments if not p["paid_date"])
    
    summary = {
        "event_name": "Priya & Rahul's Wedding",
        "event_date": wedding_date,
        "sub_events_count": len(sub_events),
        "vendors_count": len(vendors),
        "total_payments": len(payments),
        "paid_payments": len([p for p in payments if p["paid_date"]]),
        "pending_payments": len([p for p in payments if not p["paid_date"]]),
        "total_paid": float(total_paid),
        "total_pending": float(total_pending),
        "total_budget": float(total_paid + total_pending),
        "tasks_count": len(tasks),
        "completed_tasks": len([t for t in tasks if t["status"] == "completed"]),
        "pending_tasks": len([t for t in tasks if t["status"] == "pending"]),
    }
    
    return {
        "event": {
            "id": event_id,
            "name": "Priya & Rahul's Wedding",
            "event_date": wedding_date,
        },
        "sub_events": sub_events,
        "vendors": vendors,
        "payments": payments,
        "tasks": tasks,
        "summary": summary,
    }


# Quick verification
if __name__ == "__main__":
    data = get_seed_data()
    print(f"Event: {data['event']['name']}")
    print(f"Sub-events: {data['summary']['sub_events_count']}")
    print(f"Vendors: {data['summary']['vendors_count']}")
    print(f"Total Budget: ${data['summary']['total_budget']:,.0f}")
    print(f"  - Paid: ${data['summary']['total_paid']:,.0f}")
    print(f"  - Pending: ${data['summary']['total_pending']:,.0f}")
    print(f"Tasks: {data['summary']['tasks_count']} ({data['summary']['completed_tasks']} done, {data['summary']['pending_tasks']} pending)")
