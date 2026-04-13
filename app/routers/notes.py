import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()

NOTES_BASE = Path(__file__).parent.parent.parent / "local" / "notes"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _validate_id(value: str, label: str = "ID") -> str:
    if not UUID_RE.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label} format",
        )
    return value


def _notes_dir(event_id: str) -> Path:
    _validate_id(event_id, "event_id")
    d = NOTES_BASE / event_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _note_path(event_id: str, note_id: str) -> Path:
    _validate_id(note_id, "note_id")
    return _notes_dir(event_id) / f"{note_id}.json"


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None


class NoteListItem(BaseModel):
    id: str
    title: str
    updated_at: str


class NoteResponse(BaseModel):
    id: str
    event_id: str
    title: str
    content: str
    created_at: str
    updated_at: str


@router.get("", response_model=List[NoteListItem])
async def list_notes(event_id: str) -> List[NoteListItem]:
    """List all notes for an event, sorted by updated_at descending."""
    d = _notes_dir(event_id)
    items: List[NoteListItem] = []
    for fp in d.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            items.append(NoteListItem(
                id=data["id"],
                title=data["title"],
                updated_at=data["updated_at"],
            ))
        except (json.JSONDecodeError, KeyError):
            continue
    items.sort(key=lambda n: n.updated_at, reverse=True)
    return items


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(event_id: str, body: NoteCreate) -> NoteResponse:
    """Create a new note."""
    now = datetime.utcnow().isoformat()
    note_id = str(uuid.uuid4())
    note = {
        "id": note_id,
        "event_id": event_id,
        "title": body.title,
        "content": body.content,
        "created_at": now,
        "updated_at": now,
    }
    fp = _note_path(event_id, note_id)
    fp.write_text(json.dumps(note, ensure_ascii=False), encoding="utf-8")
    return NoteResponse(**note)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(event_id: str, note_id: str) -> NoteResponse:
    """Get a single note with full content."""
    fp = _note_path(event_id, note_id)
    if not fp.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    data = json.loads(fp.read_text(encoding="utf-8"))
    return NoteResponse(**data)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(event_id: str, note_id: str, body: NoteUpdate) -> NoteResponse:
    """Update a note's title and/or content."""
    fp = _note_path(event_id, note_id)
    if not fp.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    data = json.loads(fp.read_text(encoding="utf-8"))
    if body.title is not None:
        data["title"] = body.title
    if body.content is not None:
        data["content"] = body.content
    data["updated_at"] = datetime.utcnow().isoformat()

    fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return NoteResponse(**data)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(event_id: str, note_id: str) -> None:
    """Delete a note."""
    fp = _note_path(event_id, note_id)
    if not fp.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    fp.unlink()
