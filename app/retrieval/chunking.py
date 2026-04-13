import re
import logging
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

HEADING_PATTERNS = [
    re.compile(r"^[A-Z][A-Z\s&/,\-]{4,}$"),                    # ALL CAPS lines (min 5 chars)
    re.compile(r"^\d+\.\s+[A-Z]"),                               # "1. Something"
    re.compile(r"^(?:Section|Article|Part|Clause)\s+\d+", re.I), # "Section 3: ..."
    re.compile(r"^[IVXLC]+\.\s+"),                               # Roman numeral headings
    re.compile(r"^[A-Z][a-zA-Z\s&/,\-]{2,50}:\s*$"),            # "Title:" on its own line
]

MAX_CHUNK_TOKENS = 800
MIN_CHUNK_TOKENS = 50
OVERLAP_TOKENS = 100


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class Chunk:
    text: str
    page_number: int
    section_title: str
    attachment_id: str
    document_name: str
    vendor_name: str | None = None
    chunk_index: int = 0


def _estimate_tokens(text: str) -> int:
    return len(text.split())


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return False
    if _estimate_tokens(stripped) > 15:
        return False
    return any(p.match(stripped) for p in HEADING_PATTERNS)


def extract_text_from_pdf(file_path: str | Path) -> list[PageText]:
    """Extract text from each page of a PDF using PyMuPDF."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages = []
    doc = fitz.open(str(path))
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text and text.strip():
                pages.append(PageText(page_number=page_num + 1, text=text))
    finally:
        doc.close()

    return pages


def chunk_by_sections(
    pages: list[PageText],
    attachment_id: str,
    document_name: str,
    vendor_name: str | None = None,
) -> list[Chunk]:
    """Split extracted pages into chunks based on detected section headings.

    Falls back to page-based chunking with overlap if no headings are found.
    """
    raw_sections: list[tuple[str, int, str]] = []  # (section_title, page_num, text)

    for page in pages:
        lines = page.text.split("\n")
        current_title = f"Page {page.page_number}"
        current_lines: list[str] = []

        for line in lines:
            if _is_heading(line):
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        raw_sections.append((current_title, page.page_number, body))
                current_title = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                raw_sections.append((current_title, page.page_number, body))

    heading_sections = [s for s in raw_sections if not s[0].startswith("Page ")]
    if len(heading_sections) < 2:
        return _chunk_by_pages(pages, attachment_id, document_name, vendor_name)

    chunks: list[Chunk] = []
    idx = 0
    for title, page_num, text in raw_sections:
        tokens = _estimate_tokens(text)
        if tokens < MIN_CHUNK_TOKENS:
            if chunks:
                chunks[-1].text += "\n\n" + text
                continue

        if tokens > MAX_CHUNK_TOKENS:
            sub_chunks = _split_large_text(text, MAX_CHUNK_TOKENS, OVERLAP_TOKENS)
            for i, sub in enumerate(sub_chunks):
                suffix = f" (part {i + 1})" if len(sub_chunks) > 1 else ""
                chunks.append(Chunk(
                    text=sub,
                    page_number=page_num,
                    section_title=title + suffix,
                    attachment_id=attachment_id,
                    document_name=document_name,
                    vendor_name=vendor_name,
                    chunk_index=idx,
                ))
                idx += 1
        else:
            chunks.append(Chunk(
                text=text,
                page_number=page_num,
                section_title=title,
                attachment_id=attachment_id,
                document_name=document_name,
                vendor_name=vendor_name,
                chunk_index=idx,
            ))
            idx += 1

    return chunks


def _chunk_by_pages(
    pages: list[PageText],
    attachment_id: str,
    document_name: str,
    vendor_name: str | None,
) -> list[Chunk]:
    """Fallback: chunk by page with overlap windows for long pages."""
    chunks: list[Chunk] = []
    idx = 0
    for page in pages:
        text = page.text.strip()
        if not text:
            continue

        tokens = _estimate_tokens(text)
        if tokens > MAX_CHUNK_TOKENS:
            sub_chunks = _split_large_text(text, MAX_CHUNK_TOKENS, OVERLAP_TOKENS)
            for i, sub in enumerate(sub_chunks):
                chunks.append(Chunk(
                    text=sub,
                    page_number=page.page_number,
                    section_title=f"Page {page.page_number}" + (f" (part {i + 1})" if len(sub_chunks) > 1 else ""),
                    attachment_id=attachment_id,
                    document_name=document_name,
                    vendor_name=vendor_name,
                    chunk_index=idx,
                ))
                idx += 1
        else:
            chunks.append(Chunk(
                text=text,
                page_number=page.page_number,
                section_title=f"Page {page.page_number}",
                attachment_id=attachment_id,
                document_name=document_name,
                vendor_name=vendor_name,
                chunk_index=idx,
            ))
            idx += 1

    return chunks


def _split_large_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text into windows of ~max_tokens with overlap."""
    words = text.split()
    sub_chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        sub_chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return sub_chunks
