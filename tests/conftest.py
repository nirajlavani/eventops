"""
Pytest configuration and fixtures for EventOps chatbot testing.
"""
import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_eventops.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database and tables for each test (isolated)."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def mega_wedding_prompts() -> dict:
    """Load the mega wedding test scenario."""
    prompts_path = Path(__file__).parent / "prompts" / "mega_wedding_scenario.json"
    with open(prompts_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def deep_prompting_scenarios() -> dict:
    """Load the deep prompting test scenarios."""
    prompts_path = Path(__file__).parent / "prompts" / "deep_prompting_scenarios.json"
    with open(prompts_path) as f:
        return json.load(f)


@pytest.fixture
def conversation_history() -> list:
    """Shared conversation history for context tests."""
    return []


class EventStateTracker:
    """Tracks state across test prompts."""
    
    def __init__(self):
        self.event_id: str | None = None
        self.vendors: dict = {}
        self.payments: list = []
        self.tasks: list = []
        self.sub_events: list = []
        self.conversation_history: list = []
    
    def add_to_history(self, role: str, content: str):
        self.conversation_history.append({
            "role": role,
            "content": content
        })


