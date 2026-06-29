# Law Case RAG

A semantic search and chat system for legal case files. Upload PDFs, ask questions, get answers grounded in the actual case text — with memory across a conversation.

---

## What it does

- **PDF ingestion** — extracts structured metadata and clean text from legal case documents, processed asynchronously via a job queue
- **Two-stage semantic search** — queries case summaries first to suggest relevant cases, then searches specific chunks within a selected case
- **Re-ranking** — fetches top 15 chunks via vector similarity, re-ranks with a cross-encoder model, passes top 5 to LLM for higher answer precision
- **LLM answers with streaming** — builds context-aware prompts from retrieved excerpts and chat history, streams responses back incrementally
- **Citation tracking** — LLM references specific excerpts by page range; citations are appended at the end of each streamed response
- **Rolling summaries** — during ingestion, builds a progressive summary across 2-page chunks, then compresses into a short paragraph stored in Qdrant
- **Conversation memory** — session-based chat history in Postgres, filters weak responses, limits to last N messages to keep context clean
- **Async processing** — upload returns instantly with a `case_id`; background worker handles chunking, embedding, and summarization

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI |
| Embeddings | SentenceTransformer (`BAAI/bge-base-en-v1.5`) |
| Re-ranker | CrossEncoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| Vector store | Qdrant (2 collections: chunks + summaries) |
| Relational DB | Postgres (async SQLAlchemy) |
| LLM | Ollama (configurable model) |
| PDF parsing | PyMuPDF |
| Job queue | ARQ + Redis |
| Migrations | Alembic |

---

## Getting started

### 1. Copy and fill env vars
```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres async connection string |
| `QDRANT_URL` | Qdrant instance URL |
| `QDRANT_COLLECTION_NAME` | Collection name for case chunks |
| `QDRANT_SUMMARY_COLLECTION_NAME` | Collection name for case summaries |
| `QDRANT_VECTOR_SIZE` | Embedding vector size (768 for bge-base) |
| `LLM_URL` | Ollama base URL (e.g. `http://localhost:11434`) |
| `LLM_MODEL` | Model name (e.g. `mistral:7b-instruct`) |

### 2. Start Redis
```bash
brew services start redis
```

### 3. Run migrations
```bash
alembic upgrade head
```

### 4. Start the API
```bash
uvicorn app.main:app --reload
```

### 5. Start the worker (separate terminal)
```bash
arq app.worker.settings.WorkerSettings
```

---

## API

### Upload a case
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@case.pdf"
# returns case_id + status: pending
```

### Check processing status
```bash
curl http://localhost:8000/api/cases/{case_id}/status
```

### Search / discover cases
```bash
# no case_id — returns relevant cases for user to pick
curl -N "http://localhost:8000/api/search?q=wrongful+termination+maharashtra"

# with case_id — streams LLM answer with citations
curl -N "http://localhost:8000/api/search?q=who+is+the+appellant&case_id=<uuid>&stream=true"

# follow-up with session
curl -N "http://localhost:8000/api/search?q=what+was+the+verdict&case_id=<uuid>&session_id=<uuid>&stream=true"
```

### Citation format
Citations are appended at the end of each streamed response:
```
...LLM answer text...

###CITATIONS###{"citations": [{"excerpt": 1, "page_range": "Page 1-2", "chunk_index": 0}]}
```

---

## Project structure

```
app/
  services/     # Core logic: search, embeddings, LLM, re-ranking
  pipelines/    # PDF parsing, chunking, and text utilities
  db/           # Postgres + Qdrant clients and models
  constants/    # Prompt templates and config constants
  worker/       # ARQ worker tasks, settings, and Redis pool
alembic/        # DB migrations
scripts/        # Utility scripts
```

---

## TODO

- `.env.example`
- Auth and rate limiting
- Automated tests and CI
- Query expansion for better retrieval
- Observability / LLM call logging