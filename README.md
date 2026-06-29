# Tugma-AI

**Career-to-elective matcher for the Strengthened Senior High School curriculum.**

Tugma-AI interviews incoming Grade 11 students in English, Tagalog, or Taglish,
then recommends SSHS electives grounded in official DepEd curriculum documents.
It is a developer-focused case study in building a small, practical agentic RAG
system.

## Why This Exists

- SSHS replaces strands with flexible Academic and TechPro elective clusters.
- Students need career-to-elective guidance without reading policy documents.
- Recommendations should cite curriculum evidence, not generic LLM guesses.

## What It Does

- Builds a student profile from a relaxed chat, not a long form.
- Searches DepEd documents with hybrid retrieval and reranking.
- Maps careers, strengths, constraints, and hobbies to ranked electives.
- Returns markdown recommendations that Chainlit renders directly.

## Architecture

```mermaid
flowchart TD
    A[Chainlit app.py\nchat UI + graph runner] --> B[DeepAgents main agent\nintake + orchestration]
    B --> C[Retrieval subagent\nQdrant hybrid search + Jina rerank]
    B --> D[Matching subagent\ncareer-to-elective reasoning]
    C --> E[(Qdrant\nsshs_documents)]
    C --> F[Jina embeddings + reranker]
    D --> G[/recommendations.json\nPydantic validated]
    B --> H[(Redis\nLangGraph checkpoints)]
    B --> I[LangFuse\noptional tracing]
```

- `app.py` runs the Chainlit chat UI and streams the graph.
- `src/agents/` owns DeepAgents orchestration and subagent prompts.
- `src/core/` wraps LLM, Qdrant, Redis, Jina, Guardrails, and LangFuse adapters.

## Pipeline

| Stage | Output |
|---|---|
| Intake | `/profile.json` with career, strengths, constraints, hobbies, and values |
| Retrieval | `/retrieved_chunks.md` with relevant DepEd curriculum evidence |
| Matching | `/recommendations.json` plus markdown recommendations in chat |

## Key Decisions

| Decision | Why |
|---|---|
| DeepAgents over raw LangGraph | Subagent delegation and middleware are built in. |
| FilesystemMiddleware for state | Virtual files keep inter-agent contracts simple and visible. |
| Hybrid search over dense-only | BM25 helps with acronyms, curriculum terms, and mixed-language queries. |
| Jina rerank after Qdrant | Keeps retrieval broad first, then improves final precision. |
| Markdown output over custom cards | Same user value with less fragile UI plumbing. |
| Input-only guardrails | Output is already constrained by retrieval, prompts, and Pydantic. |
| Relaxed intake | Better chat UX than forcing every profile field up front. |

## Run Locally

Prerequisites:

- Python 3.11+
- Docker + docker compose
- Jina AI API key
- OpenAI-compatible LLM endpoint
- LangFuse account, optional

```bash
git clone <repo-url>
cd tugma-ai
uv sync
cp .env.example .env
```

Fill in `.env`, then ingest the DepEd documents once:

```bash
uv run python -m ingestion.ingest
```

Start Redis/Qdrant and the chat UI:

```bash
docker compose up -d
uv run chainlit run app.py
```

Try:

```text
Gusto ko maging nurse, pero hindi ako sure kung anong electives kukunin.
```

## Notes

- Biggest simplification: markdown recommendations replaced custom UI cards.
- Biggest cost win: short reranker snippets cut Jina token use by about 30x.
- Biggest UX win: intake asks 1-2 questions at a time and stops when enough.

For full architecture history, see `docs/adr/001-project-foundation.md`.
