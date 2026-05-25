# Law Case RAG

A semantic search and chat system for legal case files. Upload PDFs, ask questions, get answers grounded in the actual case text — with memory across a conversation.

---

## What it does

- **Ingest PDFs** — extracts structured metadata and clean text from legal case documents
- **Semantic search** — finds the most relevant case excerpts for any query using vector similarity
- **LLM answers with streaming** — builds context-aware prompts from retrieved excerpts and chat history, streams responses back incrementally
- **Conversation memory** — maintains chat sessions in Postgres so follow-up questions have context
- **Case filtering** — scope any search to a specific case by `case_id`

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI |
| Embeddings | SentenceTransformer (`BAAI/bge-base-en-v1.5`) |
| Vector store | Qdrant |
| Relational DB | Postgres (async SQLAlchemy) |
| LLM | Ollama (configurable model) |
| PDF parsing | PyMuPDF |
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
| `QDRANT_COLLECTION` | Collection name for vectors |
| `LLM_URL` | Ollama base URL (e.g. `http://localhost:11434`) |
| `LLM_MODEL` | Model name (e.g. `mistral:7b-instruct`) |

### 2. Run migrations
```bash
alembic upgrade head
```

### 3. Start the API
```bash
uvicorn app.main:app --reload
```

---

## Project structure

```
app/
  services/     # Core logic: search, embeddings, LLM streaming
  pipelines/    # PDF parsing and chunking
  db/           # Postgres + Qdrant clients and models
  constants/    # Prompt templates and config constants
alembic/        # DB migrations
scripts/        # Utility scripts
```

---

## TODO

- `.env.example` and run instructions
- Sample PDFs for testing
- Auth and rate limiting
- Automated tests and CI