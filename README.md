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
| API | FastAPI (async, SSE streaming) |
| Agent Framework | DeepAgents (LangGraph + LangChain substrate) |
| Frontend | Chainlit |
| Vector Search | Qdrant (hybrid: dense + sparse) |
| Session State | Redis (LangGraph AsyncRedisSaver) |
| Rate Limiting | Redis token-bucket |
| Embeddings | Jina AI (jina-embeddings-v3) |
| Reranker | Jina AI (jina-reranker-v2) |
| Document Ingestion | LlamaIndex |
| Observability | LangFuse |
| Input Guardrails | Guardrails AI |
| LLM | Any OpenAI-compatible endpoint |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Qdrant Cloud account (free tier sufficient)
- Redis Cloud account (free tier sufficient)
- Jina AI API key (free tier: 10M tokens)
- OpenAI-compatible LLM endpoint
- LangFuse account (optional, for observability)

### Setup

```bash
git clone <repo-url>
cd tugma-ai

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Fill in .env with your API keys

# Ingest DepEd documents (run once)
python -m ingestion.ingest

# Start backend
uvicorn src.main:app --reload

# Start frontend (separate terminal)
chainlit run frontend/app.py
```

### Architecture Decision Records

See `docs/adr/` for all architecture decisions.

---

## License

MIT
