# ADR 001: Project Foundation — Tugma-AI

**Date:** 2026-06-19
**Status:** Accepted (Revised after grill-with-docs + grilling session — 52 decisions. Amended 2026-06-24: simplified to 2 subagents, single model, removed translator)

---

## Context

The Strengthened Senior High School (SSHS) curriculum, per DepEd Order No. 017 s. 2026,
replaces the old 4-track/strand system with 2 tracks (Academic, Technical-Professional)
and flexible elective clusters. Students choose electives freely across clusters via a
"doorway option." No public data exists on what specific electives individual schools offer.

Tugma-AI is a conversational AI for incoming Grade 11 students that interviews them about
career aspirations, hobbies, academic strengths, and work values, then recommends
elective subjects aligned with their profile. It is a production-grade portfolio piece
demonstrating AI engineering depth.

---

## Architecture

### Pattern: Hexagonal (Ports & Adapters)

```
frontend/ (Chainlit, runs graph) ──→ agents/ (DeepAgents domain)
                                         ↓
                                    core/ (Ports: LLM, Qdrant, Redis, Jina, Guardrails)
                                         ↓
                                    models/ (Shared Kernel: Pydantic)
```

- **Domain logic** (`agents/`) depends on abstract ports (`core/`), never on frameworks.
- **Adapters** (`frontend/`) drive the domain. Swappable without touching agents.
- **Ingestion** (`ingestion/`) is an offline tool outside the runtime.
- **Shared Kernel** (`models/`) ensures all layers speak the same data contracts.
- FastAPI reduced to `GET /health` only (`src/main.py`). Graph executes in Chainlit.
- **Hexagonal depth:** Concrete with protocol. `core/` wraps external libraries directly —
  agents call `core/qdrant.hybrid_search()`, never `qdrant_client` directly.
  Swap = edit one `core/` file.

### Deployment: Docker + Fly.io

- **Container:** Single `Dockerfile` based on `python:3.13-slim-bookworm`.
  Three processes managed by `supervisord`: redis-server (port 6379), uvicorn (port 8001), chainlit (port 8000).
- **Platform:** Fly.io, Singapore region (`sin`). Secrets via `fly secrets set`.
- **Redis persistence:** Redis runs per-deploy with no Fly volume. Session data is ephemeral —
  sessions don't survive redeploys. Acceptable for portfolio demo scope. No volume cost.
- **`fly.toml`** committed to repo for reproducible deploys. Health check via TCP on port 8000.

### Agent Framework: DeepAgents (with LangGraph substrate)

**Decision:** Use `create_deep_agent()` from DeepAgents, not raw LangGraph `StateGraph`.

DeepAgents provides:
- Built-in subagent delegation (`task()` tool)
- Auto-assembled middleware stack (TodoList, Filesystem)
- `HumanInTheLoopMiddleware` via `interrupt_on` top-level parameter
- Backend abstraction (`StateBackend` — ephemeral, per-thread)
- Pluggable checkpointing and store (`AsyncRedisSaver`, `RedisStore`)
- Returns `CompiledStateGraph` — LangGraph v2 streaming works underneath

### Agent Architecture: Main Orchestrator + 2 Subagents

```
Main Agent (Intake/Orchestrator)
│  tools=[contradiction_check, emit_stage]   ← HITL trigger + stage signals
│
├── Subagent: Retrieval          Qdrant hybrid search + Jina rerank
└── Subagent: Matching           career → elective reasoning + structured output

Middleware (auto-assembled + top-level):
  TodoListMiddleware              Auto-included. Planning + step tracking.
  FilesystemMiddleware            Auto-included. Virtual files for inter-agent state.
  HumanInTheLoopMiddleware        interrupt_on={"contradiction_check": True}

Backend:
  StateBackend()                  Ephemeral session data (per-thread)

Store:        RedisStore (langgraph-redis)    Persistent memory (future use)
Checkpointer: AsyncRedisSaver                 Per-session graph state (auto-checkpoint)

Redis runs locally in Docker container (redis://localhost:6379/0). No external Redis Cloud.
```

### DeepAgents Native Patterns

**Subagent delegation:** The main agent handles the intake conversation. When ready to progress, it
delegates to subagents via the built-in `task()` tool — no manual graph edge wiring.

**Subagent format:** TypedDicts with `name`, `description`, `system_prompt` (all required) plus
optional `tools`, `model`, `middleware`, `interrupt_on`, `skills`, `permissions`.
`response_format` is a top-level `create_deep_agent()` parameter only — NOT available per-subagent.
Structured output for the matching subagent achieved via JSON schema in the system prompt + Pydantic validation on read.

**Inter-agent communication:** Via FilesystemMiddleware's virtual filesystem:
- `/profile.json` — `StudentProfile`, written by main agent
- `/retrieved_chunks.md` — Qdrant results + Jina reranked snippets, written by retrieval subagent
- `/recommendations.json` — `ElectiveRecommendation`, written by matching subagent

All agents read/write these via built-in `read_file`/`write_file` tools auto-injected by
FilesystemMiddleware. System prompts explicitly reference which files to read/write and when.

**Streaming:** `create_deep_agent()` returns `CompiledStateGraph`. Chainlit streams via
`agent.astream(input, stream_mode=["custom"], version="v2", config=...)`.
`cl.LangchainCallbackHandler()` handles token streaming automatically — no `"messages"` stream mode needed.
Only `"custom"` mode for `cl.Step` stage updates and recommendations delivery.

**Model passing:** `ChatModel` objects (from `core/llm.py`) passed to `create_deep_agent(model=...)`
and subagent dicts — not provider strings. Supports any OpenAI-compatible endpoint configured via `.env`.

**Session persistence:** `AsyncRedisSaver` as `checkpointer` + `AsyncRedisStore` as `store`.
DeepAgents auto-checkpoints after every agent turn. `thread_id` = `cl.context.session.id`.
Session TTL: 30-minute Redis TTL dict `{"default_ttl": 30, "refresh_on_read": True}` — active
sessions refresh on read, idle ones expire. Store wired but dormant — future cross-session memory.
Local dev: `docker-compose.yml` with `redis:alpine`, volume-persisted `/data`, AOF + RDB.
Fallback: `MemorySaver` + `InMemoryStore` if Redis unreachable.

### Chainlit Runs the Graph

Chainlit owns graph execution. FastAPI is a thin sidecar (`GET /health` only).
In Docker, Chainlit must bind to all interfaces: `chainlit run frontend/app.py --host 0.0.0.0 --port 8000`.

```python
# frontend/app.py — lazy singleton init pattern

_saver: AsyncRedisSaver | None = None
_store: AsyncRedisStore | None = None

@cl.on_chat_start
async def on_chat_start():
    global _saver, _store
    if _saver is None:
        _saver = get_checkpointer()
        await _saver.asetup()
        _store = get_store()
        await _store.setup()

    agent = create_deep_agent(
        model=chat_model,           # ChatModel object from core/llm.py
        system_prompt=INTAKE_SYSTEM_PROMPT,
        subagents=[retrieval_subagent, matching_subagent],
        tools=[contradiction_check, emit_stage],
        backend=StateBackend(),
        checkpointer=_saver,
        store=_store,
        interrupt_on={"contradiction_check": True},
    )
    cl.user_session.set("agent", agent)

@cl.on_message
async def on_message(msg: cl.Message):
    # Guardrails: input validation
    try:
        guard.validate(msg.content)
    except ValidationError:
        await cl.Message(content="Paumanhin, may nakita akong sensitibong impormasyon...").send()
        return

    agent = cl.user_session.get("agent")
    langfuse_handler = CallbackHandler()
    cb = cl.LangchainCallbackHandler()
    config = {"callbacks": [cb, langfuse_handler],
              "configurable": {"thread_id": cl.context.session.id}}

    # Check if resuming from HITL interrupt
    interrupted = cl.user_session.get("interrupted")
    if interrupted:
        cl.user_session.set("interrupted", False)
        input_msg = Command(resume={"decisions": [{"type": "approve"}]})
    else:
        input_msg = {"messages": [HumanMessage(content=msg.content)]}

    async with cl.Step(name="Getting to know you...", type="run") as step:
        step.input = msg.content
        final_msg = cl.Message(content="")

        async for mode, chunk in agent.astream(
            input_msg,
            stream_mode=["custom"],
            version="v2",
            config=config,
        ):
            if mode == "custom":
                if chunk.get("type") == "stage":
                    step.name = chunk["name"]
                elif chunk.get("type") == "recommendations":
                    # Render ElectiveCard custom elements
                    for subject in chunk["data"].recommendations:
                        card = cl.CustomElement(
                            name="ElectiveCard",
                            props=subject.model_dump(),
                            display="inline",
                        )
                        await cl.Message(content="", elements=[card]).send()
                    # LangFuse scoring
                    span = langfuse_handler.current_span
                    if span:
                        span.score(
                            name="profile_completeness",
                            value=profile_completeness(chunk["data"].profile),
                            data_type="NUMERIC",
                        )
                elif chunk.get("type") == "token":
                    await final_msg.stream_token(chunk["content"])

        step.output = "Done"
        await final_msg.send()

    # After stream loop: check for HITL interrupt
    state = agent.get_state(config)
    if state.next:
        cl.user_session.set("interrupted", True)
        # Agent already sent contradiction message. Wait for user reply.
```

### Streaming: Dual Callbacks + cl.Step

Two callbacks coexist additively in LangChain's callback system:
- `cl.LangchainCallbackHandler()` — Chainlit UI: LLM tokens, tool calls, step rendering
- `langfuse.langchain.CallbackHandler()` — LangFuse: traces, spans, observability

`cl.Step` is a single parent step wrapping the entire graph execution. `cl.LangchainCallbackHandler()`
auto-creates nested sub-steps for LLM calls and tool calls within the graph — no manual step nesting needed.

Stage transitions driven by `get_stream_writer()` custom events emitted from agent nodes:
```python
writer = get_stream_writer()
writer({"type": "stage", "name": "Searching curriculum..."})
```

Chainlit handler catches these events and updates the parent step's display name.
The 4 pipeline stages:
1. "Getting to know you..." (intake)
2. "Searching curriculum..." (retrieval)
3. "Matching electives..." (matching)
4. "Your recommendations" (final)

Recommendations are delivered via the `emit_recommendations` tool (in `src/agents/tools.py`).
The matcher subagent calls it after writing `/recommendations.json`. It emits two custom events:
- Stage: `{"type": "stage", "name": "Your recommendations"}`
- Data: `{"type": "recommendations", "data": <ElectiveRecommendation>, "retrieved_chunks": "..."}`

Stage events are emitted by `emit_stage` — main agent calls it before each subagent delegation.
Both tools use `get_stream_writer()` from `langgraph.config`.

### HITL: Contradiction Interrupt (Conversational)

Main agent gets two tools: `contradiction_check` (HITL trigger) and `emit_stage` (pipeline stage
signals). When the intake agent detects a contradiction
(e.g., "nurse" + "hates science"), it calls this tool. `interrupt_on={"contradiction_check": True}`
pauses the graph via `HumanInTheLoopMiddleware`.

The agent surfaces the conflict as a natural-language message **before** calling the tool:
> "Nursing typically requires strong science skills. Are you open to building those,
> or would you like me to suggest related careers that lean more on your strengths?"

The student replies conversationally. The LLM interprets accept/pivot/insist. No buttons.

**Detection:** After the `astream` loop ends, check `agent.get_state(config).next` —
non-empty means the graph is interrupted, waiting for resume. Set `cl.user_session.set("interrupted", True)`.
Note: `GraphInterrupt` is suppressed by the root graph — never raised to the caller.

**Resumption:** On the next `@cl.on_message`, if `interrupted`, pass `Command(resume=..., update=...)`:
```python
Command(
    resume={"decisions": [{"type": "approve"}]},
    update={"messages": [HumanMessage(content=msg.content)]},
)
```
The `update` injects the user's natural-language reply into agent state alongside tool approval
(`resume`). Agent sees its contradiction question → user's response → tool confirmation, then
interprets accept/pivot/insist from the actual words. Same `thread_id` preserves all state via
`AsyncRedisSaver`.

**`contradiction_check` tool (in `src/agents/tools.py`):**
```python
from langchain_core.tools import tool

@tool
def contradiction_check(reason: str, suggestion: str) -> str:
    """Flag a contradiction in the student's profile for human review.

    Call this when the student's stated career conflicts with their
    academic strengths, weaknesses, or work values.

    Args:
        reason: What the contradiction is (e.g., "Nursing requires strong
                science skills but student dislikes science")
        suggestion: What the student might consider instead
    """
    return "Contradiction flagged."
```

---

## Directory Layout

```
tugma-ai/
├── pyproject.toml
├── Dockerfile                       # Single-stage, supervisord entrypoint
├── supervisord.conf                 # redis + uvicorn + chainlit
├── fly.toml                         # Fly.io deployment config
├── .env.example
├── README.md
├── docs/adr/
│   └── 001-project-foundation.md
│
├── src/
│   ├── main.py                     # FastAPI: GET /health only
│   ├── config.py                   # Pydantic BaseSettings, nested models (.env)
│   ├── agents/
│   │   ├── main_agent.py           # create_deep_agent() → orchestrator
│   │   ├── prompts/                # Separate .md prompt files
│   │   │   ├── intake.md
│   │   │   ├── retriever.md
│   │   │   └── matcher.md
│   │   ├── subagents/
│   │   │   ├── retrieval.py        # Subagent dict: Qdrant + rerank
│   │   │   └── matching.py         # Subagent dict: career → electives
│   │   └── tools.py                # Domain tools: qdrant_hybrid_search_tool,
│   │                               #   contradiction_check
│   ├── core/
│   │   ├── llm.py                  # ChatModel factory (ChatOpenAI object)
│   │   ├── embeddings.py           # Jina v5 embeddings via HTTP
│   │   ├── reranker.py             # Jina v3 reranker via HTTP
│   │   ├── qdrant.py               # Qdrant async client + hybrid_search()
│   │   ├── redis.py                # AsyncRedisSaver + RedisStore helpers
│   │   └── guardrails.py           # Guardrails AI: ToxicLanguage + DetectPII
│   ├── models/
│   │   ├── profile.py              # StudentProfile (15 fields)
│   │   └── recommendations.py      # ElectiveRecommendation, Subject
│   └── observability/
│       └── langfuse.py             # CallbackHandler + scoring setup
│
├── ingestion/
│   ├── ingest.py                   # CLI: PDFs → chunk → embed → upsert Qdrant
│   └── chunker.py                  # LlamaIndex IngestionPipeline config
│
├── documents/                      # DepEd PDFs (gitignored, user-provided)
│   └── .gitkeep
│
├── frontend/
│   ├── app.py                      # Chainlit: graph init, lifecycle, guardrails, streaming
│   ├── chainlit.md                 # Welcome page (Taglish greeting)
│   └── public/
│       └── elements/
│           └── ElectiveCard.jsx    # Custom JSX card component for recommendations
│
└── tests/
    ├── conftest.py
    ├── test_agent.py
    ├── test_guardrails.py
    ├── test_models.py
    ├── test_scoring.py
    └── test_tools.py
```

Changes from original:
- `src/api/` collapsed to `src/main.py` (single health endpoint)
- `src/agents/middleware.py` removed (DeepAgents auto-assembles middleware)
- `src/agents/prompts/` added — separate `.md` files for all system prompts
- `src/core/guardrails.py` added (moved from `api/middleware/`)
- `src/models/chat.py` removed (SSE events not needed; Chainlit owns UI)
- `tests/test_api/` → removed (graph tested via agent directly)
- `Dockerfile`, `supervisord.conf`, `fly.toml` added to root
- `frontend/public/elements/ElectiveCard.jsx` added for recommendation cards

---

## Agent Pipeline

### Main Agent (Intake/Orchestrator)

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from src.core.llm import get_chat_model  # Returns ChatOpenAI object
from src.agents.tools import contradiction_check, emit_stage

agent = create_deep_agent(
    model=get_chat_model(),         # ChatModel object — supports any OpenAI-compatible endpoint
    system_prompt=INTAKE_SYSTEM_PROMPT,
    subagents=[
        retrieval_subagent,
        matching_subagent,
    ],
    tools=[contradiction_check, emit_stage],  # HITL trigger + pipeline stage signals
    backend=StateBackend(),
    checkpointer=_saver,
    store=_store,
    interrupt_on={"contradiction_check": True},
)
```

Key decisions:
- `TodoListMiddleware` and `FilesystemMiddleware` are auto-assembled — not passed manually
- `interrupt_on` is a top-level parameter (auto-adds `HumanInTheLoopMiddleware`)
- `context_schema` dropped — domain data flows through FilesystemMiddleware files
- Main agent has two tools: `contradiction_check` (HITL trigger) and `emit_stage` (pipeline UI signals).
  All domain work delegated to 2 subagents via `task()`.
- Model is a `ChatModel` object, not a string — enables any OpenAI-compatible endpoint
- `AsyncRedisSaver` + `RedisStore` connected to local Redis in container (`redis://localhost:6379/0`)

### Pipeline Flow

```
User Message (Tagalog/Taglish/English)
        │
        ▼
┌──────────────────────┐
│ MAIN AGENT (Intake)  │  Conversational profiling (max 6 exchanges).
│                      │  Writes /profile.json (always in English).
│                      │  Calls contradiction_check → HITL interrupt.
│                      │  Calls emit_stage before each subagent delegation.
│                      │  Agent decides when profiling is complete.
└────────┬─────────────┘
         │ profile complete → emit_stage("Searching curriculum...") → task()
         ▼
┌──────────────────────┐
│ Retrieval Subagent   │  Reads /profile.json → Qdrant hybrid
│                      │  (dense + BM25 sparse). Jina rerank.
│                      │  Writes /retrieved_chunks.md.
└────────┬─────────────┘
         │ emit_stage("Matching electives...") → task()
         ▼
┌──────────────────────┐
│ Matching Subagent    │  Reads /profile.json + /retrieved_chunks.md.
│                      │  JSON schema in system prompt. 8-rule reasoning.
│                      │  Writes /recommendations.json.
│                      │  Calls emit_recommendations() → UI + LangFuse scoring.
└────────┬─────────────┘
         │
         ▼
   Chainlit catches custom event → renders ElectiveCard components
```

### Subagent: Retrieval

```python
retrieval_subagent = {
    "name": "retriever",
    "description": "Search DepEd curriculum documents for relevant elective subjects.",
    "system_prompt": RETRIEVER_PROMPT,   # Loaded from src/agents/prompts/retriever.md
    "tools": [qdrant_hybrid_search_tool],
    "model": get_chat_model(),
}
```

### Subagent: Matching

```python
matching_subagent = {
    "name": "matcher",
    "description": "Map student profile to elective recommendations with personalized reasoning.",
    "system_prompt": MATCHER_PROMPT,     # Loaded from src/agents/prompts/matcher.md
                                         # Includes full JSON schema for ElectiveRecommendation
    "tools": [emit_recommendations],
    "model": get_chat_model(),
}
```

Note: `response_format` is NOT available per-subagent (DeepAgents SubAgent TypedDict doesn't include it).
Instead, the matching subagent's system prompt includes the full Pydantic JSON schema for
`ElectiveRecommendation`. The subagent writes to `/recommendations.json` via FilesystemMiddleware.
Chainlit reads it and validates with Pydantic. If validation fails, retry once.
The matching subagent also calls `emit_recommendations()` which emits
via `get_stream_writer()` for direct Chainlit rendering.

Matching rules (8, in system prompt):
1. Only recommend subjects found in the retrieved document chunks.
2. Map career to DepEd's prototype programs of study where possible.
3. Apply the doorway option: suggest 1-2 cross-track electives based on hobbies/skills.
4. If no direct match, generalize within the same cluster.
5. Flag contradictions (e.g., career requires science but student dislikes it).
6. Provide personalized reasoning for each recommendation.
7. For `needs_immediate_employment`, prioritize TechPro + NC II certified electives.
8. Write final recommendations to `/recommendations.json` in the exact JSON schema below.

---

## State Management

### FilesystemMiddleware Inter-Agent State

DeepAgents manages `DeepAgentState` internally. No `context_schema` extension needed.
All domain data flows through FilesystemMiddleware's virtual files (prompt-driven):

| File | Written by | Read by |
|---|---|---|
| `/profile.json` | Main agent | Retriever, Matcher |
| `/retrieved_chunks.md` | Retriever | Matcher |
| `/recommendations.json` | Matcher | Chainlit (via custom event + Pydantic validation) |

### Session Persistence

```python
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.store.redis import RedisStore

# Checkpointer: auto-persists graph state per thread_id
_saver = AsyncRedisSaver.from_conn_string("redis://localhost:6379/0")
await _saver.asetup()

# Store: persistent memory (future use)
_store = RedisStore.from_conn_string("redis://localhost:6379/0")
await _store.asetup()
```

- Redis runs locally in Docker container (`redis://localhost:6379/0`). No external Redis Cloud dependency.
- Session TTL: `{"default_ttl": 30, "refresh_on_read": True}` — active sessions auto-refresh.
- `supervisord.conf` starts redis (priority 1), then uvicorn (2), then chainlit (3).
- No Fly volume — Redis data is per-deploy ephemeral (portfolio demo scope).

---

## Data Models

### StudentProfile (11 dimensions)

```python
class StudentProfile(BaseModel):
    primary_career: str                    # "Doctor", "Software Engineer"
    career_confidence: float               # 0.0–1.0
    secondary_careers: list[str]           # Fallback interests
    academic_strengths: list[str]          # ["Math", "Science"]
    academic_weaknesses: list[str]         # ["Public Speaking"]
    preferred_track: Optional[str]         # "Academic", "TechPro", None
    intended_college_course: Optional[str] # If planning tertiary
    hobbies: list[str]                     # ["Drawing", "Cooking"]
    extracurriculars: list[str]            # ["Student Council", "Debate Club"]
    existing_skills: list[str]             # ["Basic Python", "Photo Editing"]
    work_values: list[str]                 # ["Helping others", "Creative freedom"]
    work_environment: Optional[str]        # "indoor", "outdoor", "mixed"
    collaboration_style: Optional[str]     # "team", "solo", "mixed"
    needs_immediate_employment: bool       # Bias toward TechPro + NC II
    financial_constraints: Optional[str]   # "limited college budget"
```

### ElectiveRecommendation

```python
class Subject(BaseModel):
    name: str                              # "Biology 1"
    cluster: str                           # "Science, Technology, Engineering, Mathematics"
    track: Literal["Academic", "TechPro"]
    hours: int                             # 80 or 320
    semester: str                          # "1st" or "2nd"
    description_snippet: str               # From DepEd document
    relevance_reason: str                  # Personalized explanation

class ElectiveRecommendation(BaseModel):
    profile: StudentProfile
    recommendations: list[Subject]         # Ranked primary recommendations
    doorway_electives: list[Subject]        # Cross-track suggestions
    contradictions: list[str]              # Flagged mismatches
    overall_confidence: float              # 0.0–1.0
    career_pathway: str                    # e.g., "Pre-Med / Allied Health Sciences"
```

---

## Infrastructure & Technology

### LLM / Embeddings / Reranker

| Component | Provider | Model | Note |
|-----------|----------|-------|------|
| All agents (main + subagents) | OpenAI-compatible | `LLM_MODEL` from `.env` | Passed as `ChatModel` object from `core/llm.py` |
| Embeddings | Jina AI | `jina-embeddings-v5-text-small` | 1024-dim, multilingual, 32K context. HTTP API, no SDK. |
| Reranker | Jina AI | `jina-reranker-v3` | 0.6B params, multilingual. HTTP API, no SDK. |

Both Jina services called via direct HTTP (`httpx`) in `core/embeddings.py` and `core/reranker.py`.
`Authorization: Bearer $JINA_API_KEY` header. Free tier: 10M tokens.

### Environment Configuration

Flat Pydantic `BaseSettings` (no nesting):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    jina_api_key: str = ""
    qdrant_url: str
    qdrant_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    guardrails_token: str = ""
    environment: str = "development"
    max_intake_exchanges: int = 6
    session_ttl_minutes: int = 30
```

### Qdrant

- **Deployment:** Qdrant Cloud free tier (1GB).
- **Collection:** `sshs_documents`. Created by ingest CLI (idempotent `create_collection`).
  Vector: 1024-dim (Jina v5). Sparse: BM25 for hybrid search.
  Payload: `text`, `source_document`, `page`, `subject_area`, `track`, `cluster`.
- **Search:** Server-side hybrid via `prefetch` + `FusionQuery(fusion=models.Fusion.RRF)`.
  Dense (Jina v5) + sparse (BM25) → RRF fusion → Jina reranker post-processing.
- **Access:** Exposed as `qdrant_hybrid_search_tool` (in `src/agents/tools.py`, wraps `core/qdrant.py`).
  Assigned to retrieval subagent via `tools=[qdrant_hybrid_search_tool]`.

### Redis

1. **Session state:** `AsyncRedisSaver` — DeepAgents/LangGraph checkpointing per `thread_id`.
2. **Persistent memory:** `RedisStore` — wire-up for future cross-session memory.

Redis runs locally in Docker container (`redis://localhost:6379/0`). Data persisted via
Fly.io volume at `/data/redis` with `redis-server --save 60 1`. No external Redis Cloud dependency.
30-minute session TTL (`{"default_ttl": 30, "refresh_on_read": True}`).

### Guardrails AI

**Scope:** Input-only. Validates user messages before they reach any agent.
Called from `frontend/app.py` `@cl.on_message` via `core/guardrails.py`.

```python
from guardrails import Guard
from guardrails.hub import ToxicLanguage, DetectPII

guard = Guard().use(
    ToxicLanguage(threshold=0.7, on_fail="exception"),
    DetectPII(pii_entities="pii", on_fail="exception"),
    on="messages",
)
```

- On violation: polite refusal message in Tagalog. Log to LangFuse.
- No output guardrails: retrieval pipeline + subagent prompts + Pydantic validation constrain output.

### LangFuse

**Tracing:** `CallbackHandler()` passed alongside `cl.LangchainCallbackHandler()` in
`config={"callbacks": [cb_handler, langfuse_handler]}`. Both are additive LangChain callbacks — no conflict.
Full tracing of all LLM calls, tool calls, and subagent delegations. Opt-in: if `LANGFUSE__PUBLIC_KEY` is
unset, no tracing occurs.

- No OpenTelemetry auto-instrumentation (avoids OTel overhead and potential conflicts).
- Top-level trace per session (`thread_id`).

**Scoring (in Chainlit handler):**
- **Profiling completeness** (programmatic): ratio of filled profile dimensions to total fields (0.0–1.0).
  Scored from `StudentProfile` Pydantic model when recommendations event arrives.
- **Recommendation relevance** (LLM-as-judge): async `judge_relevance(recommendations_json, retrieved_chunks)`
  calls LLM to score alignment between recommendations and retrieved DepEd curriculum chunks (0.0–1.0).
  Clamped to [0.0, 1.0]. Returns None on any failure — score silently skipped.
- Scores via `span.score(name="...", value=..., data_type="NUMERIC")`.

**Cost tracking:** Per-session LLM token usage (auto-tracked by LangFuse).

### LlamaIndex (Ingestion, offline CLI)

```python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),
        jina_embed_model,
    ],
    vector_store=qdrant_store,
    docstore_strategy=DocstoreStrategy.UPSERTS,  # Idempotent
)
```

- Idempotent via `UPSERTS` strategy — safe to re-run on document updates.
- Source: downloaded DepEd PDFs in `documents/` (gitignored, user-provided).
- Uses `llama-index-readers-file` (PDF reader) + `llama-index-vector-stores-qdrant`.
- Collection `sshs_documents` created by ingest CLI if it doesn't exist.
- Invoke: `uv run python -m ingestion.ingest`.

### Chainlit Frontend

- **Runs the graph directly** — not a separate client to FastAPI.
- `cl.LangchainCallbackHandler()` captures LLM tokens and tool calls automatically.
- Stream mode: `["custom"]` only. Callback handler handles token streaming. Custom events for `cl.Step` stages + recommendations.
- Single parent `cl.Step` wrapping graph execution. `cl.LangchainCallbackHandler()` auto-creates nested sub-steps.
- Session ID (`cl.context.session.id`) = `thread_id` for Redis checkpointing.
- HITL contradictions resolved conversationally (natural language, not buttons).
- Recommendations rendered as `cl.CustomElement(name="ElectiveCard")` components via `get_stream_writer()` custom events.
  JSX file at `frontend/public/elements/ElectiveCard.jsx` using shadcn `<Card>`.
- Welcome page (`frontend/chainlit.md`): Taglish greeting inviting students to share career goals.
- No `frontend/.chainlit/config.toml` — defaults sufficient.

---

## Domain Knowledge: SSHS Curriculum

### Sources
- SSHS Shaping Paper (38 pages, Annex A: subject list, Annex B: career/elective mappings)
- DepEd Order No. 017, s. 2026
- DepEd Memorandum No. 048, s. 2025 (Pilot Implementation, prototype programs of study)
- NCR Regional Memorandum No. 511, s. 2025 (complete elective tables)

### Track Structure
- **Academic Track:** 5 elective clusters. 4 electives/year (80h each, per semester).
- **TechPro Track:** 10 elective clusters. 1 elective/year (320h, year-long).

### Academic Elective Clusters
1. Arts, Social Sciences, and Humanities
2. Business and Entrepreneurship
3. Science, Technology, Engineering, and Mathematics
4. Sports, Health, and Wellness
5. General Academic (cross-cluster)

### TechPro Elective Clusters
1. Aesthetic, Wellness, and Human Care
2. Agri-Fishery Business and Food Innovation
3. Artisanry and Creative Enterprise
4. Automotive and Small Engine Technologies
5. Construction and Building Technologies
6. Creative Arts and Design Technologies
7. Hospitality and Tourism
8. ICT Support and Computer Programming Technologies
9. Industrial Technologies
10. Maritime Transport

### Key Features
- **Doorway option:** 1-2 electives from the other track.
- **No strands:** Clusters replace rigid strands.
- **Prototype Programs of Study:** DepEd provides career pathway templates
  (e.g., Pre-Law → Social Sciences + Philippine Governance + Creative Composition).
- **Work Immersion:** 320-640 hours.
- **5 Core Subjects:** Effective Communication, General Mathematics, General Science,
  Life and Career Skills, Pag-aaral ng Kasaysayan at Lipunang Pilipino.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No Qdrant results for career | Subagent generalizes within same cluster. Lower confidence. |
| Student contradicts self (nurse + hates science) | HITL interrupt → conversational resolution → 3 paths. |
| Translation quality poor | Log to LangFuse. Retry once. If still poor, ask rephrase. |
| LLM returns malformed output | Pydantic validates `/recommendations.json` on read. On failure, retry once. |
| Guardrails trigger | Polite refusal message. Log violation to LangFuse. |
| Redis unavailable | Graceful message. Fall back to in-memory state. Log warning. |
| Qdrant unavailable | 503-style message. Try cached recommendations if available. |

---

## 3-Day Build Plan

### Day 1: Infrastructure & Ingestion
- Download DepEd PDFs to `documents/`.
- `pyproject.toml` with all dependencies (uv add workflow, uv.lock).
- `Dockerfile`, `supervisord.conf`, `fly.toml` — deployment infrastructure.
- `src/config.py` with nested Pydantic BaseSettings.
- `src/core/` — all 6 files: `llm.py`, `embeddings.py`, `qdrant.py`, `redis.py`, `reranker.py`, `guardrails.py`.
- `ingestion/ingest.py` + `chunker.py`: LlamaIndex IngestionPipeline → Jina v5 embed → Qdrant.
- `src/main.py` — FastAPI `GET /health`.
- **Deadline:** `hybrid_search("nursing career electives")` returns relevant DepEd chunks.

### Day 2: Agent Pipeline & Chainlit UI
- `src/models/` — `profile.py`, `recommendations.py`.
- `src/agents/prompts/` — 3 `.md` system prompt files (intake, retriever, matcher).
- `src/agents/tools.py` — `qdrant_hybrid_search_tool` + `contradiction_check`.
- `src/agents/subagents/` — 3 subagent dicts (ChatModel objects, no response_format).
- `src/agents/main_agent.py` — `create_deep_agent()` with `StateBackend`, `tools=[contradiction_check]`, `interrupt_on`.
- `frontend/public/elements/ElectiveCard.jsx` — JSX card component.
- `frontend/app.py` — Chainlit entry: lazy singleton Redis init, guardrails, dual callbacks, `cl.Step`, CustomElement rendering.
- `frontend/chainlit.md` — Welcome page with Taglish greeting.
- **Deadline:** End-to-end: "Gusto ko maging nurse" → ElectiveCards rendered.

### Day 3: Depth & Polish
- HITL contradiction interrupt — conversational resolution with `contradiction_check` tool + `agent.get_state(config).next` detection + `Command(resume=...)`.
- `cl.Step` progress — `get_stream_writer()` custom events for 5 stages.
- LangFuse `CallbackHandler()` in config → auto-traces all agent turns + tool calls.
- LangFuse scoring: profiling completeness (programmatic) + recommendation relevance (LLM-as-judge).
- Chainlit `CustomElement` rendering for `ElectiveRecommendation`.
- Tests: `test_agents/`, `test_core/`, `test_ingestion/`, `conftest.py` (~15-20 tests).
- **Deadline:** System is demo-ready with observability, guardrails, interrupts, and card UI.

---

## Non-Decisions (Deferred)

1. **User authentication:** Not in scope (personal-use / demo tool).
2. **Multi-turn conversation memory beyond current session:** Not in scope. Redis TTL handles expiry.
3. **School-specific elective availability:** Requires per-school data. Future: EBEIS integration.
4. **NCAE results integration:** Future: add as optional profiling input.
5. **Grade 12 recommendations:** Current scope is Grade 11 only.
6. **Feedback loop from student outcomes:** Future: closed-loop evaluation.
7. **Rate limiting:** Deferred. Irrelevant for single-user demo. Designed, not implemented.
8. **Redis VL / LangCache (semantic caching):** Deferred. Zero hit-rate expectation in demo.
9. **Redis Streams (audit log / async jobs):** Deferred. LangFuse already traces. Async ingestion is offline CLI.
10. **Incremental ingest / document update watcher:** Deferred. Manual re-run of ingest CLI sufficient.

---

## Tradeoffs Accepted

| Tradeoff | Rationale |
|----------|-----------|
| Chainlit runs graph (not FastAPI SSE) | `cl.LangchainCallbackHandler()` only works in-process. Auto-tokens > manual SSE. |
| DeepAgents subagent delegation vs. manual graph | Idiomatic framework usage. Deeper portfolio signal. |
| FilesystemMiddleware for inter-agent state (not context_schema) | Aligns with DeepAgents' intended pattern. No state management gymnastics. |
| No output guardrails | Retrieval pipeline + subagent prompts + Pydantic validation constrain output. |
| No rate limiting | Demo tool with 1-2 users. Production infra deferred. |
| No semantic caching | Zero hit-rate expectation. Key-value cache would erase personalization. |
| Jina free tier vs. OpenAI embeddings | Free covers corpus. No cost risk for portfolio. |
| Local Redis in container (not Redis Cloud) | Simpler deployment. No external Redis dependency. Volume-persisted data. |
| Chainlit over Gradio/Streamlit | Best-in-class LangGraph integration, native agent UX. |
| CallbackHandler over OpenTelemetry for LangFuse | Simpler, additive, no OTel conflict with Chainlit callback. |
| HITL as conversational (not buttons) | Preserves chat metaphor. Simpler to build. |
| Prompts in separate .md files (not inline) | Cleaner diffs, faster prompt iteration. Standard LLM engineering practice. |
| JSON schema in system prompt (not response_format) | `response_format` not available per-subagent in DeepAgents. System prompt + Pydantic achieves same result. |
| `stream_mode=["custom"]` only (not dual mode) | `cl.LangchainCallbackHandler()` handles token streaming. Single mode simplifies loop. |

---

## References

- DeepAgents: https://github.com/langchain-ai/deepagents
- DeepAgents Docs: https://docs.langchain.com/oss/python/deepagents
- DepEd Strengthened SHS Program: https://www.deped.gov.ph/strengthened-shs-program/
- DepEd Order No. 017, s. 2026
- DepEd Memorandum No. 048, s. 2025 (Pilot Implementation)
- NCR Regional Memorandum No. 511, s. 2025
- LangGraph Redis Checkpointer: https://github.com/redis-developer/langgraph-redis
- LangGraph Streaming v2: https://docs.langchain.com/oss/python/langgraph/streaming
- Guardrails AI: https://github.com/guardrails-ai/guardrails
- LangFuse Python SDK: https://github.com/langfuse/langfuse-python
- LlamaIndex IngestionPipeline: https://docs.llamaindex.ai
- Jina Embeddings: https://jina.ai/embeddings/
- Jina Reranker: https://jina.ai/reranker/
- Chainlit: https://docs.chainlit.io
- Fly.io: https://fly.io/docs
- Jina Embeddings v5: https://jina.ai/embeddings/
- Jina Reranker v3: https://jina.ai/reranker/
