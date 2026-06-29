# ADR 003: Retrieval & AI Infrastructure

**Date:** 2026-06-19
**Status:** Accepted

Extracted and condensed from ADR 001. Supersedes the Infrastructure & Technology
section and parts of the Agent Pipeline section dealing with retrieval and AI
provider choices.

---

## Context

Retrieval accuracy determines recommendation quality. The retrieval pipeline must
handle mixed-language queries (English, Tagalog, Taglish), match curriculum terms
exactly ("Prototype Program of Study"), and surface relevant DepEd document chunks
for the matcher. A separate set of decisions governs which AI providers to use.

---

## Decision 1: Hybrid search (dense + BM25 + RRF) via Qdrant

Qdrant hybrid search combines Jina v5 dense embeddings (1024-dim) with BM25 sparse
vectors. The server fuses results via `FusionQuery(fusion=models.Fusion.RRF)`.

**Alternatives considered:**
- **Dense-only** — loses exact keyword matches. Curriculum terms ("NC II", "Prototype
  Program of Study") are lexical and benefit from BM25.
- **Keyword-only** — loses semantic matches. "Gusto ko maging nurse" needs dense
  embeddings to map to "Nursing career pathway."

**Why hybrid:**
- Mixed-language student input needs both semantic (dense) and keyword (sparse).
- RRF fusion is server-side — no client-side merging logic.
- Qdrant free tier handles the small corpus easily.

---

## Decision 2: Jina reranker post-processing

After Qdrant returns candidates, `jina-reranker-v3` reranks the top results.
Documents are truncated to 200 characters before the rerank API call (full text
is preserved in Qdrant payload for the matcher).

**Alternatives considered:**
- **No reranker** — rely purely on Qdrant ranking. Missing reranker cross-attention
  means relevant chunks can sit at position 6+.
- **Cohere reranker** — not free, same multilingual quality as Jina.

**Why Jina reranker:**
- Cross-attention rerank improves precision over vector-similarity ranking.
- 200-char truncation is ~30× cheaper: ~500 tokens/conversation instead of ~16K.
- Free tier covers the entire demo workload.

---

## Decision 3: Input-only guardrails

User messages pass through `Guardrails AI` with `ToxicLanguage(threshold=0.7)` and
`DetectPII` before reaching the agent. On violation: polite refusal in Tagalog.

**Alternatives considered:**
- **Full input + output guardrails** — also validates agent responses before
  showing them to the user.

**Why input-only:**
- Output is already constrained by three mechanisms: retrieval scope (only DepEd
  documents), system prompts (role-bound behavior), and Pydantic validation (malformed
  JSON is caught on read).
- Output guardrails add latency and can reject useful recommendations as false
  positives. Input-only covers the real risk (toxic/PII user input).

---

## Decision 4: LlamaIndex IngestionPipeline

Offline ingestion uses LlamaIndex `IngestionPipeline` with `SentenceSplitter`
(chunk_size=512, chunk_overlap=50) and the Jina embed model, writing to Qdrant.

```python
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),
        jina_embed_model,
    ],
    vector_store=qdrant_store,
    docstore_strategy=DocstoreStrategy.UPSERTS,
)
```

**Alternatives considered:**
- **Manual chunking + direct Qdrant client** — possible but more code to maintain.
- **LangChain document loaders** — similar abstraction level but LlamaIndex's
  IngestionPipeline is purpose-built for this flow.

**Why LlamaIndex:**
- Handles PDF reading, chunking, embedding, and Qdrant upsert as a single pipeline.
- `UPSERTS` strategy is idempotent — safe to re-run on document updates.
- Standard tool for RAG ingestion; no reason to reimplement.

---

## Decision 5: Single shared LLM model across all agents

All three agents (intake, retrieval, matching) use the same `LLM_MODEL` from `.env`,
passed as a `ChatModel` object from `core/llm.py`.

**Alternatives considered:**
- **Per-subagent model selection** — e.g., cheap/fast model for retrieval, expensive
  model for matching.

**Why shared model:**
- One API key, one config, one latency profile.
- Subagent prompts differentiate behavior, not the underlying model.
- If a cheaper model for retrieval were needed, it would require per-subagent model
  support from DeepAgents — which isn't available yet.

---

## Decision 6: Jina for both embeddings and reranker

- **Embeddings:** `jina-embeddings-v5-text-small` (1024-dim, multilingual, 32K context)
- **Reranker:** `jina-reranker-v3` (0.6B params, multilingual)

Both called via direct HTTP (`httpx`), no SDK.

**Alternatives considered:**
- **OpenAI text-embedding-3-small** for embeddings + Cohere reranker — two providers,
  no free tier for embeddings.
- **All OpenAI** — no multilingual reranker available.

**Why Jina:**
- Free tier (10M tokens) covers the corpus and all demo conversations.
- Multilingual support matches the English/Tagalog/Taglish domain.
- Single provider for both services simplifies API key management.

---

## Tradeoffs

| Tradeoff | Rationale |
|---|---|
| Jina free tier vs. OpenAI embeddings | Free covers corpus. No cost risk for portfolio. |
| 200-char reranker truncation loses context | Full text preserved in Qdrant payload for matcher. Reranker only needs signal. |
| Single LLM model for all agents | Simpler config. Prompts differentiate behavior, not model. |
| Jina HTTP API (no SDK) | One `httpx` call. SDK adds dependency for a thin wrapper. |

---

## References

- ADR 001: Framework & Architecture (umbrella)
- ADR 002: State & Inter-Agent Communication
- Qdrant hybrid search docs
- Jina Embeddings v5
- Jina Reranker v3
- LlamaIndex IngestionPipeline
- Guardrails AI
