import logging
from dataclasses import dataclass, field
from typing import Optional

from app.retrieval.vector_store import VectorStore, SearchResult
from app.retrieval.embeddings import EmbeddingService
from app.retrieval.chunking import extract_text_from_pdf, chunk_by_sections, Chunk
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = """You are Eve, the virtual event planner for EventOps.
The user is asking about their uploaded documents (contracts, quotes, invoices).

Answer based ONLY on the excerpts below. If the excerpts don't contain enough info, say so.

RULES:
- Write in plain, conversational English. Be concise and direct.
- CITE using [1], [2], etc. matching the excerpt number where each fact appears.
  Use different numbers for facts from different excerpts. Never default to one number.
- When referencing specific terms, clauses, or language from the document, quote them
  using > at the start of the line. ALWAYS prefer blockquotes over bullet points for
  contract language. Bullet points should only be used for your own summary lists.
- Do NOT include any "Sources" section — citations are handled separately.

{excerpts}
"""


@dataclass
class Citation:
    text: str
    document_name: str
    page_number: int
    section_title: str
    vendor_name: str | None = None
    score: float = 0.0


@dataclass
class RAGResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    has_results: bool = True


class RAGService:
    """Orchestrates the full RAG pipeline: index documents and answer questions."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore(embedding_service=self.embedding_service)
        self.llm_service = llm_service or LLMService()

    async def index_document(
        self,
        event_id: str,
        attachment_id: str,
        file_path: str,
        document_name: str,
        vendor_name: str | None = None,
        on_progress: Optional[callable] = None,
    ) -> int:
        """Extract, chunk, and index a PDF document. Returns number of chunks created.

        ``on_progress`` receives ``(stage, percent)`` where *stage* is one of
        ``extracting``, ``chunking``, ``embedding``, ``done`` and *percent*
        is an integer 0-100.
        """
        def _report(stage: str, pct: int) -> None:
            if on_progress:
                on_progress(stage, pct)

        try:
            _report("extracting", 10)
            pages = extract_text_from_pdf(file_path)
            if not pages:
                logger.warning("No text extracted from %s", file_path)
                _report("done", 100)
                return 0

            _report("chunking", 35)
            chunks = chunk_by_sections(
                pages=pages,
                attachment_id=attachment_id,
                document_name=document_name,
                vendor_name=vendor_name,
            )
            if not chunks:
                logger.warning("No chunks produced from %s", file_path)
                _report("done", 100)
                return 0

            _report("embedding", 60)
            count = await self.vector_store.add_chunks(event_id, chunks)
            _report("done", 100)
            return count

        except Exception as e:
            logger.error("Failed to index document %s: %s", document_name, str(e))
            raise

    def delete_document(self, event_id: str, attachment_id: str) -> int:
        """Remove all indexed chunks for a document."""
        return self.vector_store.delete_by_attachment(event_id, attachment_id)

    async def query(
        self,
        event_id: str,
        question: str,
        vendor_name: str | None = None,
        top_k: int = 5,
    ) -> RAGResponse:
        """Answer a question using RAG: search documents, then generate an answer with citations."""
        logger.info(
            "RAG query: event=%s question=%r vendor_filter=%s",
            event_id, question[:100], vendor_name,
        )
        search_results = await self.vector_store.search(
            event_id=event_id,
            query=question,
            top_k=top_k,
            vendor_name=vendor_name,
        )

        if not search_results:
            logger.warning("RAG query returned no results for event=%s", event_id)
            return RAGResponse(
                answer="I couldn't find any relevant information in your uploaded documents. "
                       "Make sure you've uploaded the contract or document you're asking about.",
                citations=[],
                has_results=False,
            )

        logger.info(
            "RAG found %d results, top score=%.3f, generating answer…",
            len(search_results), search_results[0].score if search_results else 0,
        )
        excerpts = self._format_excerpts(search_results)
        system_prompt = RAG_SYSTEM_PROMPT.format(excerpts=excerpts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        answer = await self.llm_service._call_api(messages, max_tokens=1024)

        citations = [
            Citation(
                text=r.text[:200] + ("..." if len(r.text) > 200 else ""),
                document_name=r.document_name,
                page_number=r.page_number,
                section_title=r.section_title,
                vendor_name=r.vendor_name,
                score=r.score,
            )
            for r in search_results
            if r.score > 0.3
        ]

        logger.info(
            "RAG response: %d citations (filtered from %d), answer_len=%d",
            len(citations), len(search_results), len(answer),
        )
        return RAGResponse(
            answer=answer,
            citations=citations,
            has_results=True,
        )

    def _format_excerpts(self, results: list[SearchResult]) -> str:
        parts: list[str] = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] Section: {r.section_title} | Page {r.page_number}\n"
                f"{r.text}\n"
            )
        return "\n".join(parts)
