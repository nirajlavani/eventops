import logging
import ssl
from typing import Optional

import certifi
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
OPENROUTER_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_MODEL = "text-embedding-3-small"
BATCH_SIZE = 96


class EmbeddingService:
    """Generate embeddings via OpenAI or OpenRouter API.

    Prefers OPENAI_API_KEY when available. Falls back to OPENROUTER_API_KEY
    so users only need a single API key for the entire application.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        settings = get_settings()
        if api_key:
            self.api_key = api_key
            self.base_url = OPENAI_EMBEDDING_URL
            logger.info("EmbeddingService: using explicit API key -> %s", OPENAI_EMBEDDING_URL)
        elif settings.openrouter_api_key:
            self.api_key = settings.openrouter_api_key
            self.base_url = OPENROUTER_EMBEDDING_URL
            logger.info("EmbeddingService: using OPENROUTER_API_KEY -> %s", OPENROUTER_EMBEDDING_URL)
        elif settings.openai_api_key:
            self.api_key = settings.openai_api_key
            self.base_url = OPENAI_EMBEDDING_URL
            logger.info("EmbeddingService: using OPENAI_API_KEY -> %s", OPENAI_EMBEDDING_URL)
        else:
            self.api_key = ""
            self.base_url = OPENAI_EMBEDDING_URL
            logger.warning("EmbeddingService: no API key configured")
        self.model = model
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            self._client = httpx.AsyncClient(timeout=60.0, verify=ssl_ctx)
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, batching if needed. Returns one vector per input text."""
        if not self.api_key:
            raise RuntimeError(
                "No embedding API key configured. "
                "Set OPENAI_API_KEY or OPENROUTER_API_KEY in your .env file."
            )

        logger.debug("Embedding %d texts via %s (model=%s)", len(texts), self.base_url, self.model)
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            embeddings = await self._embed_batch(batch)
            all_embeddings.extend(embeddings)

        logger.debug("Embedding complete: %d vectors returned", len(all_embeddings))
        return all_embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }

        response = await client.post(self.base_url, headers=headers, json=payload)
        if response.status_code != 200:
            logger.error(
                "Embedding API error: status=%d url=%s body=%s",
                response.status_code, self.base_url, response.text[:500],
            )
        response.raise_for_status()

        data = response.json()
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_items]

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        results = await self.embed_texts([query])
        return results[0]

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
