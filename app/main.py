from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db
from app.config import get_settings
from app.routers import events, vendors, payments, tasks, calendar, capture, dashboard, planning


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    await init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="EventOps AI",
    description="AI-powered event operations platform",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
)

app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(vendors.router, prefix="/api/events/{event_id}/vendors", tags=["Vendors"])
app.include_router(payments.router, prefix="/api/events/{event_id}/payments", tags=["Payments"])
app.include_router(tasks.router, prefix="/api/events/{event_id}/tasks", tags=["Tasks"])
app.include_router(calendar.router, prefix="/api/events/{event_id}/calendar", tags=["Calendar"])
app.include_router(capture.router, prefix="/api/events/{event_id}/capture", tags=["Capture"])
app.include_router(dashboard.router, prefix="/api/events/{event_id}/dashboard", tags=["Dashboard"])
app.include_router(planning.router, prefix="/api/events/{event_id}/planning", tags=["Planning"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "EventOps AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
