# Usage Guide

## Quick Start

```bash
# 1. Ensure Ollama is running with a model
ollama pull qwen2.5:7b-instruct

# 2. Install dependencies
cd ~/pre-post-com
uv sync

# 3. Launch the dashboard
uv run python app.py
```

---

## Adding a New Compaction Tool (3 steps)

### Step 1: Scaffold

```bash
uv run python -m compaction scaffold pre "LLMLingua-2" llmlingua
```

This creates `plugins/pre_llmlingua_2.py` with a template.

For a post-compactor:
```bash
uv run python -m compaction scaffold post "MyCompressor" my-package
```

### Step 2: Install + edit

```bash
uv add llmlingua
```

Open the generated file. There's one `TODO` block to fill in — replace the placeholder with your repo's actual API call:

```python
# Before (template):
with Timer() as t:
    pruned = context  # <-- replace with your compaction call

# After (filled in):
with Timer() as t:
    result = self._compressor.compress_prompt(
        context=[context],
        instruction=query,
        rate=max(0.1, 1.0 - threshold * 2),
    )
    pruned = result["compressed_prompt"]
```

That's the only code you write. Everything else (metrics, charts, grading) works automatically.

### Step 3: Restart

```bash
uv run python app.py
```

Your tool appears in the dropdown. Go to **📊 Grade All Combinations** to compare it against everything else.

### Removing a tool

```bash
uv run python -m compaction remove llmlingua_2
uv run python app.py
```

### Plugin CLI reference

```bash
uv run python -m compaction scaffold pre "Name" package   # Create pre-compactor template
uv run python -m compaction scaffold post "Name" package   # Create post-compactor template
uv run python -m compaction list                           # Show all plugin files
uv run python -m compaction remove <name>                  # Remove a plugin
```

### Working examples

See these files for reference:
- `plugins/pre_openprovence.py` — pre-compactor wrapping OpenProvence
- `plugins/post_headroom.py` — post-compactor wrapping Headroom

---

## Test Scenarios

Pick the scenario closest to your production data:

| Scenario | Content Type | Best For Testing |
|----------|---|---|
| **Short Prose** | Clean paper excerpt (~1,600 tok) | Baseline — does the compactor do anything? |
| **Long Prose (Multi-doc)** | Multiple retrieved documents (~2,700 tok) | Pre-compaction at scale — lots of noise |
| **JSON-Heavy** | API responses, monitoring data | Structural compression (JSON arrays) |
| **Code-Heavy** | Code review context with tests & config | Code-aware compression (AST, comments) |
| **Mixed** | Prose + JSON + code + logs combined | Most realistic production scenario |

---

## Dashboard Tabs

### 🏃 Benchmark Run

Runs 4 modes (baseline, pre-only, post-only, pre+post) and compares them.

1. Select scenario + compactors
2. Click **▶ Run Benchmark**
3. Wait ~20–30s

### 📊 Grade All Combinations

Tests every registered pre × post combination. Grades A–D.

### 🎯 Find Optimal Threshold

Sweeps 10 thresholds. Three modes:
- **⚡ Max Savings**: Most compression where quality stays ≥ 0.70
- **🎯 Max Quality**: Best answer quality
- **⚖️ Best Balance**: 60% quality + 40% savings

### 🔍 Inspect Compaction

See what was kept/removed/transformed.

### 🔗 Synergy Check

Do pre + post savings compound or overlap?

---

## Quick Recipes

| I Want To... | Do This |
|---|---|
| **Add a new tool** | `uv run python -m compaction scaffold pre "Name" pkg` → edit → restart |
| **Remove a tool** | `uv run python -m compaction remove name` → restart |
| **Compare two pre-compactors** | Add both → Grade All Combinations |
| **Find the best threshold** | Find Optimal → ⚖️ Best Balance |
| **Check if pre+post helps** | Benchmark Run → Synergy Check |
| **See what was pruned** | Benchmark Run → Inspect Compaction |

---

## How the Plugin System Works

```
plugins/
├── pre_openprovence.py     # Pre-compactor (auto-discovered)
├── post_headroom.py        # Post-compactor (auto-discovered)
├── pre_llmlingua_2.py      # You add this
└── post_my_tool.py         # And this
```

On startup, the system scans `plugins/*.py` and registers any class that extends `PreCompactor` or `PostCompactor`. No need to edit any config files.

Each plugin file is self-contained — the import, the class, and the API call are all in one file. To understand how it works, read `plugins/pre_openprovence.py` (60 lines) or `plugins/post_headroom.py` (35 lines).

### What your plugin needs to return

**Pre-compactor**: `compact(query, context, threshold)` → `(pruned_text, StageMetrics)`

**Post-compactor**: `compact(messages, model)` → `(compressed_messages, StageMetrics)`

The `messages` format is OpenAI-style:
```python
[
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
]
```

`StageMetrics` needs: `tokens_in`, `tokens_out`, `chars_in`, `chars_out`, `compression_ratio`, `latency_ms`. The `extra` dict is optional metadata.

---

## Other Ways to Run

### CLI (no UI)

```bash
uv run python -c "
from data.fetch_papers import load_scenarios
from compaction.pipeline import run_all_modes

scenarios = load_scenarios()
s = scenarios[0]

logger, runs = run_all_modes(
    paper_id=s['id'],
    paper_title=s['title'],
    query=s['query'],
    context=s['text'],
    threshold=0.1,
    pre_name='OpenProvence',
    post_name='Headroom',
)
logger.save()
"
```

### Jupyter Notebook

```bash
uv run jupyter notebook demo_report.ipynb
```
