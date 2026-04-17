# EventOps Cloud Migration Plan

## Overview

EventOps is a Python/FastAPI app with four infrastructure dependencies that need
cloud equivalents before it can run reliably outside a local machine:

| Local | Cloud replacement |
|---|---|
| SQLite (`eventops.db`) | Supabase PostgreSQL |
| `uploads/` directory | Supabase Storage (S3-compatible) |
| `chroma_db/` (ChromaDB) | Supabase `pgvector` extension |
| `uvicorn` on localhost | Containerized FastAPI on Railway |

The frontend (vanilla JS SPA) is served directly by FastAPI and can stay that
way — extracting it to Vercel adds CORS complexity with zero meaningful benefit
for a single-team app.

---

## Why not Vercel for the backend?

Vercel serverless functions have a 10-second timeout (30s on Pro). This app
makes multi-step LLM calls and streaming SSE responses that routinely exceed
that. **Railway, Render, or Fly.io are better fits** — they run persistent
containers, support long-lived connections, and are similarly cheap to start.

---

## Architecture after migration

```
Browser
  └─► Railway (Docker container — FastAPI + Uvicorn)
        ├─► Supabase PostgreSQL  (events, vendors, payments, tasks …)
        ├─► Supabase Storage     (uploaded PDFs, invoices, images)
        └─► Supabase pgvector    (contract embeddings, one table per event)
```

External APIs (OpenRouter, OpenAI embeddings) are unchanged.

---

## Phase 1 — Database: SQLite → Supabase PostgreSQL

**Effort: low.** The codebase already has `asyncpg` in scope and SQLAlchemy
is already configured to accept a `DATABASE_URL` env var.

### Steps

1. Create a Supabase project at supabase.com. Copy the connection string from
   *Project Settings → Database → URI* (use the **pooler / transaction mode**
   string for serverless-safe connections, or the direct string for a
   long-lived container).

2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:[password]@[host]:5432/postgres
   ```

3. Remove `aiosqlite` from `requirements.txt`, confirm `asyncpg` is listed.

4. On first deploy, SQLAlchemy's `create_all` (called in the lifespan handler
   in `app/main.py`) will create all tables automatically. No migration tool is
   required right now; add Alembic if the schema needs to evolve later.

5. Verify: hit `/health` after deploy and check Supabase table editor.

### Code change

None beyond the env var. The ORM models and async sessions are already
PostgreSQL-compatible.

---

## Phase 2 — File storage: local `uploads/` → Supabase Storage

**Effort: medium.** All upload/download logic is isolated in
`app/routers/attachments.py`. Two functions need rewriting:
- the `POST /attachments` upload handler (currently writes to disk)
- the `GET /attachments/{id}/download` handler (currently reads from disk)

### Steps

1. In Supabase, create a private bucket called `eventops-uploads`.

2. Add to `.env`:
   ```
   SUPABASE_URL=https://[project-ref].supabase.co
   SUPABASE_SERVICE_KEY=[service_role_key]
   STORAGE_BUCKET=eventops-uploads
   ```

3. Add `supabase` (Python client) to `requirements.txt`.

4. Replace the disk-write in the upload handler with:
   ```python
   from supabase import create_client
   sb = create_client(settings.supabase_url, settings.supabase_service_key)
   sb.storage.from_(settings.storage_bucket).upload(
       path=f"{event_id}/{file.filename}",
       file=await file.read(),
       file_options={"content-type": file.content_type},
   )
   ```
   Store the storage path (not a local path) in the `attachments.file_path`
   column.

5. Replace the disk-read in the download handler with a signed URL:
   ```python
   signed = sb.storage.from_(settings.storage_bucket).create_signed_url(
       path=attachment.file_path, expires_in=300
   )
   return RedirectResponse(signed["signedURL"])
   ```

6. The RAG indexing path in `app/retrieval/rag_service.py` downloads the file
   before chunking. Replace the local `open()` call with a streaming download
   from Supabase Storage using `httpx`.

7. Remove the `uploads/` directory and the `StaticFiles` mount for it (if any).

---

## Phase 3 — Vector store: ChromaDB → Supabase pgvector

**Effort: medium-high.** This is the most significant change but it removes an
entire stateful dependency (the `chroma_db/` directory) and keeps everything in
one database.

### Steps

1. Enable the `pgvector` extension in Supabase:
   ```sql
   create extension if not exists vector;
   ```

2. Create an embeddings table:
   ```sql
   create table document_chunks (
     id          uuid primary key default gen_random_uuid(),
     event_id    uuid not null references events(id) on delete cascade,
     source_file text not null,
     chunk_text  text not null,
     embedding   vector(1536)   -- text-embedding-3-small dimension
   );

   create index on document_chunks
     using ivfflat (embedding vector_cosine_ops)
     with (lists = 100);
   ```

3. Rewrite `app/retrieval/vector_store.py`. The public interface is:
   - `upsert_chunks(event_id, chunks: list[dict])` — replace with bulk
     `INSERT … ON CONFLICT DO UPDATE`
   - `query_similar(event_id, query_embedding, top_k)` → replace with:
     ```sql
     select chunk_text, 1 - (embedding <=> $1) as score
     from document_chunks
     where event_id = $2
     order by embedding <=> $1
     limit $3
     ```
   - `delete_event_collection(event_id)` → `DELETE FROM document_chunks WHERE event_id = $1`

4. Use `asyncpg` directly (already a transitive dependency via SQLAlchemy) or
   add `psycopg[binary]` for the vector queries — either works fine.

5. Remove `chromadb` from `requirements.txt` and delete `chroma_db/` from
   `.gitignore` / the repo.

---

## Phase 4 — Containerization

**Effort: low.** Needed so Railway (or any other host) can run the app
reproducibly.

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> `libmupdf-dev` is required by PyMuPDF. If the `pymupdf` wheel bundles its own
> MuPDF (it usually does on Linux), the `apt-get` line can be removed.

### `docker-compose.yml` (local dev only)

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - .:/app   # hot-reload in dev; remove for production image
```

### `.dockerignore`

```
__pycache__
*.pyc
.env
eventops.db
test_eventops.db
chroma_db/
uploads/
.git
```

---

## Phase 5 — Deploy to Railway

1. Push the repo (with Dockerfile) to GitHub.
2. Create a Railway project, add a service from the GitHub repo.
3. Set all env vars in Railway's dashboard:
   - `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `STORAGE_BUCKET`
   - `OPENROUTER_API_KEY`, `OPENAI_API_KEY`
   - `ENVIRONMENT=production`
4. Railway auto-detects the Dockerfile and builds on every push to `main`.
5. Assign a Railway subdomain (free) or a custom domain.

**Estimated cost at zero/low traffic**: ~$5/month (Railway Hobby plan).
Supabase free tier covers 500 MB DB + 1 GB storage which is plenty to start.

---

## What Vercel is good for here

If you ever want the frontend to load faster globally (CDN edge caching), you
can extract `frontend/` into a separate Vercel project. The steps would be:
1. Move `frontend/index.html` + `frontend/static/` into a standalone repo.
2. Update the JS `fetch()` base URL to point to the Railway backend.
3. Add CORS middleware to FastAPI allowing the Vercel domain.

This is **optional and not recommended initially** — it adds operational
complexity (two deploys, CORS headers, separate repos) for a marginal
performance gain.

---

## Migration sequence (recommended order)

```
1. Supabase PostgreSQL  (one env var change, zero code changes)
2. Containerize         (Dockerfile + docker-compose)
3. Deploy to Railway    (validates the container works end-to-end)
4. Supabase Storage     (swap upload/download handlers)
5. pgvector             (swap vector_store.py)
```

Do steps 1–3 first. Once the app is running in the cloud with a real database,
file storage and vector migration can be done incrementally without downtime.

---

## Open questions before starting

- **Multi-tenancy**: right now there's no auth layer. Before going public,
  add Supabase Auth (JWT row-level security) or at minimum an API key gate.
- **Backups**: Supabase free tier includes daily backups. Verify this is
  sufficient or enable point-in-time recovery on a paid plan.
- **Secrets management**: use Railway's secret store (or Doppler) rather than
  committing `.env` files.
- **Re-indexing on migration**: existing ChromaDB vectors won't transfer.
  After switching to pgvector, trigger a re-index of all attachments via the
  existing `POST /admin/reindex` endpoint.
