# Post-Compaction for Local LLMs in Production: Revised Recommendation

## TL;DR — Why the Pick Changed

The original recommendation was **LLMLingua-2** (Microsoft, 6.6K stars). That was
the right call for a visual demo where you want to highlight individual removed
tokens. It is the **wrong call for production** with a local LLM for the following
reasons:

1. LLMLingua-2 does **token-level extractive compression** — it yanks individual
   words out of sentences. The compressed text is often unreadable to humans and
   chat-mode LLMs are measurably more sensitive to this than completion-mode
   models (acknowledged in their own transparency FAQ).
2. It was trained on **meeting transcripts** (MeetingBank). Production local-LLM
   workloads see JSON, code, logs, tool output, structured data, and prose —
   LLMLingua-2 has one compressor for all of them.
3. At aggressive compression rates on long inputs, it causes **substantial
   information loss** (acknowledged in the paper itself — GPT-4's distillation
   labels get worse on long context).
4. It adds a **~560M parameter model** (XLM-RoBERTa-large) to every request path.
   On a production box already running Qwen2-7B, that is non-trivial VRAM/CPU
   contention.
5. It has known bugs with compression-rate accuracy on long texts and does not
   support JSON compression at all in v2 mode.
6. It has **no concept of reversibility** — once tokens are dropped, the
   information is gone.

**The revised recommendation for post-compaction is [Headroom](https://github.com/headroomlabs-ai/headroom)** (72K stars, Apache 2.0).

---

## What Headroom Actually Is

Headroom is a **content-aware compression layer** for LLM pipelines. It is not a
single compressor — it is a pipeline of specialised compressors, each designed
for a different content type, chained behind a content router.

| Attribute              | Detail                                                            |
|------------------------|-------------------------------------------------------------------|
| **Repo**               | [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) |
| **Stars**              | ~72,000                                                           |
| **License**            | Apache 2.0                                                        |
| **Origin**             | Built internally at Netflix for agent cost control                |
| **Deploy modes**       | Python library / TypeScript SDK / HTTP proxy / ASGI middleware / MCP server |
| **Compression**        | 47-95% on input (content-dependent), ~32% on output (estimated)   |
| **Reversible**         | Yes — CCR stores originals locally, LLM retrieves on demand       |
| **Local-first**        | Yes — no data leaves the machine                                  |
| **Ollama/vLLM native** | Yes — `create_ollama_provider()` / `create_vllm_provider()` built in |

### The Compression Pipeline

```
Incoming content (messages, tool output, RAG chunks, files, logs)
    |
    v
+--------------------------------------------------+
|  ContentRouter                                    |
|    Detects content type and routes to:            |
|    +-- SmartCrusher       (JSON arrays/objects)   |
|    +-- CodeCompressor     (AST-aware, 7 languages)|
|    +-- Kompress-v2-base   (prose, HF model)       |
|    +-- RTK integration    (CLI/shell output)      |
+--------------------------------------------------+
    |
    v
+--------------------------------------------------+
|  CacheAligner                                     |
|    Stabilises prefixes so KV cache hits           |
|  CCR (Content-addressable Cached Retrieval)       |
|    Stores originals locally, retrievable on       |
|    demand via headroom_retrieve tool               |
+--------------------------------------------------+
    |
    v
  Compressed payload --> local LLM (Ollama/vLLM)
```

Each compressor is purpose-built:

- **SmartCrusher**: Collapses JSON arrays of objects into schema + representative
  samples. A 100-element JSON array becomes schema + 3 examples. Lossless in
  structure, lossy only in redundant repetition.
- **CodeCompressor**: Parses ASTs for Python, JS/TS, Go, Rust, Java, C/C++.
  Strips comments, collapses whitespace, preserves semantics.
- **Kompress-v2-base**: A HuggingFace model trained on real agentic traces (not
  meeting transcripts). Handles prose and mixed content.
- **RTK**: Rewrites shell command output (git log, ls, test results) into
  condensed forms. A 500-line git log becomes a compact summary.

### Output Token Reduction

Headroom also compresses the **output** side (what the model writes back):

- **Verbosity steering**: Appends a short "be terse, don't restate context"
  directive to the system prompt (preserving the prefix cache).
- **Effort routing**: Dials down thinking effort on routine turns (file reads,
  passing tests). Full effort on new questions and errors.
- **Measurement**: Reports output savings as an estimate with confidence
  interval. Optional `HEADROOM_OUTPUT_HOLDOUT=0.1` creates a measured control
  group.

---

## Why Headroom for Production (Not LLMLingua-2)

| Criterion                          | Headroom                                     | LLMLingua-2                              |
|------------------------------------|----------------------------------------------|------------------------------------------|
| **Content awareness**              | Routes JSON/code/logs/prose to specialised compressors | One compressor for everything (token classification) |
| **Compression approach**           | Structural — preserves meaning by design     | Extractive token removal — can break grammar/coherence |
| **Production deployment**          | Library, proxy, ASGI middleware, LiteLLM callback | Library only (3 lines of Python)         |
| **Local LLM support**              | Built-in Ollama + vLLM providers             | Model-agnostic but no infra integration  |
| **Reversibility**                  | Yes — CCR, originals always recoverable      | No — tokens are gone                     |
| **KV cache preservation**          | CacheAligner stabilises prefixes             | Rewritten text breaks prefix cache       |
| **Output compression**             | Verbosity steering + effort routing          | Not designed for output compression      |
| **Training data**                  | Agentic traces (realistic production data)   | Meeting transcripts (MeetingBank)        |
| **Handles JSON**                   | SmartCrusher — 60-95% on structured data     | Unsupported in v2 mode (known bug)       |
| **Handles code**                   | AST-aware for 7 languages                    | No code awareness                        |
| **Stars / adoption**               | 72K                                          | 6.6K                                     |
| **Battle-tested**                  | Netflix production + 72K-star community      | Academic benchmarks                      |

### What Production Actually Needs

Recent production experience (documented in "Context Engineering in 2026" and the
parallel compaction paper from June 2026) shows a clear hierarchy of what works:

**Tier 1 — No-model compaction (cheapest, fastest, preserves cache):**
Cap tool outputs at fixed sizes, truncate stale history, clear old tool results.
This alone cut cost-per-turn by 38% in paired experiments while keeping quality
identical. Headroom's SmartCrusher and RTK operate in this tier.

**Tier 2 — Content-aware structural compression:**
Route different content types to specialised compressors. This is Headroom's core
value. A JSON array of 100 objects gets collapsed to schema + samples. A 500-line
git log becomes a summary. Code gets AST-stripped. Each compressor understands
what can be safely removed for its content type.

**Tier 3 — Model-based summarisation (most expensive, breaks cache):**
Only when approaching window limits, summarise old turns using the LLM itself.
This is what Claude Code's `/compact`, Codex, and optillm's compact plugin do.
Use sparingly — it is lossy, slow, and invalidates prefix cache.

LLMLingua-2 sits awkwardly between Tier 2 and Tier 3: it uses a model (tier 3
cost/complexity) but does extractive token removal rather than semantic
summarisation (worse than tier 3 quality). Headroom covers Tier 1 and Tier 2
cleanly with purpose-built compressors.

---

## How OpenProvence + Headroom Work Together in Production

```
                      PRE-COMPACTION                          POST-COMPACTION
               +---------------------------+          +---------------------------+
               |                           |          |                           |
User Query --> | OpenProvence               |          | Headroom                  |
Retrieved   --> | (sentence-level pruning)  | -------> | (output shaping +         |
Documents      | Drops irrelevant passages |          |  history compression)     |
               | Reranks by relevance      |  Qwen   | Structural compression    |
               | 80-90% context reduction  |  2-7B   | of output for downstream  |
               |                           | -------> | consumers / next turn     |
               +---------------------------+          +---------------------------+
                                                      |
                    Granularity: SENTENCE               Granularity: STRUCTURAL
                    Model: ModernBERT (30-310M)         Model: Kompress-v2-base + rules
                    What: RAG context pruning            What: Output shaping + content
                    When: Before LLM sees input                 compression for re-entry
```

**They are complementary, not overlapping:**

- **OpenProvence** operates at the **retrieval layer** — it prunes irrelevant
  retrieved documents before they enter the prompt. It is a reranker-pruner:
  scores sentences for relevance and drops the ones below threshold.

- **Headroom** operates at the **pipeline/transport layer** — it compresses
  whatever flows through the LLM pipeline (input messages, tool outputs, output
  for history). It handles the structural compression of diverse content types.

In a production RAG pipeline with a local LLM:

1. Retriever fetches N documents.
2. **OpenProvence** prunes them down to relevant sentences (pre-compaction).
3. **Headroom** compresses the prompt payload structurally before Qwen2-7B
   sees it (pre-compaction, tier 2).
4. Qwen2-7B generates a response.
5. **Headroom** shapes the output and compresses it for downstream
   consumers or conversation history (post-compaction).

---

## Headroom Integration with Ollama (Qwen2-7B)

### Library mode (inline in your app):

```python
from headroom import compress
from openai import OpenAI

# Compress messages before sending to Qwen2-7B
result = compress(messages, model="qwen2:7b")
print(f"Saved {result.tokens_saved} tokens ({result.compression_ratio:.0%})")

# Send compressed messages to Ollama
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
response = client.chat.completions.create(
    model="qwen2:7b",
    messages=result.messages,
)
```

### Proxy mode (zero code changes):

```bash
# Start Headroom proxy pointing at Ollama
export OPENAI_BASE_URL=http://localhost:11434/v1
export HEADROOM_OUTPUT_SHAPER=1  # enable output compression
headroom proxy --port 8787

# Point your app at the proxy instead of Ollama directly
# http://localhost:8787/v1/chat/completions
```

### LiteLLM callback (production gateway):

```python
import litellm
from headroom import HeadroomCallback

litellm.callbacks = [HeadroomCallback()]
response = litellm.completion(
    model="ollama/qwen2:7b",
    messages=messages,
)
```

---

## Benchmarks (Headroom)

### Input compression on real workloads:

| Workload                | Before (tokens) | After (tokens) | Savings |
|-------------------------|----------------:|---------------:|--------:|
| Code search (100 results) | 17,765        | 1,408          | **92%** |
| SRE incident debugging  | 65,694          | 5,118          | **92%** |
| GitHub issue triage      | 54,174          | 14,761         | **73%** |
| Codebase exploration     | 78,502          | 41,254         | **47%** |

### Quality preserved on standard benchmarks:

| Benchmark  | Category | Baseline | Headroom | Delta      |
|------------|----------|----------|----------|------------|
| GSM8K      | Math     | 0.870    | 0.870    | +/-0.000   |
| TruthfulQA | Factual  | 0.530    | 0.560    | +0.030     |
| SQuAD v2   | QA       | —        | 97%      | 19% compr. |
| BFCL       | Tools    | —        | 97%      | 32% compr. |

### Output reduction (proxy mode):

```
Reduction: 31.7%  (95% CI 27.7% … 35.7%)   [estimated]
```

---

## What About LLMLingua-2?

LLMLingua-2 still has a role, but it is narrower than initially presented:

**Keep it for:**
- Academic benchmarking and comparison (published results on LongBench, GSM8K, BBH)
- Prose-heavy workloads where token-level extraction works (meeting summaries, articles)
- The visual demo component — its token-level keep/drop scores are unmatched for
  showing exactly what was removed

**Do not use it for:**
- Production pipelines handling JSON, code, logs, or structured data
- Aggressive compression (>3x) on long inputs
- Any pipeline where reversibility matters
- Systems where prefix cache efficiency is important

The demo can still include LLMLingua-2 as a **comparison arm** to show the
difference between token-level extraction and content-aware structural
compression, but Headroom should be the production post-compaction tool.

---

## References

- Headroom GitHub: https://github.com/headroomlabs-ai/headroom
- Headroom docs: https://headroom-docs.vercel.app/docs
- Headroom Ollama provider: `headroom/providers/openai_compatible.py`
- Kompress-v2-base model: https://huggingface.co/chopratejas/kompress-v2-base
- "Context Engineering in 2026" — https://www.louisbouchard.ai/context-engineering-2026/
- "Parallel Context Compaction for Long-Horizon LLM Agent Serving" — https://arxiv.org/abs/2605.23296
- LLMLingua-2 paper: https://aclanthology.org/2024.findings-acl.57/
- OpenProvence: https://github.com/hotchpotch/open_provence
