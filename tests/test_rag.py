"""
Tests for the RAG (Retrieval-Augmented Generation) pipeline.

Covers:
- PDF text extraction and section-based chunking
- Vector store add/search/delete operations
- End-to-end RAG query flow (with mocked embeddings)
- Document query intent in capture schemas
- Context service document listing
"""
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Vendor
from app.models.attachment import Attachment
from app.retrieval.chunking import (
    Chunk,
    PageText,
    chunk_by_sections,
    extract_text_from_pdf,
    _is_heading,
    _estimate_tokens,
    _split_large_text,
)
from app.retrieval.vector_store import VectorStore, SearchResult
from app.retrieval.rag_service import RAGService, RAGResponse, Citation
from app.schemas.capture import IntentType, DocumentQueryData, CitationData


# ============================================================================
# HELPERS
# ============================================================================

async def _make_event(db: AsyncSession, name: str = "Test Wedding") -> Event:
    event = Event(name=name, event_date=date(2026, 11, 29))
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def _make_vendor(db: AsyncSession, event_id: str, name: str = "Blackberry Ridge",
                       category: str = "venue") -> Vendor:
    vendor = Vendor(event_id=event_id, name=name, category=category)
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return vendor


def _create_test_pdf(path: str, content_pages: list[str]) -> str:
    """Create a simple test PDF with given pages of text content."""
    import fitz
    doc = fitz.open()
    for text in content_pages:
        page = doc.new_page()
        page.insert_text((50, 50), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


CONTRACT_PAGE_1 = """WEDDING VENUE CONTRACT

BLACKBERRY RIDGE ESTATES

1. SERVICES PROVIDED
The venue agrees to provide the following services for the wedding event:
- Main ballroom rental for ceremony and reception
- Outdoor garden area for cocktail hour
- Bridal suite access from 10am day of event
- Tables and chairs for up to 200 guests
- Basic audio/visual equipment

2. PAYMENT TERMS
Total venue rental fee: $48,000
Payment schedule:
- First deposit of $16,000 due upon signing
- Second payment of $16,000 due May 1, 2026
- Final payment of $16,000 due November 28, 2026
Late payments subject to 5% surcharge."""

CONTRACT_PAGE_2 = """3. CANCELLATION POLICY
Cancellation more than 180 days before event: Full refund minus $500 admin fee
Cancellation 90-180 days before event: 50% refund of total paid
Cancellation less than 90 days before event: No refund
Force majeure events will be handled on a case-by-case basis.

4. LIABILITY AND INSURANCE
The venue carries general liability insurance up to $2,000,000.
Client is responsible for obtaining event insurance.
The venue is not responsible for damage to personal property.

5. FOOD AND BEVERAGE
All catering must be provided by venue-approved caterers.
Outside food and beverage is not permitted.
Bar service available with proper licensing.
Minimum food and beverage spend: $15,000."""


# ============================================================================
# CHUNKING TESTS
# ============================================================================

@pytest.mark.fast
class TestChunkingHelpers:
    """Test chunking utility functions."""

    def test_is_heading_all_caps(self):
        assert _is_heading("CANCELLATION POLICY")
        assert _is_heading("PAYMENT TERMS")
        assert not _is_heading("this is normal text")

    def test_is_heading_numbered(self):
        assert _is_heading("1. Services Provided")
        assert _is_heading("3. Cancellation Policy")

    def test_is_heading_section_keyword(self):
        assert _is_heading("Section 5: Insurance")
        assert _is_heading("Article 3: Liability")

    def test_is_heading_rejects_long_lines(self):
        long_text = "This is a very long line that should not be detected as a heading " * 3
        assert not _is_heading(long_text)

    def test_is_heading_rejects_empty(self):
        assert not _is_heading("")
        assert not _is_heading("   ")

    def test_estimate_tokens(self):
        assert _estimate_tokens("hello world foo bar") == 4
        assert _estimate_tokens("") == 0

    def test_split_large_text(self):
        words = " ".join([f"word{i}" for i in range(100)])
        chunks = _split_large_text(words, max_tokens=30, overlap=5)
        assert len(chunks) >= 3
        assert all(len(c.split()) <= 30 for c in chunks)


@pytest.mark.fast
class TestChunkBySections:
    """Test section-based chunking logic."""

    def test_detects_sections_from_pages(self):
        pages = [
            PageText(page_number=1, text=CONTRACT_PAGE_1),
            PageText(page_number=2, text=CONTRACT_PAGE_2),
        ]
        chunks = chunk_by_sections(pages, attachment_id="att_1", document_name="contract.pdf")
        assert len(chunks) > 0
        section_titles = [c.section_title for c in chunks]
        has_sections = any(
            "CANCELLATION" in t.upper() or "PAYMENT" in t.upper() or "SERVICES" in t.upper()
            for t in section_titles
        )
        assert has_sections, f"Expected section headings, got: {section_titles}"

    def test_chunk_metadata(self):
        pages = [PageText(page_number=1, text=CONTRACT_PAGE_1)]
        chunks = chunk_by_sections(
            pages,
            attachment_id="att_123",
            document_name="venue_contract.pdf",
            vendor_name="Blackberry Ridge",
        )
        assert all(c.attachment_id == "att_123" for c in chunks)
        assert all(c.document_name == "venue_contract.pdf" for c in chunks)
        assert all(c.vendor_name == "Blackberry Ridge" for c in chunks)

    def test_fallback_to_page_chunking(self):
        pages = [
            PageText(page_number=1, text="Just plain text without any headings at all. " * 20),
            PageText(page_number=2, text="More plain text on page two without headings. " * 20),
        ]
        chunks = chunk_by_sections(pages, attachment_id="att_2", document_name="notes.pdf")
        assert len(chunks) >= 2
        assert all("Page" in c.section_title for c in chunks)

    def test_empty_pages_produce_no_chunks(self):
        pages = [PageText(page_number=1, text="   ")]
        chunks = chunk_by_sections(pages, attachment_id="att_3", document_name="empty.pdf")
        assert len(chunks) == 0


@pytest.mark.fast
class TestPDFExtraction:
    """Test PDF text extraction."""

    def test_extract_from_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                _create_test_pdf(f.name, [CONTRACT_PAGE_1, CONTRACT_PAGE_2])
                pages = extract_text_from_pdf(f.name)
                assert len(pages) == 2
                assert pages[0].page_number == 1
                assert pages[1].page_number == 2
                assert "SERVICES PROVIDED" in pages[0].text
                assert "CANCELLATION" in pages[1].text
            finally:
                os.unlink(f.name)

    def test_extract_nonexistent_pdf(self):
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf("/nonexistent/file.pdf")


# ============================================================================
# VECTOR STORE TESTS (with mocked embeddings)
# ============================================================================

def _make_mock_embedding_service():
    """Create a mock embedding service that returns deterministic vectors."""
    mock = AsyncMock()
    call_count = [0]

    async def embed_texts(texts):
        vectors = []
        for t in texts:
            call_count[0] += 1
            vec = [0.0] * 384
            vec[call_count[0] % 384] = 1.0
            vectors.append(vec)
        return vectors

    async def embed_query(query):
        vec = [0.0] * 384
        for i, word in enumerate(query.split()):
            vec[i % 384] = 0.5
        return vec

    mock.embed_texts = embed_texts
    mock.embed_query = embed_query
    return mock


@pytest.mark.fast
class TestVectorStore:
    """Test ChromaDB vector store operations."""

    def setup_method(self):
        self.chroma_dir = tempfile.mkdtemp()
        self.mock_embeddings = _make_mock_embedding_service()
        self.store = VectorStore(
            embedding_service=self.mock_embeddings,
            persist_dir=self.chroma_dir,
        )

    def teardown_method(self):
        shutil.rmtree(self.chroma_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_add_and_search_chunks(self):
        chunks = [
            Chunk(text="Cancellation policy requires 30 days notice",
                  page_number=2, section_title="Cancellation Policy",
                  attachment_id="att_1", document_name="contract.pdf",
                  vendor_name="Blackberry Ridge", chunk_index=0),
            Chunk(text="Payment of $16,000 due upon signing",
                  page_number=1, section_title="Payment Terms",
                  attachment_id="att_1", document_name="contract.pdf",
                  vendor_name="Blackberry Ridge", chunk_index=1),
        ]
        count = await self.store.add_chunks("event_1", chunks)
        assert count == 2

        results = await self.store.search("event_1", "cancellation policy")
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].document_name == "contract.pdf"

    @pytest.mark.asyncio
    async def test_delete_by_attachment(self):
        chunks = [
            Chunk(text="Test content", page_number=1, section_title="Test",
                  attachment_id="att_del", document_name="test.pdf",
                  chunk_index=0),
        ]
        await self.store.add_chunks("event_2", chunks)
        deleted = self.store.delete_by_attachment("event_2", "att_del")
        assert deleted == 1

        results = await self.store.search("event_2", "test content")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_empty_collection(self):
        results = await self.store.search("nonexistent_event", "any query")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_vendor_filter(self):
        chunks = [
            Chunk(text="Vendor A info", page_number=1, section_title="Info",
                  attachment_id="att_f1", document_name="a.pdf",
                  vendor_name="Vendor A", chunk_index=0),
            Chunk(text="Vendor B info", page_number=1, section_title="Info",
                  attachment_id="att_f2", document_name="b.pdf",
                  vendor_name="Vendor B", chunk_index=1),
        ]
        await self.store.add_chunks("event_f", chunks)

        results_a = await self.store.search("event_f", "info", vendor_name="Vendor A")
        assert all(r.vendor_name == "Vendor A" for r in results_a)


# ============================================================================
# RAG SERVICE TESTS (with mocked dependencies)
# ============================================================================

@pytest.mark.fast
class TestRAGService:
    """Test RAG pipeline with mocked vector store and LLM."""

    @pytest.mark.asyncio
    async def test_query_no_results(self):
        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[])

        rag = RAGService(vector_store=mock_vs)
        response = await rag.query("event_1", "What is the cancellation policy?")

        assert isinstance(response, RAGResponse)
        assert not response.has_results
        assert "couldn't find" in response.answer.lower()
        assert response.citations == []

    @pytest.mark.asyncio
    async def test_query_with_results(self):
        mock_results = [
            SearchResult(
                text="Cancellation more than 180 days: full refund minus $500 admin fee.",
                page_number=2,
                section_title="Cancellation Policy",
                attachment_id="att_1",
                document_name="venue_contract.pdf",
                vendor_name="Blackberry Ridge",
                score=0.92,
            ),
        ]

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=mock_results)

        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value="The cancellation policy requires 180 days notice for a full refund.")

        rag = RAGService(vector_store=mock_vs, llm_service=mock_llm)
        response = await rag.query("event_1", "What is the cancellation policy?")

        assert response.has_results
        assert "cancellation" in response.answer.lower()
        assert len(response.citations) == 1
        assert response.citations[0].document_name == "venue_contract.pdf"
        assert response.citations[0].section_title == "Cancellation Policy"
        assert response.citations[0].page_number == 2

    @pytest.mark.asyncio
    async def test_index_document(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                _create_test_pdf(f.name, [CONTRACT_PAGE_1])

                mock_vs = AsyncMock()
                mock_vs.add_chunks = AsyncMock(return_value=5)

                rag = RAGService(vector_store=mock_vs)
                count = await rag.index_document(
                    event_id="event_idx",
                    attachment_id="att_idx",
                    file_path=f.name,
                    document_name="contract.pdf",
                    vendor_name="Blackberry Ridge",
                )
                assert count == 5
                mock_vs.add_chunks.assert_called_once()
            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_delete_document(self):
        mock_vs = MagicMock()
        mock_vs.delete_by_attachment = MagicMock(return_value=3)

        rag = RAGService(vector_store=mock_vs)
        deleted = rag.delete_document("event_1", "att_1")
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_low_score_citations_filtered(self):
        mock_results = [
            SearchResult(
                text="Relevant info", page_number=1, section_title="Section A",
                attachment_id="att_1", document_name="doc.pdf",
                vendor_name=None, score=0.85,
            ),
            SearchResult(
                text="Barely relevant", page_number=2, section_title="Section B",
                attachment_id="att_1", document_name="doc.pdf",
                vendor_name=None, score=0.15,
            ),
        ]

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=mock_results)

        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value="Answer based on section A.")

        rag = RAGService(vector_store=mock_vs, llm_service=mock_llm)
        response = await rag.query("event_1", "some question")

        assert len(response.citations) == 1
        assert response.citations[0].section_title == "Section A"


# ============================================================================
# SCHEMA TESTS
# ============================================================================

@pytest.mark.fast
class TestDocumentQuerySchema:
    """Test document query schema and intent types."""

    def test_document_query_intent_exists(self):
        assert IntentType.DOCUMENT_QUERY == "document_query"
        assert IntentType.DOCUMENT_QUERY.value == "document_query"

    def test_document_query_data_schema(self):
        data = DocumentQueryData(
            query="What is the cancellation policy?",
            vendor_name="Blackberry Ridge",
            document_type="contract",
        )
        assert data.query == "What is the cancellation policy?"
        assert data.vendor_name == "Blackberry Ridge"

    def test_citation_data_schema(self):
        citation = CitationData(
            text="Cancellation requires 30 days notice.",
            document_name="venue_contract.pdf",
            page_number=2,
            section_title="Cancellation Policy",
            vendor_name="Blackberry Ridge",
            score=0.92,
        )
        assert citation.page_number == 2
        assert citation.score == 0.92

    def test_document_query_data_with_citations(self):
        data = DocumentQueryData(
            query="payment terms",
            citations=[
                {"text": "Payment of $16K due...", "document_name": "contract.pdf",
                 "page_number": 1, "section_title": "Payment Terms"},
            ],
        )
        assert len(data.citations) == 1


# ============================================================================
# CONTEXT SERVICE TESTS
# ============================================================================

@pytest.mark.fast
class TestContextDocuments:
    """Test that context service includes uploaded documents."""

    @pytest.mark.asyncio
    async def test_context_includes_documents(self, test_db: AsyncSession):
        event = await _make_event(test_db)
        vendor = await _make_vendor(test_db, event.id)

        att = Attachment(
            event_id=event.id,
            vendor_id=vendor.id,
            filename="stored_contract.pdf",
            original_filename="venue_contract.pdf",
            file_path="/uploads/contract.pdf",
            content_type="application/pdf",
            file_size=12345,
            category="contract",
        )
        test_db.add(att)
        await test_db.commit()

        from app.services.context_service import ContextService
        ctx_service = ContextService()
        context = await ctx_service.get_full_context(event.id, test_db)

        assert "documents" in context
        assert len(context["documents"]) == 1
        assert context["documents"][0]["filename"] == "venue_contract.pdf"
        assert context["documents"][0]["vendor_name"] == "Blackberry Ridge"

    @pytest.mark.asyncio
    async def test_context_format_includes_documents_section(self, test_db: AsyncSession):
        event = await _make_event(test_db)

        att = Attachment(
            event_id=event.id,
            filename="stored.pdf",
            original_filename="my_contract.pdf",
            file_path="/uploads/stored.pdf",
            content_type="application/pdf",
            file_size=5000,
            category="quote",
        )
        test_db.add(att)
        await test_db.commit()

        from app.services.context_service import ContextService
        ctx_service = ContextService()
        context = await ctx_service.get_full_context(event.id, test_db)
        formatted = ctx_service.format_full_context_for_prompt(context)

        assert "UPLOADED DOCUMENTS" in formatted
        assert "my_contract.pdf" in formatted
        assert "category: quote" in formatted

    @pytest.mark.asyncio
    async def test_context_no_documents(self, test_db: AsyncSession):
        event = await _make_event(test_db)

        from app.services.context_service import ContextService
        ctx_service = ContextService()
        context = await ctx_service.get_full_context(event.id, test_db)
        formatted = ctx_service.format_full_context_for_prompt(context)

        assert "None uploaded yet" in formatted
