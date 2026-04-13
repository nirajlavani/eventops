import logging
from dataclasses import dataclass
from typing import Optional

import chromadb

from app.config import get_settings
from app.retrieval.chunking import Chunk
from app.retrieval.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    text: str
    page_number: int
    section_title: str
    attachment_id: str
    document_name: str
    vendor_name: str | None
    score: float


class VectorStore:
    """Persistent ChromaDB wrapper scoped per event."""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        persist_dir: Optional[str] = None,
    ):
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.embedding_service = embedding_service or EmbeddingService()
        self._client: Optional[chromadb.ClientAPI] = None

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            logger.info("Initializing ChromaDB at %s", self.persist_dir)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
        return self._client

    def _collection_name(self, event_id: str) -> str:
        safe = event_id.replace("-", "")[:48]
        return f"event_{safe}"

    def _get_or_create_collection(self, event_id: str) -> chromadb.Collection:
        client = self._get_client()
        return client.get_or_create_collection(
            name=self._collection_name(event_id),
            metadata={"hnsw:space": "cosine"},
        )

    async def add_chunks(self, event_id: str, chunks: list[Chunk]) -> int:
        """Embed and upsert chunks into the collection for an event. Returns count added."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_texts(texts)

        collection = self._get_or_create_collection(event_id)

        ids = [f"{c.attachment_id}_{c.chunk_index}" for c in chunks]
        metadatas = [
            {
                "page_number": c.page_number,
                "section_title": c.section_title,
                "attachment_id": c.attachment_id,
                "document_name": c.document_name,
                "vendor_name": c.vendor_name or "",
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(
            "Indexed %d chunks for event %s from %s",
            len(chunks), event_id, chunks[0].document_name,
        )
        return len(chunks)

    async def search(
        self,
        event_id: str,
        query: str,
        top_k: int = 5,
        vendor_name: str | None = None,
    ) -> list[SearchResult]:
        """Search for chunks matching a query. Optionally filter by vendor name."""
        query_embedding = await self.embedding_service.embed_query(query)

        collection = self._get_or_create_collection(event_id)
        total_chunks = collection.count()
        logger.info(
            "Searching event=%s collection=%s total_chunks=%d query=%r vendor_filter=%s top_k=%d",
            event_id, self._collection_name(event_id), total_chunks,
            query[:80], vendor_name, top_k,
        )
        if total_chunks == 0:
            logger.warning("Collection is empty for event %s — no documents indexed", event_id)
            return []

        where_filter = None
        if vendor_name:
            where_filter = {"vendor_name": {"$eq": vendor_name}}
            probe = collection.get(where=where_filter, limit=1, include=[])
            if not probe["ids"]:
                logger.info(
                    "Vendor filter '%s' matched 0 chunks, retrying without filter",
                    vendor_name,
                )
                where_filter = None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, total_chunks),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results["distances"][0]

            for doc, meta, dist in zip(docs, metas, distances):
                score = 1.0 - dist
                search_results.append(SearchResult(
                    text=doc,
                    page_number=meta.get("page_number", 0),
                    section_title=meta.get("section_title", ""),
                    attachment_id=meta.get("attachment_id", ""),
                    document_name=meta.get("document_name", ""),
                    vendor_name=meta.get("vendor_name") or None,
                    score=score,
                ))

        logger.info(
            "Search returned %d results, scores: %s",
            len(search_results),
            [round(r.score, 3) for r in search_results],
        )
        return search_results

    def delete_by_attachment(self, event_id: str, attachment_id: str) -> int:
        """Remove all chunks belonging to a specific attachment."""
        collection = self._get_or_create_collection(event_id)
        if collection.count() == 0:
            return 0

        existing = collection.get(
            where={"attachment_id": {"$eq": attachment_id}},
        )
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            logger.info("Deleted %d chunks for attachment %s", len(existing["ids"]), attachment_id)
            return len(existing["ids"])
        return 0
