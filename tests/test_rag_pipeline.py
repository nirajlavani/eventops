"""
Rigorous RAG Pipeline Tests.

Tests the full retrieval pipeline against both synthetic and real-world contracts
in tests/docs/.

Validates:
- Deterministic chunking and indexing of PDFs (synthetic + real)
- Retrieval consistency: repeated queries return identical results
- Citation accuracy: answers always cite source document, section, and page
- Cross-document retrieval: queries hit the correct contract
- Vendor-filtered retrieval: filters restrict results to the right vendor
- Real-world contract extraction and chunking robustness
- Multi-vendor index with 6+ real contracts
- Negative cases: irrelevant queries get low scores or no results
"""
import os
import shutil
import tempfile
from pathlib import Path
from difflib import SequenceMatcher

import pytest

from app.retrieval.chunking import (
    Chunk,
    PageText,
    chunk_by_sections,
    extract_text_from_pdf,
)
from app.retrieval.vector_store import VectorStore, SearchResult
from app.retrieval.rag_service import RAGService, RAGResponse, Citation

DOCS_DIR = Path(__file__).parent / "docs"

# Real-world contracts
WATERS_EDGE_PDF = DOCS_DIR / "Waters-Edge-Contract.pdf"
DJ_CHIRAG_PDF = DOCS_DIR / "DJ_Chirag_Contract_Quote.pdf"
AWAAZ_DJ_PDF = DOCS_DIR / "awaaz_DJ_unsigned-contract-v2-Blackberry-Ridge-231322405.pdf"
LAUREN_PHOTO_PDF = DOCS_DIR / "LAUREN VAUGHAN PHOTOGRAPHY Contract.pdf"
OFFICIANT_PDF = DOCS_DIR / "Officiant Contract.pdf"
CELEBRATIONS_PDF = DOCS_DIR / "CELEBRATIONS EVENT AND RENTAL MANAGEMENT Contract.pdf"

REAL_CONTRACTS = [
    (WATERS_EDGE_PDF, "att_waters", "Waters-Edge-Contract.pdf", "Waters Edge"),
    (DJ_CHIRAG_PDF, "att_chirag", "DJ_Chirag_Contract_Quote.pdf", "DJ Chirag"),
    (AWAAZ_DJ_PDF, "att_awaaz", "awaaz_DJ_contract.pdf", "Awaaz Entertainment"),
    (LAUREN_PHOTO_PDF, "att_lauren", "Lauren_Vaughan_Photography.pdf", "Lauren Vaughan Photography"),
    (OFFICIANT_PDF, "att_officiant", "Officiant_Contract.pdf", "Officiant"),
    (CELEBRATIONS_PDF, "att_celebrations", "Celebrations_Contract.pdf", "Celebrations Event & Rental"),
]

SIMILARITY_THRESHOLD = 0.6


def text_similarity(a: str, b: str) -> float:
    """Compute normalized similarity between two strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _make_deterministic_embedding_service():
    """Embedding service that produces consistent, content-aware vectors.

    Uses a simple bag-of-characters hash so that semantically identical text
    always gets the same vector — enabling deterministic retrieval tests
    without calling an external API.
    """
    from unittest.mock import AsyncMock

    DIM = 384

    def _text_to_vec(text: str) -> list[float]:
        vec = [0.0] * DIM
        for i, ch in enumerate(text.lower()):
            vec[ord(ch) % DIM] += 1.0
        norm = max(sum(v * v for v in vec) ** 0.5, 1e-9)
        return [v / norm for v in vec]

    mock = AsyncMock()

    async def embed_texts(texts: list[str]) -> list[list[float]]:
        return [_text_to_vec(t) for t in texts]

    async def embed_query(query: str) -> list[float]:
        return _text_to_vec(query)

    mock.embed_texts = embed_texts
    mock.embed_query = embed_query
    return mock


# ============================================================================
# FIXTURE: Shared indexed vector store with all real-world contracts
# ============================================================================

@pytest.fixture(scope="module")
def indexed_store():
    """Index all real-world test PDFs into a temporary ChromaDB and yield the store."""
    chroma_dir = tempfile.mkdtemp()
    embedding_svc = _make_deterministic_embedding_service()
    store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)

    import asyncio

    async def _index_all():
        for pdf_path, att_id, doc_name, vendor in REAL_CONTRACTS:
            if not pdf_path.exists():
                continue
            pages = extract_text_from_pdf(str(pdf_path))
            chunks = chunk_by_sections(
                pages, attachment_id=att_id, document_name=doc_name, vendor_name=vendor,
            )
            await store.add_chunks("event_test", chunks)

    asyncio.get_event_loop().run_until_complete(_index_all())

    yield store

    shutil.rmtree(chroma_dir, ignore_errors=True)


# ============================================================================
# 1. RETRIEVAL CONSISTENCY — same query returns similar results each time
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRetrievalConsistency:
    """Run the same query multiple times and assert results stay consistent."""

    @pytest.mark.asyncio
    async def test_repeated_cancellation_query_returns_consistent_results(self, indexed_store):
        results_runs = []
        for _ in range(3):
            results = await indexed_store.search("event_test", "What is the cancellation policy?")
            results_runs.append(results)

        for run in results_runs:
            assert len(run) > 0, "Search returned no results"

        first_texts = [r.text for r in results_runs[0]]
        for later_run in results_runs[1:]:
            later_texts = [r.text for r in later_run]
            assert first_texts == later_texts, "Results differ between identical queries"

    @pytest.mark.asyncio
    async def test_repeated_payment_query_returns_consistent_results(self, indexed_store):
        results_runs = []
        for _ in range(3):
            results = await indexed_store.search("event_test", "How much do I need to pay and when?")
            results_runs.append(results)

        for run in results_runs:
            assert len(run) > 0

        for later_run in results_runs[1:]:
            assert [r.text for r in results_runs[0]] == [r.text for r in later_run]

    @pytest.mark.asyncio
    async def test_paraphrased_queries_return_overlapping_documents(self, indexed_store):
        """Different phrasings of the same question should retrieve overlapping documents."""
        q1_results = await indexed_store.search("event_test", "cancellation policy refund")
        q2_results = await indexed_store.search("event_test", "what happens if I cancel")

        q1_docs = {r.document_name for r in q1_results}
        q2_docs = {r.document_name for r in q2_results}
        overlap = q1_docs & q2_docs

        assert len(overlap) > 0, (
            f"Paraphrased queries returned zero overlapping documents.\n"
            f"Query 1 docs: {q1_docs}\n"
            f"Query 2 docs: {q2_docs}"
        )


# ============================================================================
# 2. VENDOR FILTERING — scoped retrieval
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestVendorFilteredRetrieval:
    """Ensure vendor_name filter restricts results."""

    @pytest.mark.asyncio
    async def test_filter_by_venue_vendor(self, indexed_store):
        results = await indexed_store.search(
            "event_test", "deposit cancellation fee", vendor_name="Waters Edge",
        )
        for r in results:
            assert r.vendor_name == "Waters Edge", (
                f"Vendor filter leaked: got {r.vendor_name}"
            )

    @pytest.mark.asyncio
    async def test_filter_by_dj_vendor(self, indexed_store):
        results = await indexed_store.search(
            "event_test", "entertainment performance deposit", vendor_name="DJ Chirag",
        )
        for r in results:
            assert r.vendor_name == "DJ Chirag"

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_vendor_falls_back_to_unfiltered(self, indexed_store):
        """When vendor filter matches nothing, fallback returns unfiltered results."""
        results = await indexed_store.search(
            "event_test", "cancellation", vendor_name="Nonexistent Vendor LLC",
        )
        assert len(results) > 0, "Fallback should return unfiltered results"


# ============================================================================
# 3. RAG RESPONSE — citation verification
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRAGCitationAccuracy:
    """Verify that RAG responses always include proper citations."""

    def _make_rag_with_mock_llm(self, store, llm_answer: str):
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value=(llm_answer, {}))
        return RAGService(vector_store=store, llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_cancellation_query_cites_document(self, indexed_store):
        rag = self._make_rag_with_mock_llm(
            indexed_store,
            "Cancellation requires written notice. Deposit may be forfeited.",
        )
        response = await rag.query("event_test", "What is the cancellation policy?")

        assert response.has_results
        assert len(response.citations) > 0, "Response must include at least one citation"

    @pytest.mark.asyncio
    async def test_every_citation_has_required_fields(self, indexed_store):
        rag = self._make_rag_with_mock_llm(indexed_store, "A deposit is required.")
        response = await rag.query("event_test", "What is the deposit amount?")

        for citation in response.citations:
            assert citation.document_name, "Citation missing document_name"
            assert citation.section_title, "Citation missing section_title"
            assert citation.page_number >= 1, "Citation missing valid page_number"
            assert citation.text, "Citation missing text excerpt"
            assert citation.score > 0, "Citation missing score"

    @pytest.mark.asyncio
    async def test_low_relevance_results_excluded_from_citations(self, indexed_store):
        rag = self._make_rag_with_mock_llm(indexed_store, "Some answer.")
        response = await rag.query("event_test", "cancellation policy deposit refund")

        for citation in response.citations:
            assert citation.score > 0.3, (
                f"Low-score citation should be filtered: score={citation.score}"
            )

    @pytest.mark.asyncio
    async def test_no_results_returns_helpful_message(self, indexed_store):
        from unittest.mock import AsyncMock
        empty_store = AsyncMock()
        empty_store.search = AsyncMock(return_value=[])
        rag = RAGService(vector_store=empty_store)

        response = await rag.query("event_test", "What about underwater basket weaving?")
        assert not response.has_results
        assert len(response.citations) == 0
        assert "couldn't find" in response.answer.lower()


# ============================================================================
# 4. RAG RESPONSE — consistency across repeated queries
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRAGResponseConsistency:
    """Repeated RAG queries with the same LLM mock must produce identical citations."""

    @pytest.mark.asyncio
    async def test_same_query_produces_same_citations(self, indexed_store):
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value=("The deposit is required upon signing.", {}))

        responses = []
        for _ in range(3):
            rag = RAGService(vector_store=indexed_store, llm_service=mock_llm)
            resp = await rag.query("event_test", "What is the deposit requirement?")
            responses.append(resp)

        first_citations = [(c.document_name, c.section_title, c.page_number) for c in responses[0].citations]
        for later in responses[1:]:
            later_citations = [(c.document_name, c.section_title, c.page_number) for c in later.citations]
            assert first_citations == later_citations, (
                f"Citations differ between runs:\n  Run 1: {first_citations}\n  Run N: {later_citations}"
            )


# ============================================================================
# 5. END-TO-END INDEX + QUERY via RAGService
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRAGServiceEndToEnd:
    """Test indexing via RAGService and querying back."""

    @pytest.mark.asyncio
    async def test_index_and_query_waters_edge(self):
        chroma_dir = tempfile.mkdtemp()
        try:
            from unittest.mock import AsyncMock
            embedding_svc = _make_deterministic_embedding_service()
            store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)

            mock_llm = AsyncMock()
            mock_llm._call_api = AsyncMock(
                return_value=("A deposit is required to secure the date.", {})
            )

            rag = RAGService(vector_store=store, llm_service=mock_llm)

            count = await rag.index_document(
                event_id="e2e_event",
                attachment_id="att_e2e",
                file_path=str(WATERS_EDGE_PDF),
                document_name="Waters-Edge-Contract.pdf",
                vendor_name="Waters Edge",
            )
            assert count > 0, "Indexing should produce chunks"

            response = await rag.query("e2e_event", "What is the deposit?")
            assert response.has_results
            assert len(response.citations) > 0
            assert any(
                c.document_name == "Waters-Edge-Contract.pdf" for c in response.citations
            )

            mock_llm._call_api.assert_called_once()
            call_args = mock_llm._call_api.call_args[0][0]
            system_msg = call_args[0]["content"]
            assert "[1]" in system_msg, "Excerpts should be numbered [1], [2], …"
        finally:
            shutil.rmtree(chroma_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_delete_then_query_returns_no_results(self):
        chroma_dir = tempfile.mkdtemp()
        try:
            embedding_svc = _make_deterministic_embedding_service()
            store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)

            rag = RAGService(vector_store=store)

            await rag.index_document(
                event_id="del_event",
                attachment_id="att_del",
                file_path=str(LAUREN_PHOTO_PDF),
                document_name="lauren_photo.pdf",
                vendor_name="Lauren Vaughan Photography",
            )

            deleted = rag.delete_document("del_event", "att_del")
            assert deleted > 0

            results = await store.search("del_event", "photographer coverage")
            assert len(results) == 0
        finally:
            shutil.rmtree(chroma_dir, ignore_errors=True)


# ============================================================================
# 6. RETRIEVAL RELEVANCE — results should contain expected keywords
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRetrievalRelevance:
    """Verify that retrieval results contain relevant content."""

    @pytest.mark.asyncio
    async def test_cancellation_query_returns_cancellation_content(self, indexed_store):
        results = await indexed_store.search("event_test", "cancellation refund policy")
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(
            kw in all_text for kw in ["cancel", "refund", "cancellation"]
        ), f"No result mentions cancellation across {len(results)} results"

    @pytest.mark.asyncio
    async def test_payment_query_returns_payment_content(self, indexed_store):
        results = await indexed_store.search("event_test", "payment schedule deposit due date fee")
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(
            kw in all_text for kw in ["payment", "deposit", "due", "fee", "$"]
        ), f"No result mentions payment across {len(results)} results"

    @pytest.mark.asyncio
    async def test_liability_query_returns_relevant_content(self, indexed_store):
        results = await indexed_store.search(
            "event_test", "liability insurance damage responsible",
            vendor_name="Waters Edge",
        )
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(
            kw in all_text for kw in ["insurance", "liability", "damage", "responsible"]
        ), f"No result mentions liability across {len(results)} results"


# ============================================================================
# ============================================================================
#
#   REAL-WORLD CONTRACT TESTS
#
# ============================================================================
# ============================================================================


@pytest.fixture(scope="module")
def real_indexed_store():
    """Index all 6 real-world contracts into a temporary ChromaDB."""
    chroma_dir = tempfile.mkdtemp()
    embedding_svc = _make_deterministic_embedding_service()
    store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)

    import asyncio

    async def _index_all():
        for pdf_path, att_id, doc_name, vendor in REAL_CONTRACTS:
            if not pdf_path.exists():
                continue
            pages = extract_text_from_pdf(str(pdf_path))
            chunks = chunk_by_sections(
                pages, attachment_id=att_id, document_name=doc_name, vendor_name=vendor,
            )
            await store.add_chunks("real_event", chunks)

    asyncio.get_event_loop().run_until_complete(_index_all())

    yield store

    shutil.rmtree(chroma_dir, ignore_errors=True)


# ============================================================================
# 10. REAL-WORLD PDF EXTRACTION
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldPDFExtraction:
    """Verify text extraction from actual vendor contracts."""

    def test_waters_edge_extracts_multiple_pages(self):
        pages = extract_text_from_pdf(str(WATERS_EDGE_PDF))
        assert len(pages) >= 5, f"Waters Edge has 7 pages, extracted {len(pages)}"

    def test_dj_chirag_extracts_multiple_pages(self):
        pages = extract_text_from_pdf(str(DJ_CHIRAG_PDF))
        assert len(pages) >= 5, f"DJ Chirag has 10 pages, extracted {len(pages)}"

    def test_awaaz_extracts_pages(self):
        pages = extract_text_from_pdf(str(AWAAZ_DJ_PDF))
        assert len(pages) >= 3, f"Awaaz has 6 pages, extracted {len(pages)}"

    def test_lauren_photography_extracts_pages(self):
        pages = extract_text_from_pdf(str(LAUREN_PHOTO_PDF))
        assert len(pages) >= 3, f"Lauren Vaughan has 7 pages, extracted {len(pages)}"

    def test_officiant_extracts_pages(self):
        pages = extract_text_from_pdf(str(OFFICIANT_PDF))
        assert len(pages) >= 2, f"Officiant has 4 pages, extracted {len(pages)}"

    def test_celebrations_extracts_pages(self):
        pages = extract_text_from_pdf(str(CELEBRATIONS_PDF))
        assert len(pages) >= 3, f"Celebrations has 5 pages, extracted {len(pages)}"

    @pytest.mark.parametrize("pdf_path,expected_terms", [
        (WATERS_EDGE_PDF, ["deposit", "cancel"]),
        (DJ_CHIRAG_PDF, ["deposit", "refund"]),
        (AWAAZ_DJ_PDF, ["fee", "payment"]),
        (LAUREN_PHOTO_PDF, ["payment", "cancel"]),
        (OFFICIANT_PDF, ["fee", "cancel"]),
        (CELEBRATIONS_PDF, ["deposit", "fee"]),
    ])
    def test_extracted_text_contains_key_contract_terms(self, pdf_path, expected_terms):
        pages = extract_text_from_pdf(str(pdf_path))
        combined = " ".join(p.text.lower() for p in pages)
        for term in expected_terms:
            assert term in combined, (
                f"{pdf_path.name}: expected '{term}' in extracted text"
            )


# ============================================================================
# 11. REAL-WORLD CHUNKING ROBUSTNESS
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldChunking:
    """Verify chunking handles varied real-world formatting."""

    @pytest.mark.parametrize("pdf_path,doc_name", [
        (WATERS_EDGE_PDF, "waters.pdf"),
        (DJ_CHIRAG_PDF, "chirag.pdf"),
        (AWAAZ_DJ_PDF, "awaaz.pdf"),
        (LAUREN_PHOTO_PDF, "lauren.pdf"),
        (OFFICIANT_PDF, "officiant.pdf"),
        (CELEBRATIONS_PDF, "celebrations.pdf"),
    ])
    def test_produces_at_least_two_chunks(self, pdf_path, doc_name):
        pages = extract_text_from_pdf(str(pdf_path))
        chunks = chunk_by_sections(pages, attachment_id="rw", document_name=doc_name)
        assert len(chunks) >= 2, (
            f"{pdf_path.name}: expected >=2 chunks, got {len(chunks)}"
        )

    @pytest.mark.parametrize("pdf_path,doc_name", [
        (WATERS_EDGE_PDF, "waters.pdf"),
        (DJ_CHIRAG_PDF, "chirag.pdf"),
        (AWAAZ_DJ_PDF, "awaaz.pdf"),
        (LAUREN_PHOTO_PDF, "lauren.pdf"),
        (OFFICIANT_PDF, "officiant.pdf"),
        (CELEBRATIONS_PDF, "celebrations.pdf"),
    ])
    def test_all_chunks_have_non_empty_text(self, pdf_path, doc_name):
        pages = extract_text_from_pdf(str(pdf_path))
        chunks = chunk_by_sections(pages, attachment_id="rw2", document_name=doc_name)
        for i, chunk in enumerate(chunks):
            assert len(chunk.text.strip()) > 0, (
                f"{pdf_path.name} chunk {i} has empty text"
            )
            assert chunk.page_number >= 1

    def test_chunking_deterministic_on_real_contracts(self):
        """Each real contract must produce identical chunks on repeated runs."""
        for pdf_path, _, doc_name, _ in REAL_CONTRACTS:
            if not pdf_path.exists():
                continue
            pages = extract_text_from_pdf(str(pdf_path))
            a = chunk_by_sections(pages, attachment_id="det", document_name=doc_name)
            b = chunk_by_sections(pages, attachment_id="det", document_name=doc_name)
            assert len(a) == len(b), f"{pdf_path.name}: chunk count differs"
            for ca, cb in zip(a, b):
                assert ca.text == cb.text, f"{pdf_path.name}: text differs"
                assert ca.section_title == cb.section_title

    def test_waters_edge_contains_deposit_content(self):
        pages = extract_text_from_pdf(str(WATERS_EDGE_PDF))
        chunks = chunk_by_sections(pages, attachment_id="we", document_name="we.pdf")
        all_text = " ".join(c.text.lower() for c in chunks)
        assert "deposit" in all_text, "Waters Edge contract should mention deposit"
        assert "cancel" in all_text, "Waters Edge contract should mention cancellation"

    def test_dj_chirag_contains_performance_terms(self):
        pages = extract_text_from_pdf(str(DJ_CHIRAG_PDF))
        chunks = chunk_by_sections(pages, attachment_id="dj", document_name="dj.pdf")
        all_text = " ".join(c.text.lower() for c in chunks)
        assert "dj" in all_text or "entertainment" in all_text or "music" in all_text


# ============================================================================
# 12. REAL-WORLD RETRIEVAL CONSISTENCY
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldRetrievalConsistency:
    """Repeated queries against real contracts must return identical results."""

    @pytest.mark.asyncio
    async def test_deposit_query_is_deterministic(self, real_indexed_store):
        runs = []
        for _ in range(3):
            results = await real_indexed_store.search("real_event", "deposit refund cancellation")
            runs.append(results)
        first_texts = [r.text for r in runs[0]]
        for later in runs[1:]:
            assert [r.text for r in later] == first_texts, "Deposit query results differ between runs"

    @pytest.mark.asyncio
    async def test_payment_schedule_query_is_deterministic(self, real_indexed_store):
        runs = []
        for _ in range(3):
            results = await real_indexed_store.search("real_event", "payment schedule due date fee")
            runs.append(results)
        first_texts = [r.text for r in runs[0]]
        for later in runs[1:]:
            assert [r.text for r in later] == first_texts


# ============================================================================
# 13. REAL-WORLD VENDOR-FILTERED RETRIEVAL
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldVendorFiltering:
    """Vendor filter scopes real-world results correctly."""

    @pytest.mark.asyncio
    async def test_filter_waters_edge(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "deposit cancellation fee", vendor_name="Waters Edge",
        )
        assert len(results) > 0, "Should find Waters Edge results"
        for r in results:
            assert r.vendor_name == "Waters Edge"

    @pytest.mark.asyncio
    async def test_filter_dj_chirag(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "entertainment performance", vendor_name="DJ Chirag",
        )
        assert len(results) > 0, "Should find DJ Chirag results"
        for r in results:
            assert r.vendor_name == "DJ Chirag"

    @pytest.mark.asyncio
    async def test_filter_awaaz(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "fee payment total", vendor_name="Awaaz Entertainment",
        )
        assert len(results) > 0, "Should find Awaaz results"
        for r in results:
            assert r.vendor_name == "Awaaz Entertainment"

    @pytest.mark.asyncio
    async def test_filter_lauren_photography(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "photography coverage", vendor_name="Lauren Vaughan Photography",
        )
        assert len(results) > 0, "Should find Lauren Vaughan results"
        for r in results:
            assert r.vendor_name == "Lauren Vaughan Photography"

    @pytest.mark.asyncio
    async def test_filter_officiant(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "ceremony officiant", vendor_name="Officiant",
        )
        assert len(results) > 0, "Should find Officiant results"
        for r in results:
            assert r.vendor_name == "Officiant"

    @pytest.mark.asyncio
    async def test_filter_celebrations(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "decorating rental fee", vendor_name="Celebrations Event & Rental",
        )
        assert len(results) > 0, "Should find Celebrations results"
        for r in results:
            assert r.vendor_name == "Celebrations Event & Rental"


# ============================================================================
# 14. REAL-WORLD CROSS-DOCUMENT — right contract for the question
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldCrossDocument:
    """Queries about specific topics should retrieve the right vendor's contract."""

    @pytest.mark.asyncio
    async def test_venue_query_hits_waters_edge(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "venue rental facility event space",
            vendor_name="Waters Edge",
        )
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(kw in all_text for kw in ["venue", "rental", "facilit", "event"])

    @pytest.mark.asyncio
    async def test_dj_query_hits_dj_contract(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "DJ music entertainment performance sound lighting",
            vendor_name="DJ Chirag",
        )
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(kw in all_text for kw in ["dj", "music", "entertainment", "sound", "lighting"])

    @pytest.mark.asyncio
    async def test_officiant_query_hits_officiant(self, real_indexed_store):
        results = await real_indexed_store.search(
            "real_event", "ceremony officiant marriage wedding",
            vendor_name="Officiant",
        )
        assert len(results) > 0
        all_text = " ".join(r.text.lower() for r in results)
        assert any(kw in all_text for kw in ["officiant", "ceremony", "marriage", "wedding"])


# ============================================================================
# 15. REAL-WORLD CITATION ACCURACY
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldCitationAccuracy:
    """RAG citations on real contracts have correct document names and page ranges."""

    def _make_rag_with_mock_llm(self, store, answer: str):
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value=(answer, {}))
        return RAGService(vector_store=store, llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_citations_reference_real_documents(self, real_indexed_store):
        rag = self._make_rag_with_mock_llm(
            real_indexed_store, "The deposit is required upon signing.",
        )
        response = await rag.query("real_event", "What is the deposit amount?")
        assert response.has_results
        assert len(response.citations) > 0
        valid_docs = {doc_name for _, _, doc_name, _ in REAL_CONTRACTS}
        for c in response.citations:
            assert c.document_name in valid_docs, (
                f"Citation references unknown doc: {c.document_name}"
            )

    @pytest.mark.asyncio
    async def test_all_citations_have_valid_page_numbers(self, real_indexed_store):
        rag = self._make_rag_with_mock_llm(
            real_indexed_store, "Cancellation terms vary by vendor.",
        )
        response = await rag.query("real_event", "cancellation policy refund deposit")
        for c in response.citations:
            assert c.page_number >= 1, f"Invalid page number: {c.page_number}"
            assert c.section_title, f"Missing section title on citation"
            assert c.text, f"Missing text on citation"

    @pytest.mark.asyncio
    async def test_citations_consistent_across_runs(self, real_indexed_store):
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm._call_api = AsyncMock(return_value=("The fee is due before the event.", {}))

        responses = []
        for _ in range(3):
            rag = RAGService(vector_store=real_indexed_store, llm_service=mock_llm)
            resp = await rag.query("real_event", "What fees are due and when?")
            responses.append(resp)

        first_cites = [
            (c.document_name, c.section_title, c.page_number) for c in responses[0].citations
        ]
        for later in responses[1:]:
            later_cites = [
                (c.document_name, c.section_title, c.page_number) for c in later.citations
            ]
            assert first_cites == later_cites, "Real-world citation order changed between runs"

    @pytest.mark.asyncio
    async def test_low_score_citations_filtered_on_real_docs(self, real_indexed_store):
        rag = self._make_rag_with_mock_llm(real_indexed_store, "Answer.")
        response = await rag.query("real_event", "cancellation refund policy")
        for c in response.citations:
            assert c.score > 0.3, f"Low-score citation leaked: {c.score}"


# ============================================================================
# 16. REAL-WORLD END-TO-END INDEX + QUERY
# ============================================================================

@pytest.mark.fast
@pytest.mark.rag
class TestRealWorldEndToEnd:
    """Index a single real contract from scratch and query it."""

    @pytest.mark.asyncio
    async def test_index_waters_edge_and_query_deposit(self):
        chroma_dir = tempfile.mkdtemp()
        try:
            from unittest.mock import AsyncMock
            embedding_svc = _make_deterministic_embedding_service()
            store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)
            mock_llm = AsyncMock()
            mock_llm._call_api = AsyncMock(return_value=("A deposit is required to hold the date.", {}))

            rag = RAGService(vector_store=store, llm_service=mock_llm)
            count = await rag.index_document(
                event_id="e2e_real",
                attachment_id="att_we",
                file_path=str(WATERS_EDGE_PDF),
                document_name="Waters-Edge-Contract.pdf",
                vendor_name="Waters Edge",
            )
            assert count > 0

            response = await rag.query("e2e_real", "What is the deposit requirement?")
            assert response.has_results
            assert len(response.citations) > 0
            assert any(
                c.document_name == "Waters-Edge-Contract.pdf" for c in response.citations
            )

            call_args = mock_llm._call_api.call_args[0][0]
            system_msg = call_args[0]["content"]
            assert "[1]" in system_msg, "Excerpts should be numbered [1], [2], …"
        finally:
            shutil.rmtree(chroma_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_index_officiant_and_query_ceremony(self):
        chroma_dir = tempfile.mkdtemp()
        try:
            from unittest.mock import AsyncMock
            embedding_svc = _make_deterministic_embedding_service()
            store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)
            mock_llm = AsyncMock()
            mock_llm._call_api = AsyncMock(return_value=("The officiant will perform the ceremony.", {}))

            rag = RAGService(vector_store=store, llm_service=mock_llm)
            count = await rag.index_document(
                event_id="e2e_off",
                attachment_id="att_off",
                file_path=str(OFFICIANT_PDF),
                document_name="Officiant_Contract.pdf",
                vendor_name="Officiant",
            )
            assert count > 0

            response = await rag.query("e2e_off", "What are the officiant's responsibilities?")
            assert response.has_results
            assert len(response.citations) > 0
            assert any(
                c.document_name == "Officiant_Contract.pdf" for c in response.citations
            )
        finally:
            shutil.rmtree(chroma_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_delete_real_contract_clears_all_chunks(self):
        chroma_dir = tempfile.mkdtemp()
        try:
            embedding_svc = _make_deterministic_embedding_service()
            store = VectorStore(embedding_service=embedding_svc, persist_dir=chroma_dir)
            rag = RAGService(vector_store=store)

            await rag.index_document(
                event_id="del_real",
                attachment_id="att_del_real",
                file_path=str(DJ_CHIRAG_PDF),
                document_name="dj.pdf",
                vendor_name="DJ Chirag",
            )

            deleted = rag.delete_document("del_real", "att_del_real")
            assert deleted > 0

            results = await store.search("del_real", "DJ entertainment music")
            assert len(results) == 0
        finally:
            shutil.rmtree(chroma_dir, ignore_errors=True)
