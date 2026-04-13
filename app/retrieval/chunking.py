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


def _is_section_header_row(row: list[str], ncols: int) -> bool:
    """A row is a section header when the first cell has text but the rest are empty.

    This catches patterns like  | Grah Shanti + Vidhi 11/28/2026 |  |  |  |  |
    which PDF quote/invoice tables use as sub-section dividers.
    """
    if not row or not row[0]:
        return False
    non_empty = sum(1 for c in row if c)
    return non_empty == 1 and ncols >= 3


def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF Table object into structured markdown.

    Section-header rows (first cell has content, rest empty) are rendered as
    ### headings so the LLM can clearly see which line items belong to which
    event/category. Regular data rows stay in pipe-delimited table format.
    """
    data = table.extract()
    if not data:
        return ""
    rows = [
        [c.replace("\n", " ").strip() if c else "" for c in row]
        for row in data
    ]
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return ""

    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]

    parts: list[str] = []
    current_table_rows: list[list[str]] = []
    last_header_row: list[str] | None = None

    def _flush_table():
        if not current_table_rows:
            return
        if last_header_row:
            header_line = "| " + " | ".join(last_header_row) + " |"
            sep_line = "| " + " | ".join("---" for _ in range(ncols)) + " |"
            body = [header_line, sep_line]
        else:
            first = current_table_rows[0]
            body = [
                "| " + " | ".join(first) + " |",
                "| " + " | ".join("---" for _ in range(ncols)) + " |",
            ]
            current_table_rows.pop(0)
        for r in current_table_rows:
            body.append("| " + " | ".join(r) + " |")
        parts.append("\n".join(body))

    for row in rows:
        if _is_section_header_row(row, ncols):
            _flush_table()
            current_table_rows = []
            last_header_row = None
            parts.append(f"\n### {row[0]}\n")
        elif row == [""] * ncols:
            continue
        elif all(c in ("", "Description", "Qty", "Unit", "Total", "Amount",
                       "Price", "Rate", "Item", "Cost")
                 for c in row if c):
            _flush_table()
            current_table_rows = []
            last_header_row = row
        else:
            current_table_rows.append(row)

    _flush_table()
    return "\n".join(parts)


def _rects_overlap(r1, r2) -> bool:
    """Check if two (x0, y0, x1, y1) rectangles overlap."""
    return not (r1[2] <= r2[0] or r2[2] <= r1[0] or r1[3] <= r2[1] or r2[3] <= r1[1])


def _extract_page_with_tables(page) -> str:
    """Extract page text with tables converted to markdown.

    Non-table text and markdown tables are merged in top-to-bottom reading
    order so the surrounding context (e.g. a heading like
    'Grah Shanti + Vidhi') stays adjacent to its table.
    """
    tables_result = page.find_tables()
    tables = tables_result.tables if tables_result else []

    if not tables:
        return page.get_text("text")

    table_bboxes = [t.bbox for t in tables]

    # Collect content pieces as (y_position, text)
    pieces: list[tuple[float, str]] = []

    # Add markdown tables
    for tbl, bbox in zip(tables, table_bboxes):
        md = _table_to_markdown(tbl)
        if md:
            pieces.append((bbox[1], md))

    # Add non-table text blocks
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:  # only text blocks
            continue
        block_rect = (block["bbox"][0], block["bbox"][1], block["bbox"][2], block["bbox"][3])

        if any(_rects_overlap(block_rect, tb) for tb in table_bboxes):
            continue

        # Reconstruct text from spans
        lines = []
        for line in block.get("lines", []):
            spans_text = "".join(s.get("text", "") for s in line.get("spans", []))
            if spans_text.strip():
                lines.append(spans_text)
        if lines:
            pieces.append((block["bbox"][1], "\n".join(lines)))

    # Sort by vertical position and join
    pieces.sort(key=lambda p: p[0])
    return "\n\n".join(text for _, text in pieces)


def extract_text_from_pdf(file_path: str | Path) -> list[PageText]:
    """Extract text from each page of a PDF using PyMuPDF.

    Tables are detected via find_tables() and converted to markdown so the
    LLM can reason about rows, columns, and line-item pricing.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages = []
    doc = fitz.open(str(path))
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = _extract_page_with_tables(page)
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
