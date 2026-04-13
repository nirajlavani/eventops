# EventOps AI

An AI-powered event operations platform for managing weddings, conferences, and complex multi-vendor events. Built around a conversational chatbot ("Eve") that extracts structured data from natural language, a RAG pipeline for contract Q&A, and a real-time observability dashboard for monitoring AI performance.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (SPA)                                │
│   Vanilla JS · Glassmorphism UI · Chat Interface · Dashboard · AI Ops      │
└──────────────┬────────────────────────────────────────┬─────────────────────┘
               │  REST API + SSE Streaming              │  Admin API
               ▼                                        ▼
┌──────────────────────────────────┐   ┌──────────────────────────────────────┐
│         FastAPI Backend          │   │       Admin / Observability          │
│                                  │   │                                      │
│  ┌───────────┐  ┌─────────────┐  │   │  /api/admin/metrics/*  (summary,     │
│  │  Routers  │  │  Services   │  │   │   recent, health)                    │
│  │           │  │             │  │   │  /api/admin/reindex   (bulk re-index) │
│  │ • capture │  │ • extract   │  │   └───────────────┬──────────────────────┘
│  │ • events  │  │ • context   │  │                   │
│  │ • vendors │  │ • planning  │  │                   │
│  │ • payments│  │ • metrics   │  │                   │
│  │ • tasks   │  │             │  │                   │
│  │ • calendar│  │             │  │                   │
│  │ • attach  │  │             │  │                   │
│  │ • notes   │  │             │  │                   │
│  └─────┬─────┘  └──────┬──────┘  │                   │
│        │               │         │                   │
│        ▼               ▼         │                   │
│  ┌──────────────────────────┐    │                   │
│  │   LLM Service            │    │                   │
│  │   (Tiered Model Router)  │    │                   │
│  └───┬────────┬────────┬────┘    │                   │
│      │        │        │         │                   │
└──────┼────────┼────────┼─────────┘                   │
       │        │        │                             │
    ┌──▼──┐  ┌──▼──┐  ┌──▼──┐         ┌───────────────▼──────────────┐
    │FAST │  │ BAL │  │STRNG│         │       RAG Pipeline           │
    │     │  │     │  │     │         │                              │
    │route│  │extra│  │ RAG │         │  PDF → PyMuPDF (tables +    │
    │intent│  │ction│  │synth│         │         text extraction)     │
    └──┬──┘  └──┬──┘  └──┬──┘         │      → Section chunking      │
       └────────┴────────┘            │      → Embedding (text-     │
                │                     │         embedding-3-small)   │
    ┌───────────▼───────────┐         │      → ChromaDB (cosine)     │
    │    OpenRouter API     │◄───────►│      → LLM answer gen       │
    │                       │         └──────────────────────────────┘
    │  Embeddings:          │
    │  text-embedding-      │
    │  3-small              │
    └───────────────────────┘
    ┌───────────────────────┐
    │   SQLite (async)      │
    │                       │
    │  Events, Vendors,     │
    │  Payments, Tasks,     │
    │  Calendar, Attachments│
    │  AILog, AIMetric,     │
    │  SubEvent, Feedback   │
    └───────────────────────┘
```

### Data Flow: Natural Language Capture

```
User: "Paid $500 deposit to Blackberry Ridge"
  │
  ▼
┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Context Service     │───►│  LLM Extraction  │───►│  Structured     │
│  (vendors, payments, │    │  (intent, data,  │    │  Result         │
│   tasks, docs)       │    │   confidence)    │    │  {intent:       │
└─────────────────────┘    └──────────────────┘    │   "payment",   │
                                                    │   data: {...}} │
                                                    └───────┬─────────┘
                                                            │
                                              User confirms │
                                                            ▼
                                                    ┌─────────────────┐
                                                    │  Persist to DB  │
                                                    │  + Auto-create  │
                                                    │    vendor/tasks │
                                                    └─────────────────┘
```

### Data Flow: Document Q&A (RAG)

```
User: "How much is the Grah Shanti in the Awaaz contract?"
  │
  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Intent       │──►│ Embed Query  │──►│ ChromaDB     │──►│ LLM Answer   │
│ Classification│   │ (text-emb-  │   │ Cosine       │   │ Generation   │
│ → doc_query  │   │  3-small)    │   │ Search       │   │ with [1][2]  │
└──────────────┘   └──────────────┘   │ (top-5)      │   │ citations    │
                                       └──────────────┘   └──────────────┘
```

## Features

### Core Event Management
- **Multi-event support** — manage weddings, conferences, and corporate events simultaneously
- **Vendor tracking** — contacts, categories, notes, and linked payments
- **Payment management** — deposits, balances, due dates, payment methods, bulk entry
- **Task board** — priorities, due dates, vendor-linked tasks, drag-and-drop Kanban
- **Calendar** — schedule tastings, fittings, meetings; monthly grid with event dots
- **Sub-events** — break complex events into ceremonies, receptions, etc.
- **File attachments** — upload contracts, invoices, quotes (PDF, images, docs)

### AI Chatbot ("Eve")
- **Natural language capture** — enter payments, tasks, vendors, and calendar events in plain English
- **Intent extraction** — LLM classifies input into 10 intent types with structured data extraction
- **Context-aware** — references existing vendors, payments, and tasks to avoid duplicates
- **Multi-step operations** — single message can trigger vendor creation + payment + reminder task
- **Streaming responses** — SSE-based token streaming for real-time chat UX
- **Conversation history** — maintains context across turns for follow-up messages

### RAG Pipeline (Contract Q&A)
- **Table-aware PDF extraction** — PyMuPDF `find_tables()` converts tabular data to structured markdown
- **Section-based chunking** — headings, tables, and text split into semantically coherent chunks
- **Vector search** — ChromaDB with cosine similarity, per-event collections
- **Cited answers** — responses include `[1]`, `[2]` source references with page numbers
- **Vendor-scoped queries** — optionally filter search results by vendor name

### Observability Dashboard (AI Ops)
- **Dark-mode admin panel** — garnet-themed overlay, visually distinct from user UI
- **Real-time metrics** — total calls, token usage, estimated cost, latency percentiles
- **Activity charts** — 7-day activity trend and latency trend (SVG)
- **Intent distribution** — breakdown of how users interact with the chatbot
- **RAG performance** — query count, average retrieval score, chunk statistics
- **Recent activity log** — timestamped table of all AI operations
- **Bulk re-index** — one-click re-indexing of all PDFs with latest extraction pipeline
- **Model display** — shows which LLM model is currently powering the system

### Dashboard & Visualization
- **Spend donut chart** — animated per-vendor breakdown with multi-column legend
- **Financial summary cards** — total spend, upcoming payments, overdue amounts
- **Vendor icons** — customizable emoji icons synced with donut chart colors
- **Notes** — rich-text note-taking per event, file-backed storage

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, async/await |
| **Database** | SQLite via aiosqlite (PostgreSQL-ready) |
| **ORM** | SQLAlchemy 2.0 (async sessions, mapped columns) |
| **LLM** | Tiered model routing via OpenRouter (Gemini 2.5 Flash Lite / 2.0 Flash / 2.5 Flash) |
| **Embeddings** | OpenAI text-embedding-3-small (via OpenRouter or direct) |
| **Vector Store** | ChromaDB (persistent, cosine similarity) |
| **PDF Extraction** | PyMuPDF (fitz) with table detection |
| **Frontend** | Vanilla JS, CSS (glassmorphism), Font Awesome |
| **Validation** | Pydantic v2 (schemas + settings) |
| **Testing** | pytest + pytest-asyncio, httpx ASGITransport |

## Setup

### Prerequisites
- Python 3.11+
- An [OpenRouter API key](https://openrouter.ai/keys) (required for AI features)

### Installation

```bash
# Clone and enter the project
git clone <repo-url>
cd eventops

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### Running

```bash
# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or with auto-reload for development
uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) for the UI, or [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

### Running Tests

```bash
python3 -m pytest tests/ -v
```

## Configuration

All settings are loaded from environment variables (`.env` file supported):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | API key for LLM and embedding calls (required) |
| `OPENAI_API_KEY` | — | Optional: direct OpenAI key for embeddings |
| `LLM_MODEL` | `google/gemini-2.0-flash-001` | Default (balanced) model on OpenRouter |
| `LLM_MODEL_FAST` | *(empty — uses LLM_MODEL)* | Fast tier: intent classification |
| `LLM_MODEL_STRONG` | *(empty — uses LLM_MODEL)* | Strong tier: RAG synthesis, planning |
| `DATABASE_URL` | `sqlite+aiosqlite:///./eventops.db` | Async database URL |
| `UPLOAD_DIR` | `uploads` | Directory for file attachments |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum upload file size |
| `CHROMA_PERSIST_DIR` | `chroma_db` | ChromaDB persistence directory |
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `true` | Enable debug mode |

### Model Routing

EventOps uses tiered model routing — each LLM call is assigned a tier that maps to a different model based on task complexity:

| Tier | Default Model | Call Sites | Optimized For |
|------|---------------|------------|---------------|
| **Fast** | `google/gemini-2.5-flash-lite` | Intent classification | Low latency, low cost |
| **Balanced** | `google/gemini-2.0-flash-001` | Structured extraction, streaming, auto-repair | JSON accuracy, moderate cost |
| **Strong** | `google/gemini-2.5-flash` | RAG answer synthesis, planning | Citation accuracy, complex reasoning |

When `LLM_MODEL_FAST` or `LLM_MODEL_STRONG` are not set, all tiers fall back to `LLM_MODEL`. Set them in `.env` to enable routing:

```bash
LLM_MODEL=google/gemini-2.0-flash-001
LLM_MODEL_FAST=google/gemini-2.5-flash-lite
LLM_MODEL_STRONG=google/gemini-2.5-flash
```

## Project Structure

```
eventops/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, router registration
│   ├── config.py               # Pydantic settings (env-based)
│   ├── database.py             # Async SQLAlchemy engine + session
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── event.py            #   Event, with relationships
│   │   ├── vendor.py           #   Vendor (name, category, contact)
│   │   ├── payment.py          #   Payment (amount, dates, method)
│   │   ├── task.py             #   Task (title, priority, status)
│   │   ├── calendar_event.py   #   CalendarEvent (date, time, location)
│   │   ├── attachment.py       #   Attachment (file metadata)
│   │   ├── sub_event.py        #   SubEvent (ceremony, reception, etc.)
│   │   ├── ai_log.py           #   AILog (extraction audit trail)
│   │   └── ai_metric.py        #   AIMetric (observability telemetry)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── routers/                # FastAPI route handlers
│   │   ├── capture.py          #   /capture/extract + /extract/stream
│   │   ├── admin.py            #   /admin/metrics + /admin/reindex
│   │   └── ...                 #   events, vendors, payments, etc.
│   ├── services/               # Business logic layer
│   │   ├── llm_service.py      #   OpenRouter LLM calls + JSON extraction
│   │   ├── extraction.py       #   Intent routing + data persistence
│   │   ├── context_service.py  #   Event context assembly for prompts
│   │   ├── planning.py         #   AI planning recommendations
│   │   └── metrics.py          #   Async metric recording
│   └── retrieval/              # RAG pipeline
│       ├── rag_service.py      #   Orchestrator (index + query)
│       ├── chunking.py         #   PDF extraction + table-aware chunking
│       ├── embeddings.py       #   Embedding API client
│       └── vector_store.py     #   ChromaDB wrapper (per-event collections)
├── frontend/
│   ├── index.html              # Single-page app shell
│   └── static/
│       ├── css/                #   Glassmorphism + branding styles
│       ├── js/app.js           #   ~4700 lines of vanilla JS
│       └── images/             #   Logo and assets
├── tests/
│   ├── conftest.py             # Async test fixtures (httpx + test DB)
│   ├── test_api_coverage.py    # REST endpoint coverage
│   ├── test_rag.py             # RAG pipeline tests
│   ├── test_rag_pipeline.py    # Chunking + extraction tests
│   └── docs/                   # Sample PDFs for testing
├── requirements.txt
├── .env.example
├── pytest.ini
└── README.md
```

## API Reference

### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/events` | Create a new event |
| `GET` | `/api/events` | List all events |
| `GET` | `/api/events/{id}` | Get event details |
| `PUT` | `/api/events/{id}` | Update event |
| `DELETE` | `/api/events/{id}` | Delete event (cascades) |

### Resources (scoped by event)
| Prefix | Resource |
|--------|----------|
| `.../vendors` | Vendor management (CRUD + search) |
| `.../payments` | Payment tracking (CRUD + filtering) |
| `.../tasks` | Task management (CRUD + status updates) |
| `.../calendar` | Calendar events + monthly grid view |
| `.../sub-events` | Sub-event management |
| `.../attachments` | File upload, download, indexing status |
| `.../notes` | File-backed note CRUD |

### AI & Capture
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `.../capture/extract` | Extract structured data from text |
| `POST` | `.../capture/extract/stream` | SSE streaming extraction |
| `POST` | `.../capture/confirm` | Confirm and persist extraction |
| `POST` | `.../capture/reject` | Reject an extraction |
| `GET` | `.../dashboard` | Event summary with financials |
| `POST` | `.../planning/focus` | AI planning recommendations |

### Admin / Observability
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/metrics/summary` | Aggregated metrics (tokens, cost, latency) |
| `GET` | `/api/admin/metrics/recent` | Recent AI operations log |
| `GET` | `/api/admin/metrics/health` | System health (error rate, percentiles) |
| `POST` | `/api/admin/reindex` | Re-index all PDFs with latest pipeline |
| `GET` | `/api/admin/reindex/status` | Re-index progress |

## License

MIT
