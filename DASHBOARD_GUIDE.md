# Dashboard Guide — Presentation Reference

A walkthrough of every element in the benchmarking dashboard, how each metric is calculated, and how to interpret results honestly.

---

## Dashboard Header

> **🔬 LLM Compaction Benchmarking Tool**

**What to say**: *"This is a benchmarking tool for evaluating LLM compaction techniques. You plug in any pre- and post-compaction tools, run them against different types of content, and get objective measurements of savings, quality, and speed. The tool is repo-agnostic — whatever compactors you register, it benchmarks them."*

---

## Shared Controls

### Test Scenario (Dropdown)

Selects which content to benchmark against. The tool ships with 5 scenario types:

| Scenario | ~Tokens | What It Stresses |
|----------|--------:|---|
| **Short Prose** | 1,600 | Clean, focused text — baseline difficulty |
| **Long Prose (Multi-doc RAG)** | 2,700+ | Many retrieved documents, lots of irrelevant content — tests pruning at scale |
| **JSON-Heavy** | 1,300 | JSON arrays, nested objects, repeated schemas — tests structural compression |
| **Code-Heavy** | 1,900 | Full code files with tests and config — tests code-aware compression |
| **Mixed** | 1,300 | Prose + JSON + code + tables — most realistic production scenario |

**What to say**: *"Different compaction tools are designed for different content types. This dropdown lets you test each tool on the scenario that's most like your production data."*

### Pre-Compactor / Post-Compactor (Dropdowns)

Select which registered compactors to use. `none` is always available as a passthrough baseline.

**What to say**: *"These dropdowns list every compaction tool registered in the system. Select the ones you want to benchmark. Use 'none' on either side to isolate the other tool's effect."*

### Threshold (Slider: 0.01–0.50)

Controls how aggressively the pre-compactor filters content (if the pre-compactor supports it). Higher = more removed.

---

## Tab 1: 🏃 Benchmark Run

The main tab. Runs 4 modes (baseline, pre-only, post-only, pre+post) and compares them.

### Results Summary Table

| Column | What It Shows | Source |
|--------|---|---|
| **Mode** | Which pipeline variant ran | Baseline / Pre Only / Post Only / Pre Post |
| **Raw Input** | Document tokens before processing | `len(text) // 4` — character approximation |
| **LLM In** | Tokens the model actually received | Ollama's `prompt_tokens` — real tokenizer count |
| **LLM Out** | Tokens the model generated | Ollama's `completion_tokens` |
| **After Post** | Tokens after post-compaction | Reported by the post-compactor |
| **Quality** | Composite score vs baseline | See "Quality Metrics" section below |
| **Latency** | Wall-clock time for entire pipeline | `time.perf_counter()` sum of all stages |

### Chart: Token Counts by Mode

Three grouped bars per mode — Raw Input, LLM Input, LLM Output.

**How to read it**: Look at the LLM Input bars. If your pre-compactor is working, those bars will be shorter than baseline. If they're the same height, the pre-compactor didn't remove anything (which may be correct for that content type).

### Chart: Latency Breakdown

Stacked bars showing time spent in each stage: pre-compaction, LLM inference, post-compaction.

**How to read it**: The LLM inference segment should shrink when pre-compaction reduces input tokens. If the pre-compaction overhead is larger than the inference savings, it's not worth it for that document length.

### Chart: Savings vs Quality

Bars (left axis) = token savings %. Line (right axis) = composite quality score.

**How to read it**:
- **Tall bars + flat line** = great result — big savings, no quality loss
- **Tall bars + dropping line** = compression is too aggressive
- **Short bars + flat line** = compactor isn't doing much on this content type
- **No bars + flat line** = compactor correctly identified nothing to compress

**What savings % means**:
```
savings_pct = (1 - mode_llm_input / baseline_llm_input) × 100
```

### Answers by Mode

Full text of each mode's answer, with quality breakdown and LLM-judge explanation. Read these to verify the numbers make sense — sometimes a 0.5 composite score hides a perfectly good answer that was just paraphrased differently.

---

## Tab 2: 📊 Grade All Combinations

Tests every registered pre × post compactor combination and ranks them.

### Grading Criteria

| Grade | Criteria |
|-------|----------|
| **A** | ROUGE-L ≥ 0.85 AND savings ≥ 20% |
| **B** | ROUGE-L ≥ 0.70 AND savings ≥ 10% |
| **C** | ROUGE-L ≥ 0.50 |
| **D** | ROUGE-L < 0.50 |

**What to say**: *"This tab answers: given all the compaction tools we have registered, which combination works best for this specific content type and query?"*

### Honest interpretation

- A grade of D doesn't mean the tool is bad — it might mean the scenario doesn't match what the tool is designed for.
- Run grading across multiple scenarios to get the full picture.
- The grading weights favour quality over savings — a tool that saves nothing but preserves quality gets C, not D.

---

## Tab 3: 🎯 Find Optimal Threshold

Sweeps 10 thresholds (0.01 → 0.50) to find the best pre-compaction setting.

### Three Modes

| Button | Objective | Selection Criteria |
|--------|---|---|
| **⚡ Max Savings** | Most compression without breaking quality | Highest savings where ROUGE-L ≥ 0.70 |
| **🎯 Max Quality** | Best answer quality with any compression | Highest ROUGE-L across all thresholds |
| **⚖️ Best Balance** | Sweet spot | 60% quality + 40% savings weighted score |

### Charts

- **Threshold Sweep**: Shows quality (line), savings (bars), and latency (dotted) across all thresholds
- **Optimal Point**: Scatter plot of all thresholds on a savings-vs-quality curve, optimal highlighted in red

---

## Tab 4: 🔍 Inspect Compaction

Shows exactly what each compaction stage did.

**Pre-compaction panel**: Tokens in/out, sentences kept/removed, compression ratio, and sample sentences.

**Post-compaction panel**: Tokens before/after, tokens saved, transforms applied.

**What to say about `router:protected:user_message`**: *"Some post-compactors will classify certain content as protected — meaning it's critical and shouldn't be compressed. That's the tool working correctly, not failing. Different content types trigger different compression strategies."*

---

## Tab 5: 🔗 Synergy Check

Tests whether pre + post savings compound or overlap.

| Result Pattern | Meaning |
|---|---|
| Actual > Expected | **Synergistic** — pre-compaction creates content the post-compactor handles better |
| Actual ≈ Expected | **Additive** — each removes different content, savings stack |
| Actual < Expected | **Overlapping** — both target the same content, diminishing returns |

---

## Quality Metrics — Full Reference

### ROUGE-L

Measures word-level overlap using the Longest Common Subsequence.

- **Precision**: Of what the compacted answer said, how much matched the baseline?
- **Recall**: Of what the baseline said, how much did the compacted answer also say?
- **F1**: Harmonic mean of precision and recall

Uses Google's `rouge-score` library with Porter stemming.

### NLI Preservation

Uses a cross-encoder NLI model to check bidirectional entailment:
- Forward: Does the baseline entail the compacted answer?
- Backward: Does the compacted answer entail the baseline?
- Preservation = geometric mean of forward and backward entailment

**Note**: NLI models can be harsh on paraphrased text. A low NLI score doesn't always mean quality loss — check the actual answers.

### LLM-as-Judge

The local LLM scores the compacted answer against the baseline on a structured rubric:
- **Factual preservation** (0–1): Are the same facts present?
- **Accuracy** (0–1): Are any facts wrong?
- **Completeness** (0–1): Is detail lost?
- **Coherence** (0–1): Is the answer well-structured?
- **Overall** (0–1): Single summary score

The judge also provides a one-sentence explanation.

**Note**: This uses the same local LLM, so it's non-deterministic and may have model-specific biases.

### Composite Score

```
composite = 0.15 × NLI + 0.45 × Judge_overall + 0.40 × ROUGE-L
```

NLI is downweighted because cross-encoder NLI models are unreliable on multi-paragraph text (they're trained on short sentence pairs). ROUGE-L and the LLM-judge are more trustworthy for this comparison task.

### Score Interpretation

| Composite | What It Means |
|:-:|---|
| **0.85–1.00** | Near-identical to baseline |
| **0.70–0.85** | Good — key facts preserved, minor detail loss |
| **0.50–0.70** | Acceptable — core answer intact, noticeably less detailed |
| **Below 0.50** | Significant quality loss — compaction too aggressive for this scenario |

---

## Token Counting Methods

| Where | Method | Detail |
|---|---|---|
| **Raw Input** | Character approximation | `len(text) // 4` (~4 chars/token for English BPE) |
| **LLM In / Out** | Model tokenizer | Ollama's API: `response.usage.prompt_tokens` / `completion_tokens` |
| **Post-compaction** | Tool-specific | Each post-compactor reports its own token counts |

---

## Common Questions

### "Why did the pre-compactor save nothing on [scenario]?"

If the document is short and most content is relevant to the query, there's nothing to prune. Pre-compaction works best on long, noisy documents (like multi-doc RAG retrieval). Try the **Long Prose** or **Mixed** scenario.

### "Why did the post-compactor save 0 tokens?"

Some post-compactors are content-type-aware and won't compress content they consider critical (like user queries in a single-turn scenario). This is correct behaviour. Try the **JSON-Heavy** or **Code-Heavy** scenario, or a post-compactor designed for the content type you're testing.

### "The quality score is low but the answers look fine?"

The NLI model is strict about paraphrasing. If ROUGE-L and the LLM-judge both say quality is good but NLI is low, the answer is probably fine — it's just worded differently. Read the judge's explanation and the actual answers.

### "Which scenario should I test first?"

Start with the scenario that's closest to your production data. If you're doing RAG retrieval, use **Long Prose**. If you're building an agent with tool calls, use **JSON-Heavy** or **Mixed**. Then run **Grade All Combinations** across all scenarios for the full picture.

### "How do I add a new compaction tool?"

1. Implement the `PreCompactor` or `PostCompactor` interface in `compaction/registry.py`
2. Register it in `build_default_registry()`
3. Restart the dashboard — it appears in the dropdowns automatically

See `DEMO.md` for a code example.

---

## Presentation Flow

1. **Explain the purpose**: "This benchmarks compaction tools — plug them in, test them, see what works for your data."
2. **Show the scenarios**: "We have 5 content types — each stresses different compaction strategies."
3. **Run a benchmark**: Pick a scenario that matches your audience's use case.
4. **Grade combinations**: "Here's how every tool combination performs on this content."
5. **Find optimal**: "For the best tool, here's the ideal threshold setting."
6. **Inspect**: "Here's exactly what got compressed and what was preserved."
7. **Key takeaway**: "Different tools work on different content. This tool helps you find what works for yours."
