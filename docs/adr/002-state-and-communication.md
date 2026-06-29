# ADR 002: State & Inter-Agent Communication

**Date:** 2026-06-19
**Status:** Accepted

Extracted and condensed from ADR 001. Supersedes the State Management section and
parts of the Architecture section dealing with inter-agent data flow.

---

## Context

The agent pipeline has two forms of state:
1. **Inter-agent data** — profile, retrieved chunks, recommendations flowing between
   intake, retrieval, and matching agents.
2. **Session persistence** — graph checkpoints that survive across user turns within
   a single conversation.

Two decisions define how both work: the inter-agent file contract and the Redis-backed
checkpointing strategy.

---

## Decision 1: FilesystemMiddleware over custom context_schema

DeepAgents offers a `context_schema` parameter to extend `DeepAgentState`. Instead,
Tugma-AI uses the built-in FilesystemMiddleware to pass data through virtual files:

| File | Written by | Read by |
|---|---|---|
| `/profile.json` | Main agent | Retriever, Matcher |
| `/retrieved_chunks.md` | Retriever | Matcher |
| `/recommendations.json` | Matcher | Chainlit (via markdown output) |

**Alternative considered:** Extending `DeepAgentState` with a `context_schema` that
carried typed fields for profile, chunks, and recommendations. This would require
custom state serialization and middleware to inject into subagent context.

**Why FilesystemMiddleware:**
- Prompts reference file paths explicitly (`"Write your findings to
  /retrieved_chunks.md"`) — no indirection through schema fields.
- Each virtual file is a single, visible contract. A developer reads the prompt and
  knows exactly what the agent reads and writes.
- No state-management boilerplate. FilesystemMiddleware auto-injects `read_file` and
  `write_file` tools.

---

## Decision 2: Redis session persistence

Graph checkpoints use `AsyncRedisSaver`; persistent memory uses `RedisStore`:
- `thread_id` = `cl.context.session.id`
- 30-minute TTL (`{"default_ttl": 30, "refresh_on_read": True}`)

Redis runs locally in Docker (`redis://localhost:6379/0`). No external Redis Cloud.

**Alternatives considered:**
- `MemorySaver` only — loses state on server restart, no session continuity across
  Chainlit reconnects.
- SQLite — heavier setup, no TTL-based expiry, no built-in store semantics.

**Why Redis:**
- AsyncRedisSaver auto-checkpoints after every agent turn (DeepAgents native).
- RedisStore provides memory semantics for future cross-session features.
- Container-local Redis is simple enough for a portfolio demo; no cloud dependency.
- 30-min TTL with refresh-on-read means active sessions stay alive, idle ones clean
  up automatically.

---

## Decision 3: Fallback to MemorySaver + InMemoryStore

When Redis is unreachable (wrong URL, container not running), the system falls back:

```python
try:
    _saver = AsyncRedisSaver.from_conn_string(settings.redis_url)
    _store = RedisStore.from_conn_string(settings.redis_url)
except:
    _saver = MemorySaver()
    _store = InMemoryStore()
```

**Why:** Demo should never crash because Redis isn't running. Fallback is silent and
session data simply doesn't persist across restarts — acceptable for the demo scope.

---

## Tradeoffs

| Tradeoff | Rationale |
|---|---|
| Ephemeral Redis (no persistence across container restarts) | Acceptable for portfolio demo. Production would add AOF/RDB. |
| FilesystemMiddleware ties agents to string file paths | Less type-safe than context_schema, but prompts already reference files. |

---

## References

- ADR 001: Framework & Architecture (umbrella)
- DeepAgents middleware docs
- langgraph-redis: AsyncRedisSaver + RedisStore
