# EventOps AI

AI-powered event operations platform for managing weddings, conferences, and other complex events.

## Features

- **Event Management**: Create and manage multiple events (weddings, conferences, corporate events)
- **Vendor Tracking**: Track vendors, contacts, and categories per event
- **Payment Management**: Record payments, track balances, and upcoming due dates
- **Task Management**: Create tasks with priorities and due dates
- **Calendar Events**: Schedule meetings, tastings, fittings, and other appointments
- **Natural Language Capture**: Enter updates in plain text, AI extracts structured data
- **AI Planning Assistant**: Get prioritized recommendations on what to focus on

## Tech Stack

- **Backend**: Python, FastAPI
- **Database**: SQLite (MVP), PostgreSQL-ready
- **AI**: MiniMax M2.5 via OpenRouter API (cost-efficient)
- **ORM**: SQLAlchemy 2.0

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENROUTER_API_KEY
   # Get your key at https://openrouter.ai/keys
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Access the API docs at `http://localhost:8000/docs`

## API Overview

### Events
- `POST /api/events` - Create new event
- `GET /api/events` - List all events
- `GET /api/events/{event_id}` - Get event details
- `PUT /api/events/{event_id}` - Update event
- `DELETE /api/events/{event_id}` - Delete event

### Resources (scoped by event)
- `/api/events/{event_id}/vendors` - Vendor management
- `/api/events/{event_id}/payments` - Payment tracking
- `/api/events/{event_id}/tasks` - Task management
- `/api/events/{event_id}/calendar` - Calendar events

### AI Features
- `POST /api/events/{event_id}/capture/extract` - Extract structured data from text
- `POST /api/events/{event_id}/capture/confirm` - Confirm and save extracted data
- `GET /api/events/{event_id}/dashboard` - Get event summary
- `POST /api/events/{event_id}/planning/focus` - Get AI planning recommendations

## Natural Language Capture

Enter updates in plain text:
```
"Paid $500 deposit to decorator. Remaining $1500 due April 10."
```

The AI extracts structured data:
```json
{
  "intent": "payment",
  "data": {
    "vendor_name": "decorator",
    "amount_paid": 500,
    "remaining_balance": 1500,
    "due_date": "2026-04-10"
  }
}
```

Review and confirm to save to the database.

## Project Structure

```
eventops/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   └── retrieval/           # Future: Vector DB (Phase 2)
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT
