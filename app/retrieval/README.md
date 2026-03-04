# Retrieval Module (Phase 2)

This module is a placeholder for future vector database integration.

## Planned Features

- **Meeting Transcript Search**: Store and search meeting transcripts
- **Contract Q&A**: Query contract documents semantically
- **Decision Context**: Retrieve historical decision discussions

## Architecture

```
retrieval/
├── __init__.py
├── embeddings.py      # Embedding generation (OpenAI/local models)
├── vector_store.py    # Vector DB client (pgvector/Pinecone/Chroma)
├── chunking.py        # Document chunking strategies
└── rag.py             # RAG pipeline for Q&A
```

## Integration Points

- **Attachments table**: File metadata stored in relational DB
- **Vector DB**: Embeddings and chunks stored separately
- **Hybrid queries**: Route between relational and vector based on intent

## Implementation Notes

- Keep retrieval separate from capture endpoint
- Contract Q&A will be a dedicated `/retrieval/query` endpoint
- Use citation-based responses with source references
