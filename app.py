"""LLM Compaction Benchmarking Tool — Gradio Dashboard.

Plug in any pre- and post-compaction tools, run them against diverse
test scenarios, and measure savings, quality, and latency.
"""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr

from compaction.logger import PipelineLogger, load_logs, _run_to_dict
from compaction.pipeline import run_all_modes, OLLAMA_MODEL
from compaction.registry import REGISTRY
from compaction.auto_tune import (
    find_optimal_performance,
    find_optimal_capability,
    find_joint_optimal,
    grade_compactors,
)
from evaluation.metrics import compute_quality
from evaluation.visualizations import (
    token_comparison_chart,
    latency_breakdown_chart,
    savings_chart,
    synergy_chart,
    summary_table,
    threshold_sweep_chart,
    optimal_highlight_chart,
    compactor_grading_chart,
    grading_table,
)

DATA_DIR = Path(__file__).parent / "data"
SCENARIOS_FILE = DATA_DIR / "scenarios.json"


def _load_scenarios() -> list[dict]:
    if not SCENARIOS_FILE.exists():
        from data.fetch_papers import save_scenarios
        save_scenarios()
    with open(SCENARIOS_FILE) as f:
        return json.load(f)


def _scenario_choices() -> list[str]:
    scenarios = _load_scenarios()
    return [
        f"{s.get('category_label', s['id'])} — {s['title'][:60]}"
        for s in scenarios
    ]


def _get_scenario(scenario_idx: str, query_override: str):
    """Resolve scenario selection into query + context."""
    scenarios = _load_scenarios()
    idx = 0
    for i, s in enumerate(scenarios):
        label = f"{s.get('category_label', s['id'])} — {s['title'][:60]}"
        if scenario_idx and (scenario_idx.startswith(s["id"]) or scenario_idx == label):
            idx = i
            break
    scenario = scenarios[idx]
    query = query_override.strip() if query_override.strip() else scenario["query"]
    return scenario, query, scenario["text"]


def _scenario_info(scenario_idx: str) -> str:
    """Return a markdown description of the selected scenario."""
    scenarios = _load_scenarios()
    for s in scenarios:
        label = f"{s.get('category_label', s['id'])} — {s['title'][:60]}"
        if scenario_idx and (scenario_idx.startswith(s["id"]) or scenario_idx == label):
            tok = s.get("approx_tokens", max(1, len(s["text"]) // 4))
            desc = s.get("description", "")
            cat = s.get("category", "unknown")
            return (
                f"**Category**: `{cat}` · **~{tok:,} tokens** · "
                f"Default query: *{s['query'][:80]}*\n\n"
                f"{desc}"
            )
    return ""


# ---------------------------------------------------------------------------
# Tab 1: Benchmark Run
# ---------------------------------------------------------------------------

def run_pipeline(scenario_idx: str, query_override: str, threshold: float,
                 pre_name: str, post_name: str, progress=gr.Progress()):
    """Run all four modes for the selected scenario with chosen compactors."""
    scenarios = _load_scenarios()
    if not scenarios:
        return ("No scenarios loaded.", None, None, None, None, "", "", "")

    scenario, query, context = _get_scenario(scenario_idx, query_override)

    progress(0.1, desc="Running baseline...")
    logger = PipelineLogger()
    logger, runs = run_all_modes(
        paper_id=scenario["id"],
        paper_title=scenario["title"],
        query=query,
        context=context,
        threshold=threshold,
        logger=logger,
        pre_name=pre_name,
        post_name=post_name,
    )

    progress(0.8, desc="Computing quality metrics...")
    baseline_answer = runs[0].answer_final
    for run in runs[1:]:
        if run.answer_final and baseline_answer:
            run.quality = compute_quality(baseline_answer, run.answer_final)
    runs[0].quality = {
        "rouge_l_f1": 1.0, "nli_preservation": 1.0,
        "judge_overall": 1.0, "composite_score": 1.0,
    }

    progress(0.9, desc="Saving logs...")
    logger.save()

    runs_data = []
    for run in runs:
        d = _run_to_dict(run)
        d["quality"] = run.quality
        runs_data.append(d)

    tokens_fig = token_comparison_chart(runs_data)
    latency_fig = latency_breakdown_chart(runs_data)
    savings_fig = savings_chart(runs_data)
    syn_fig = synergy_chart(runs_data)
    table_html = summary_table(runs_data)

    answers = ""
    for run in runs:
        mode = run.mode.replace("_", " ").title()
        q = run.quality or {}
        pre_label = pre_name if run.mode in ("pre_only", "pre_post") else "—"
        post_label = post_name if run.mode in ("post_only", "pre_post") else "—"
        answers += f"### {mode}\n"
        answers += f"Pre: `{pre_label}` · Post: `{post_label}`\n\n"
        answers += f"{run.answer_final}\n\n"

        if q and mode != "Baseline":
            answers += "**Quality**: "
            parts = []
            if "rouge_l_f1" in q:
                parts.append(f"ROUGE-L: {q['rouge_l_f1']:.3f}")
            if "nli_preservation" in q:
                parts.append(f"NLI: {q['nli_preservation']:.3f}")
            if "judge_overall" in q:
                parts.append(f"Judge: {q['judge_overall']:.1%}")
            if "composite_score" in q:
                parts.append(f"**Composite: {q['composite_score']:.3f}**")
            answers += " | ".join(parts) + "\n\n"

            if "judge_explanation" in q and q["judge_explanation"]:
                answers += f"*Judge says: {q['judge_explanation']}*\n\n"

        answers += "---\n\n"

    pre_diff = _build_pre_diff(runs, pre_name)
    post_diff = _build_post_diff(runs, post_name)

    return (
        table_html,
        tokens_fig,
        latency_fig,
        savings_fig,
        syn_fig,
        answers,
        pre_diff,
        post_diff,
    )


# ---------------------------------------------------------------------------
# Tab: Find Optimal
# ---------------------------------------------------------------------------

def run_find_optimal_perf(scenario_idx, query_override, pre_name, post_name, progress=gr.Progress()):
    scenario, query, context = _get_scenario(scenario_idx, query_override)
    result = find_optimal_performance(query, context, pre_name, post_name, progress_fn=progress)
    sweep_fig = threshold_sweep_chart(result.all_trials)
    highlight_fig = optimal_highlight_chart(result)
    return result.explanation, sweep_fig, highlight_fig


def run_find_optimal_cap(scenario_idx, query_override, pre_name, post_name, progress=gr.Progress()):
    scenario, query, context = _get_scenario(scenario_idx, query_override)
    result = find_optimal_capability(query, context, pre_name, post_name, progress_fn=progress)
    sweep_fig = threshold_sweep_chart(result.all_trials)
    highlight_fig = optimal_highlight_chart(result)
    return result.explanation, sweep_fig, highlight_fig


def run_find_joint(scenario_idx, query_override, pre_name, post_name, progress=gr.Progress()):
    scenario, query, context = _get_scenario(scenario_idx, query_override)
    result = find_joint_optimal(query, context, pre_name, post_name, progress_fn=progress)
    sweep_fig = threshold_sweep_chart(result.all_trials)
    highlight_fig = optimal_highlight_chart(result)
    return result.explanation, sweep_fig, highlight_fig


# ---------------------------------------------------------------------------
# Tab: Grade Compactors
# ---------------------------------------------------------------------------

def run_grading(scenario_idx, query_override, threshold, progress=gr.Progress()):
    scenario, query, context = _get_scenario(scenario_idx, query_override)
    grades = grade_compactors(query, context, threshold=threshold, progress_fn=progress)
    chart = compactor_grading_chart(grades)
    table = grading_table(grades)
    return table, chart


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_pre_diff(runs, pre_name: str) -> str:
    for run in runs:
        if run.mode in ("pre_only", "pre_post"):
            pre = run.stages.get("pre_compaction")
            if pre:
                extra = pre.extra
                name = extra.get("compactor_name", pre_name)
                kept = extra.get("sentences_kept", 0)
                removed = extra.get("sentences_removed", 0)
                ratio = pre.compression_ratio

                text = f"**{name}**\n\n"
                text += f"- Tokens in: **{pre.tokens_in:,}** → Tokens out: **{pre.tokens_out:,}**\n"
                text += f"- Sentences kept: **{kept}** · Removed: **{removed}**\n"
                text += f"- Compression: **{ratio:.1%}**\n"

                score = extra.get("reranking_score")
                if score:
                    text += f"- Relevance score: **{score}**\n"

                text += "\n"

                kept_list = extra.get("kept_sentences", [])
                if kept_list:
                    text += "**Kept (sample):**\n"
                    for s in kept_list[:5]:
                        text += f"> {s[:150]}{'...' if len(s) > 150 else ''}\n\n"

                removed_list = extra.get("removed_sentences", [])
                if removed_list:
                    text += "**Removed (sample):**\n"
                    for s in removed_list[:3]:
                        text += f"> ~~{s[:150]}{'...' if len(s) > 150 else ''}~~\n\n"

                return text
    return "Pre-compaction not active in this run (set to `none`)."


def _build_post_diff(runs, post_name: str) -> str:
    for run in runs:
        if run.mode in ("post_only", "pre_post"):
            post = run.stages.get("post_compaction")
            if post:
                extra = post.extra
                name = extra.get("compactor_name", post_name)
                text = f"**{name}**\n\n"
                text += f"- Tokens before: **{post.tokens_in:,}**\n"
                text += f"- Tokens after: **{post.tokens_out:,}**\n"
                text += f"- Tokens saved: **{extra.get('tokens_saved', 0):,}**\n"
                text += f"- Compression: **{post.compression_ratio:.1%}**\n"
                transforms = extra.get("transforms_applied", [])
                if transforms:
                    text += f"- Transforms: `{', '.join(transforms)}`\n"
                return text
    return "Post-compaction not active in this run (set to `none`)."


# ---------------------------------------------------------------------------
# Build the app
# ---------------------------------------------------------------------------

def build_app():
    """Build the Gradio benchmarking dashboard."""
    registered_pre = ", ".join(
        f"`{name}`" for name in REGISTRY.pre_choices() if name != "none"
    )
    registered_post = ", ".join(
        f"`{name}`" for name in REGISTRY.post_choices() if name != "none"
    )

    with gr.Blocks(
        title="LLM Compaction Benchmark",
    ) as app:
        gr.Markdown(
            "# 🔬 LLM Compaction Benchmarking Tool\n"
            f"**LLM**: `{OLLAMA_MODEL}` via Ollama\n\n"
            "Plug in any pre- and post-compaction tools, run them against diverse test scenarios, "
            "and measure token savings, quality retention, and latency.\n\n"
            f"**Registered pre-compactors**: {registered_pre or '*(none)*'} · "
            f"**Post-compactors**: {registered_post or '*(none)*'}"
        )

        # ── Shared controls ──────────────────────────────────────
        with gr.Row():
            with gr.Column(scale=2):
                scenario_dd = gr.Dropdown(
                    choices=_scenario_choices(),
                    label="Test Scenario",
                    value=_scenario_choices()[0] if _scenario_choices() else None,
                )
                scenario_info = gr.Markdown(value="", label="Scenario Info")
                query_box = gr.Textbox(
                    label="Query (leave blank for scenario default)",
                    placeholder="e.g. What is the main contribution?",
                )
            with gr.Column(scale=1):
                pre_dd = gr.Dropdown(
                    choices=REGISTRY.pre_choices(),
                    label="Pre-Compactor",
                    value="OpenProvence" if "OpenProvence" in REGISTRY.pre_choices() else REGISTRY.pre_choices()[0],
                )
                post_dd = gr.Dropdown(
                    choices=REGISTRY.post_choices(),
                    label="Post-Compactor",
                    value="Headroom" if "Headroom" in REGISTRY.post_choices() else REGISTRY.post_choices()[0],
                )
                threshold_slider = gr.Slider(
                    minimum=0.01, maximum=0.5, value=0.1, step=0.01,
                    label="Pre-compaction threshold",
                )

        # Update scenario info when selection changes
        scenario_dd.change(
            fn=_scenario_info,
            inputs=[scenario_dd],
            outputs=[scenario_info],
        )

        # ── Tab 1: Benchmark Run ─────────────────────────────────
        with gr.Tab("🏃 Benchmark Run"):
            gr.Markdown(
                "Run the selected scenario through **4 modes** (baseline, pre-only, post-only, pre+post) "
                "using your chosen compactors. Compare token savings, quality, and latency side by side."
            )
            run_btn = gr.Button("▶ Run Benchmark", variant="primary", size="lg")
            summary_html = gr.HTML(label="Results Summary")
            with gr.Row():
                tokens_plot = gr.Plot(label="Token Comparison")
                latency_plot = gr.Plot(label="Latency Breakdown")
            with gr.Row():
                savings_plot = gr.Plot(label="Savings vs Quality")
            answers_md = gr.Markdown(label="Answers by Mode")

        # ── Tab 2: Grade Compactors ──────────────────────────────
        with gr.Tab("📊 Grade All Combinations"):
            gr.Markdown(
                "### Test every registered pre × post compactor combination\n"
                "Runs one trial per combination at the current threshold "
                "and grades them **A–D** based on quality retention and token savings.\n\n"
                "*Use this to compare how different tools perform on the same scenario.*"
            )
            grade_btn = gr.Button("📊 Grade All Combinations", variant="primary", size="lg")
            grade_table_html = gr.HTML(label="Grading Results")
            grade_chart = gr.Plot(label="Compactor Rankings")

        # ── Tab 3: Find Optimal ──────────────────────────────────
        with gr.Tab("🎯 Find Optimal Threshold"):
            gr.Markdown(
                "### Sweep thresholds to find the best setting\n"
                "Runs the selected compactors at 10 thresholds (0.01 → 0.50) and "
                "recommends the optimal point for your objective."
            )
            with gr.Row():
                perf_btn = gr.Button("⚡ Max Savings (quality ≥ 0.70)", variant="primary")
                cap_btn = gr.Button("🎯 Max Quality", variant="secondary")
                joint_btn = gr.Button("⚖️ Best Balance", variant="secondary")

            optimal_md = gr.Markdown(label="Recommendation")
            with gr.Row():
                sweep_plot = gr.Plot(label="Threshold Sweep")
                highlight_plot = gr.Plot(label="Optimal Point")

        # ── Tab 4: Inspect Compaction ────────────────────────────
        with gr.Tab("🔍 Inspect Compaction"):
            gr.Markdown(
                "### What did each compaction stage actually do?\n"
                "Shows exactly what was kept, removed, or transformed. "
                "Populated after a Benchmark Run."
            )
            with gr.Row():
                pre_diff_md = gr.Markdown(label="Pre-Compaction Details")
                post_diff_md = gr.Markdown(label="Post-Compaction Details")

        # ── Tab 5: Synergy Check ─────────────────────────────────
        with gr.Tab("🔗 Synergy Check"):
            gr.Markdown(
                "### Do pre + post savings compound or overlap?\n"
                "Compares the sum of individual savings vs. the actual combined savings.\n\n"
                "- **Actual > Expected** → synergistic (they help each other)\n"
                "- **Actual ≈ Expected** → independent and additive\n"
                "- **Actual < Expected** → overlapping (diminishing returns)"
            )
            synergy_plot = gr.Plot(label="Synergy Analysis")

        # ── Wire up events ───────────────────────────────────────
        run_btn.click(
            fn=run_pipeline,
            inputs=[scenario_dd, query_box, threshold_slider, pre_dd, post_dd],
            outputs=[
                summary_html, tokens_plot, latency_plot,
                savings_plot, synergy_plot, answers_md,
                pre_diff_md, post_diff_md,
            ],
        )

        optimal_inputs = [scenario_dd, query_box, pre_dd, post_dd]
        optimal_outputs = [optimal_md, sweep_plot, highlight_plot]

        perf_btn.click(fn=run_find_optimal_perf, inputs=optimal_inputs, outputs=optimal_outputs)
        cap_btn.click(fn=run_find_optimal_cap, inputs=optimal_inputs, outputs=optimal_outputs)
        joint_btn.click(fn=run_find_joint, inputs=optimal_inputs, outputs=optimal_outputs)

        grade_btn.click(
            fn=run_grading,
            inputs=[scenario_dd, query_box, threshold_slider],
            outputs=[grade_table_html, grade_chart],
        )

    return app


if __name__ == "__main__":
    app = build_app()
    app.launch(share=False)
