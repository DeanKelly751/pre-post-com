# LLM Compaction Benchmarking Tool

## What This Tool Does

This is a **benchmarking tool for evaluating LLM compaction techniques**. Plug in any pre-compaction and post-compaction repos, run them against diverse test scenarios, and get objective measurements of:

- **Token savings** — how much input/output is reduced
- **Quality retention** — whether the LLM's answer degrades
- **Latency impact** — net speedup or overhead
- **Cost efficiency** — projected savings at scale

The tool is **repo-agnostic**. It ships with two compactors pre-registered (OpenProvence for pre-compaction, Headroom for post-compaction), but these are just starting points. The value is the benchmarking harness — swap in any tool and see how it performs.

---

## Why This Exists

> "Does compaction actually help, or does it just break things?"

That's the question this tool answers, with data. Compaction techniques promise to reduce token counts and costs, but:
- Different tools work on different content types
- Savings depend heavily on document length, structure, and query specificity
- Quality degradation may not be obvious without systematic measurement
- "Pre" and "post" compaction serve fundamentally different purposes

This tool lets you **test before you commit** — run your candidate compaction tools against realistic scenarios and see the numbers before deploying to production.

---

## How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                    TEST SCENARIO                              │
│  (short prose, long RAG retrieval, JSON, code, mixed)        │
└────────────────────────────┬─────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │    YOUR PRE-COMPACTOR       │  ← any registered tool
              │    (or "none" for baseline) │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │    LOCAL LLM                │  ← Qwen2.5-7B via Ollama
              │    Generate answer          │     (or any Ollama model)
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │    YOUR POST-COMPACTOR      │  ← any registered tool
              │    (or "none" for baseline) │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │    MEASUREMENTS             │
              │  • Token counts per stage   │
              │  • Latency per stage        │
              │  • Quality vs baseline      │
              │    (ROUGE-L, NLI, Judge)    │
              └─────────────────────────────┘
```

The tool runs **4 modes** for every benchmark:

| Mode | Pre-compaction | Post-compaction | Purpose |
|------|:-:|:-:|---|
| **Baseline** | none | none | Reference point — no compaction |
| **Pre-only** | ✓ | none | Isolate pre-compaction's effect |
| **Post-only** | none | ✓ | Isolate post-compaction's effect |
| **Pre+Post** | ✓ | ✓ | Combined — test for synergy or overlap |

---

## Test Scenarios

The tool ships with 5 scenario types that stress different compaction strategies:

| Scenario | ~Tokens | What It Tests |
|----------|--------:|---|
| **Short Prose** | 1,600 | Baseline difficulty — clean, relevant text |
| **Long Prose (Multi-doc RAG)** | 2,700+ | Input pruning at scale — lots of irrelevant content |
| **JSON-Heavy** | 1,300 | Structural compression of arrays, nested objects, repeated schemas |
| **Code-Heavy** | 1,900 | Code-aware compression — AST stripping, comment removal |
| **Mixed** | 1,300 | Real-world agent context — prose + JSON + code + tables |

Different compaction tools will perform differently on each scenario. That's the point — you can see **where each tool excels and where it doesn't**.

---

## Quality Metrics

Every compacted answer is compared against the baseline (no compaction) using three independent methods:

| Metric | Type | What It Checks |
|--------|------|---|
| **ROUGE-L** | Lexical | Word-level overlap (longest common subsequence) |
| **NLI Preservation** | Semantic | Does the answer preserve the same factual claims? (bidirectional entailment) |
| **LLM-as-Judge** | Rubric | Structured scoring of factual preservation, accuracy, completeness, coherence |
| **Composite** | Weighted | `0.15 × NLI + 0.45 × Judge + 0.40 × ROUGE-L` (NLI downweighted — unreliable on paragraphs) |

The composite score provides a single number for comparison, but the individual metrics help diagnose *how* quality is affected.

---

## Plugging In Your Own Compactors

The tool uses a **plugin system** — drop a file in `plugins/` and restart.

### Fastest path

```bash
# Scaffold a template
uv run python -m compaction scaffold pre "LLMLingua-2" llmlingua

# Install the package
uv add llmlingua

# Edit plugins/pre_llmlingua_2.py — fill in the one TODO block (~5 lines)

# Restart
uv run python app.py
```

Your tool appears in the dropdowns and in Grade Compactors automatically.

### Plugin CLI

```bash
uv run python -m compaction scaffold pre "Name" package   # Generate pre-compactor template
uv run python -m compaction scaffold post "Name" package   # Generate post-compactor template
uv run python -m compaction list                           # Show all plugins
uv run python -m compaction remove <name>                  # Remove a plugin
```

### How it works

The `plugins/` directory is auto-scanned on startup. Any `.py` file containing a class that extends `PreCompactor` or `PostCompactor` is registered automatically. No config files to edit.

See `plugins/pre_openprovence.py` and `plugins/post_headroom.py` for working examples.

---

## Running the Tool

### Prerequisites

- **Ollama** running locally with a model pulled:
  ```bash
  ollama pull qwen2.5:7b-instruct
  ```

### Install & launch

```bash
cd pre-post-com
uv sync
uv run python app.py
```

### Dashboard tabs

| Tab | What It Does |
|-----|---|
| **🏃 Benchmark Run** | Run all 4 modes, compare results |
| **📊 Grade All Combinations** | Test every pre × post combination, grade A–D |
| **🎯 Find Optimal Threshold** | Sweep thresholds to find the best setting |
| **🔍 Inspect Compaction** | See what was actually kept/removed/transformed |
| **🔗 Synergy Check** | Do pre + post savings compound or overlap? |

### Jupyter notebook (offline sharing)

```bash
uv run jupyter notebook demo_report.ipynb
```

---

## What the Measurements Mean

### Token counts

| Metric | What It Is | Why It Matters |
|--------|-----------|---|
| **Raw Input** | Document tokens before any processing | Starting point — same across all modes |
| **LLM Input** | Tokens the model actually received | **The cost metric** — every token here costs compute/time/money |
| **LLM Output** | Tokens the model generated | Usually similar across modes |

### Why fewer input tokens matter

Even on a local LLM with no per-token API charge, tokens cost you:

| Cost Dimension | Impact |
|---|---|
| **Latency** | More tokens → longer attention computation → slower responses |
| **Memory** | KV cache grows linearly with sequence length |
| **Throughput** | Slower requests → fewer requests/second on same hardware |
| **Energy** | More compute per request → higher power draw |
| **API cost** | If using hosted models, savings translate directly to dollars |

---

## Understanding the Results

### What good results look like

- **Pre-compaction on long, noisy documents**: 40–60% token reduction, quality ≥ 0.85
- **Post-compaction on JSON/tool outputs**: 30–90% compression on structured content
- **Combined (synergistic)**: Each technique saves from a different source → additive

### What underwhelming results tell you

- **Pre-compaction saves little on short, focused docs**: The tool is correct — there's nothing irrelevant to prune. Test on longer, noisier content.
- **Post-compaction saves 0% on single-turn prose**: Some post-compactors are designed for multi-turn conversations, JSON, or code — not short Q&A. Switch to a different scenario.
- **Low quality scores despite good answers**: The NLI model can be harsh on paraphrased text. Read the LLM-as-judge explanation and the actual answers — they may be better than the number suggests.

### The scenarios matter

No single scenario tells the full story. A compaction tool that looks bad on short prose may be exceptional on JSON arrays. **Grade it across all scenarios** to get the full picture.

---

## Project Structure

```
pre-post-com/
├── app.py                      # Gradio benchmarking dashboard
├── demo_report.ipynb           # Jupyter notebook for offline sharing
├── DEMO.md                     # This file
├── DASHBOARD_GUIDE.md          # Detailed metric explanations
├── USAGE.md                    # Step-by-step usage guide
│
├── compaction/
│   ├── registry.py             # Pluggable compactor registry + base classes
│   ├── pre_compaction.py       # OpenProvence wrapper (example pre-compactor)
│   ├── post_compaction.py      # Headroom wrapper (example post-compactor)
│   ├── pipeline.py             # Orchestrates 4 benchmark modes
│   ├── auto_tune.py            # Threshold sweeping & grading engine
│   └── logger.py               # Structured JSON logging
│
├── evaluation/
│   ├── metrics.py              # ROUGE-L, NLI, LLM-as-judge, composite
│   └── visualizations.py       # Plotly charts and HTML tables
│
├── data/
│   ├── fetch_papers.py         # Static test scenarios (5 content types)
│   └── scenarios.json          # Generated scenario data
│
└── logs/
    └── runs.json               # Benchmark run logs (auto-generated)
```

---

## Production Considerations

This tool is **for benchmarking, not production deployment**. Key differences:

| Aspect | This Tool | Production |
|--------|-----------|------------|
| Token counting | Character approximation for input, model tokenizer for LLM | Model-specific tokenizer everywhere |
| Quality metrics | ROUGE-L + NLI + LLM-judge | Domain-specific evals + human review |
| Error handling | Minimal | Retries, fallbacks, circuit breakers |
| Input data | Static test scenarios | Live retrieval pipeline |
| Multi-turn | Single Q&A per scenario | Full conversation history |

The benchmarking results are directionally accurate — use them to decide **which tools to evaluate further** and **which scenarios they're suited for**.

---

## Known Limitations

Issues we're aware of but haven't addressed yet:

| Limitation | Impact | Workaround |
|---|---|---|
| **Single-turn only** | Post-compactors designed for multi-turn conversation history can't show their value. True pre+post synergy emerges across turns where compressed history becomes next turn's context. | Would need a multi-turn pipeline mode — significant refactor. |
| **Quality = "similarity to baseline" not "correctness"** | If compaction removes noise and the LLM produces a *better* answer, it scores low. The tool penalises improvement. | Read the actual answers alongside the scores. |
| **Pre-compactor config limited to `threshold`** | Compactors with richer configuration (chunk size, algorithm variant, min retention %) must hardcode those in their class. | Extend `PreCompactor.compact()` to accept `**kwargs`. |
| **No cross-scenario summary** | Can't run one compactor across all 5 scenarios in one click. Must run each manually. | Add a "Run All Scenarios" batch mode. |
| **Same model as generator and judge** | The judge (currently `qwen2.5:7b-instruct`) is the same model that generated the answers. Self-preference bias is possible. | Set `JUDGE_MODEL` in `evaluation/metrics.py` to a different Ollama model if available. |
| **No statistical rigour** | Single-run results, no confidence intervals or repeated trials. | Even with temperature=0, minor non-determinism exists in some backends. |
| **No retry on LLM failures** | If Ollama hiccups mid-benchmark, the run fails. | Add retry logic to `call_llm()`. |
