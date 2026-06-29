# ADR 001: Project Foundation — Framework & Architecture

**Date:** 2026-06-19
**Status:** Accepted. See ADR 002 (State & Communication) and ADR 003 (Retrieval & AI
Infrastructure) for extracted decisions that supersede portions of the original
monolithic document.

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
app.py (Chainlit, runs graph) ──→ agents/ (DeepAgents domain)
                                     ↓
                                core/ (Ports: LLM, Qdrant, Redis, Jina, Guardrails)
                                     ↓
                                models/ (Shared Kernel: Pydantic)
```

- **Domain logic** (`agents/`) depends on abstract ports (`core/`), never on frameworks.
- **Adapters** (`app.py`) drive the domain. Swappable without touching agents.
- **Ingestion** (`ingestion/`) is an offline tool outside the runtime.
- **Shared Kernel** (`models/`) ensures all layers speak the same data contracts.
- **Hexagonal depth:** Concrete with protocol. `core/` wraps external libraries directly —
  agents call `core/qdrant.hybrid_search()`, never `qdrant_client` directly.
  Swap = edit one `core/` file.
- No FastAPI sidecar — Chainlit runs the graph directly.

### Deployment: Docker (generic container)

- **Container:** Single `Dockerfile` based on `python:3.13-slim-bookworm`.
  Chainlit managed by `supervisord` on port 8000.
- **Secrets:** Inject via container env (`--env-file .env` or host orchestrator secrets).
- **Redis persistence:** Bundled in-container Redis is ephemeral (`--save "" --appendonly no` per `supervisord.conf`).
  Session data does not survive container restart. Acceptable for portfolio demo scope.

### Agent Framework: DeepAgents (with LangGraph substrate)

**Decision:** Use `create_deep_agent()` from DeepAgents, not raw LangGraph `StateGraph`.

DeepAgents provides:
- Built-in subagent delegation (`task()` tool)
- Auto-assembled middleware stack (TodoList, Filesystem)
- Backend abstraction (`StateBackend` — ephemeral, per-thread)
- Pluggable checkpointing and store (`AsyncRedisSaver`, `RedisStore`)
- Returns `CompiledStateGraph` — LangGraph v2 streaming works underneath

### Agent Architecture: Main Orchestrator + 2 Subagents

```
Main Agent (Intake/Orchestrator)
│  tools=[emit_stage]              Pipeline stage signals
│
├── Subagent: Retrieval          Qdrant hybrid search + Jina rerank
└── Subagent: Matching           career → elective reasoning + structured output

Middleware (auto-assembled):
  TodoListMiddleware              Auto-included. Planning + step tracking.
  FilesystemMiddleware            Auto-included. Virtual files for inter-agent state.

Backend:
  StateBackend()                  Ephemeral session data (per-thread)

Store:        RedisStore (langgraph-redis)    Persistent memory (future use)
Checkpointer: AsyncRedisSaver                 Per-session graph state (auto-checkpoint)
```

### DeepAgents Native Patterns

**Subagent delegation:** The main agent handles the intake conversation. When ready to progress, it
delegates to subagents via the built-in `task()` tool — no manual graph edge wiring.

**Subagent format:** TypedDicts with `name`, `description`, `system_prompt` (all required) plus
optional `tools`, `model`, `middleware`, `skills`, `permissions`.
`response_format` is a top-level `create_deep_agent()` parameter only — NOT available per-subagent.
Structured output for the matching subagent achieved via JSON schema in the system prompt + Pydantic validation on read.

**Inter-agent communication:** Via FilesystemMiddleware's virtual filesystem. See ADR 002.

**Streaming:** `create_deep_agent()` returns `CompiledStateGraph`. Chainlit streams via
`agent.astream(input, stream_mode=["messages", "custom"], config=...)`.
Dual mode: `"messages"` for LLM token streaming, `"custom"` for stage events.

**Model passing:** `ChatModel` objects (from `core/llm.py`) passed to `create_deep_agent(model=...)`
and subagent dicts — not provider strings. Supports any OpenAI-compatible endpoint configured via `.env`.

**Session persistence:** `AsyncRedisSaver` as `checkpointer` + `AsyncRedisStore` as `store`.
See ADR 002 for details.

### Chainlit Runs the Graph

Chainlit owns graph execution. In Docker, bind to all interfaces: `chainlit run app.py --host 0.0.0.0 --port 8000`.

```python
# app.py — current pattern (simplified, Day 4)

@cl.on_chat_start
async def on_chat_start():
    await _setup_state()
    agent = build_agent(checkpointer=_saver, store=_store)
    cl.user_session.set("agent", agent)
    ...

@cl.on_message
async def on_message(msg: cl.Message):
    passed, reason = check_input(msg.content)
    if not passed:
        ...  # guardrail rejection

    agent = cl.user_session.get("agent")
    langfuse_handler = get_langfuse_handler()
    cb = cl.LangchainCallbackHandler()
    config = {"callbacks": [cb, ...], "configurable": {"thread_id": cl.context.session.id}}

    async with cl.Step(name="Getting to know you...", type="run") as step:
        final_msg = cl.Message(content="")
        async for mode, *data in agent.astream(
            input_msg, stream_mode=["messages", "custom"], config=config
        ):
            if mode == "messages":
                await final_msg.stream_token(msg_chunk.content)
            elif mode == "custom":
                if chunk.get("type") == "stage":
                    if final_msg.content:
                        await final_msg.send()
                        final_msg = cl.Message(content="")
                    step.name = chunk["name"]
                    await step.update()

    if final_msg.content:
        await final_msg.send()
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
The 3 pipeline stages:
1. "Getting to know you..." (intake)
2. "Searching curriculum..." (retrieval)
3. "Matching electives..." (matching)

Recommendations are delivered as the matcher's natural language LLM response
(markdown format — tables, lists). No custom events needed; no CustomElement cards.
The matcher writes `/recommendations.json` via FilesystemMiddleware and outputs
its markdown summary directly as the chat response.

### HITL: Contradiction Detection (Conversational)

Main agent has one tool: `emit_stage` (pipeline stage signals). When the intake agent detects a
contradiction (e.g., "nurse" + "hates science"), it gently points out the conflict in conversation
and asks for clarification — no tool call, no interrupt, no buttons. The LLM interprets
accept/pivot/insist from the student's natural-language reply.

---

## Directory Layout

```
tugma-ai/
├── pyproject.toml
├── Dockerfile
├── supervisord.conf
├── .env.example
├── README.md
├── app.py                           # Chainlit entrypoint (runs graph)
├── docs/adr/
│   ├── 001-project-foundation.md    # Framework & architecture
│   ├── 002-state-and-communication.md
│   └── 003-retrieval-and-infrastructure.md
│
├── src/
│   ├── config.py
│   ├── agents/
│   │   ├── main_agent.py
│   │   ├── prompts/
│   │   │   ├── intake.md
│   │   │   ├── retriever.md
│   │   │   └── matcher.md
│   │   ├── subagents/
│   │   │   ├── retrieval.py
│   │   │   └── matching.py
│   │   └── tools.py
│   ├── core/
│   │   ├── llm.py
│   │   ├── embeddings.py
│   │   ├── reranker.py
│   │   ├── qdrant.py
│   │   ├── redis.py
│   │   └── guardrails.py
│   ├── models/
│   │   ├── profile.py
│   │   └── recommendations.py
│   └── observability/
│       └── langfuse.py
│
├── ingestion/
│   └── ingest.py
│
├── documents/                       # DepEd PDFs (gitignored)
│   └── .gitkeep
│
└── tests/
    ├── conftest.py
    ├── test_agent.py
    ├── test_guardrails.py
    ├── test_models.py
    └── test_tools.py
```

---

## Agent Pipeline

### Main Agent (Intake/Orchestrator)

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from src.core.llm import get_chat_model
from src.agents.tools import emit_stage

agent = create_deep_agent(
    model=get_chat_model(),
    system_prompt=INTAKE_SYSTEM_PROMPT,
    subagents=[retrieval_subagent, matching_subagent],
    tools=[emit_stage],
    backend=StateBackend(),
    checkpointer=_saver,
    store=_store,
)
```

Key characteristics:
- `TodoListMiddleware` and `FilesystemMiddleware` are auto-assembled.
- Main agent has one tool: `emit_stage` (pipeline UI signals). Domain work delegated to subagents.
- Contradiction detection is conversational — no interrupt or tool call.
- Model is a `ChatModel` object supporting any OpenAI-compatible endpoint.

### Pipeline Flow

```
User Message (Tagalog/Taglish/English)
        │
        ▼
│ MAIN AGENT (Intake)       │  Conversational profiling (max 8 exchanges).
│                           │  Writes /profile.json.
│                           │  Agent decides when profiling is complete.
         │ profile complete → emit_stage("Searching curriculum...") → task()
         ▼
│ Retrieval Subagent        │  Reads /profile.json → Qdrant hybrid search.
│                           │  Jina rerank. Writes /retrieved_chunks.md.
         │ emit_stage("Matching electives...") → task()
         ▼
│ Matching Subagent         │  Reads /profile.json + /retrieved_chunks.md.
│                           │  8-rule reasoning. Writes /recommendations.json.
│                           │  Outputs markdown summary as LLM response.
```

### Subagent Definitions

**Retrieval:**
```python
retrieval_subagent = {
    "name": "retriever",
    "description": "Search DepEd curriculum documents for relevant elective subjects.",
    "system_prompt": RETRIEVER_PROMPT,
    "tools": [qdrant_hybrid_search_tool],
    "model": get_chat_model(),
}
```

**Matching:**
```python
matching_subagent = {
    "name": "matcher",
    "description": "Map student profile to elective recommendations with personalized reasoning.",
    "system_prompt": MATCHER_PROMPT,
    "tools": [],
    "model": get_chat_model(),
}
```

Note: `response_format` is NOT available per-subagent in DeepAgents. The matching
subagent's system prompt describes the output format concisely. Pydantic validates
on read.

---

## Non-Decisions (Deferred)

1. **User authentication** — Not in scope (personal-use / demo tool).
2. **Multi-turn conversation memory beyond current session** — Not in scope. Redis TTL handles expiry.
3. **School-specific elective availability** — Requires per-school data. Future: EBEIS integration.
4. **NCAE results integration** — Future: add as optional profiling input.
5. **Grade 12 recommendations** — Current scope is Grade 11 only.
6. **Feedback loop from student outcomes** — Future: closed-loop evaluation.
7. **Rate limiting** — Deferred. Irrelevant for single-user demo.
8. **Redis VL / LangCache (semantic caching)** — Deferred. Zero hit-rate expectation in demo.
9. **Redis Streams (audit log / async jobs)** — Deferred. LangFuse already traces.
10. **Incremental ingest / document update watcher** — Deferred. Manual re-run of ingest CLI sufficient.

---

## Tradeoffs Accepted

| Tradeoff | Rationale |
|---|---|
| Chainlit runs graph (not FastAPI SSE) | `cl.LangchainCallbackHandler()` only works in-process. Auto-tokens > manual SSE. |
| DeepAgents subagent delegation vs. manual graph | Idiomatic framework usage. Deeper portfolio signal. |
| FilesystemMiddleware for inter-agent state (not context_schema) | Aligns with DeepAgents' intended pattern. No state management gymnastics. See ADR 002. |
| No output guardrails | Retrieval pipeline + subagent prompts + Pydantic validation constrain output. See ADR 003. |
| No rate limiting | Demo tool with 1-2 users. Production infra deferred. |
| No semantic caching | Zero hit-rate expectation. Key-value cache would erase personalization. |
| Jina free tier vs. OpenAI embeddings | Free covers corpus. No cost risk for portfolio. See ADR 003. |
| Local Redis in container (not Redis Cloud) | Simpler deployment. No external Redis dependency. See ADR 002. |
| Chainlit over Gradio/Streamlit | Best-in-class LangGraph integration, native agent UX. |
| CallbackHandler over OpenTelemetry for LangFuse | Simpler, additive, no OTel conflict with Chainlit callback. |
| Prompts in separate .md files (not inline) | Cleaner diffs, faster prompt iteration. |
| JSON schema in system prompt (not response_format) | `response_format` not available per-subagent in DeepAgents. |
| `stream_mode=["messages", "custom"]` | Callback handler + custom events. Dual mode gives token streaming + stage updates. |

---

## References

- ADR 002: State & Inter-Agent Communication
- ADR 003: Retrieval & AI Infrastructure
- DeepAgents: https://github.com/langchain-ai/deepagents
- DeepAgents Docs: https://docs.langchain.com/oss/python/deepagents
- DepEd Strengthened SHS Program: https://www.deped.gov.ph/strengthened-shs-program/
- DepEd Order No. 017, s. 2026
- LangGraph Streaming v2: https://docs.langchain.com/oss/python/langgraph/streaming
- Guardrails AI: https://github.com/guardrails-ai/guardrails
- LangFuse Python SDK: https://github.com/langfuse/langfuse-python
- Chainlit: https://docs.chainlit.io
