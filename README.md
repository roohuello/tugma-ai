# Tugma-AI

**Career-to-elective matcher for the Strengthened Senior High School curriculum.**

An AI agent that interviews incoming Grade 11 students about their career aspirations
and recommends elective subjects aligned with their profile — powered by official
DepEd curriculum documents.

---

## Overview

With the new Strengthened SHS curriculum (DepEd Order No. 017, s. 2026), students
have freedom to choose elective subjects across 15 clusters spanning Academic and
Technical-Professional tracks. Tugma-AI helps students navigate this choice through
a conversational AI experience.

### How it works

1. Student chats in English, Tagalog, or Taglish about their career goals
2. AI profiles them across 11 dimensions (career, skills, hobbies, values, etc.)
3. Matches profile against official DepEd curriculum documents
4. Recommends elective subjects with personalized reasoning

### Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (GET /health only) |
| Agent Framework | DeepAgents (LangGraph + LangChain substrate) |
| Frontend | Chainlit |
| Vector Search | Qdrant (hybrid: dense + sparse) |
| Session State | Redis (LangGraph AsyncRedisSaver) |
| Embeddings | Jina AI (jina-embeddings-v5-text-small) |
| Reranker | Jina AI (jina-reranker-v3) |
| Document Ingestion | LlamaIndex |
| Observability | LangFuse |
| Input Guardrails | Guardrails AI |
| LLM | Any OpenAI-compatible endpoint |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + docker compose (for Redis + Qdrant)
- Jina AI API key (free tier: 10M tokens)
- OpenAI-compatible LLM endpoint
- LangFuse account (optional, for observability)

### Setup

```bash
git clone <repo-url>
cd tugma-ai

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Fill in .env with your API keys

# Ingest DepEd documents (run once)
uv run python -m ingestion.ingest

# Start backend services
docker compose up -d

# Start frontend
uv run chainlit run frontend/app.py
```

### Architecture Decision Records

See `docs/adr/` for all architecture decisions.

---

## License

MIT
