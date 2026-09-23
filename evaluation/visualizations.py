"""Plotly chart builders for the compaction demo."""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _fmt_score(val) -> str:
    """Format a 0-1 score for display, or show '-' if missing."""
    if val is None or val == "-":
        return "-"
    if isinstance(val, str):
        return val
    return f"{val:.3f}"


def token_comparison_chart(runs_data: list[dict]) -> go.Figure:
    """Grouped bar chart: token counts per mode."""
    modes = []
    input_tokens = []
    llm_input = []
    llm_output = []

    for run in runs_data:
        modes.append(run["mode"].replace("_", " ").title())
        stages = run["stages"]
        input_tokens.append(stages.get("input", {}).get("tokens_in", 0))
        llm_input.append(stages.get("llm", {}).get("tokens_in", 0))
        llm_output.append(stages.get("llm", {}).get("tokens_out", 0))

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Raw Input Tokens", x=modes, y=input_tokens))
    fig.add_trace(go.Bar(name="LLM Input Tokens", x=modes, y=llm_input))
    fig.add_trace(go.Bar(name="LLM Output Tokens", x=modes, y=llm_output))

    fig.update_layout(
        title="Token Counts by Mode",
        barmode="group",
        yaxis_title="Tokens",
        template="plotly_white",
        height=450,
    )
    return fig


def latency_breakdown_chart(runs_data: list[dict]) -> go.Figure:
    """Stacked bar chart: latency per stage per mode."""
    modes = []
    pre_lat = []
    llm_lat = []
    post_lat = []

    for run in runs_data:
        modes.append(run["mode"].replace("_", " ").title())
        stages = run["stages"]
        pre_lat.append(stages.get("pre_compaction", {}).get("latency_ms", 0))
        llm_lat.append(stages.get("llm", {}).get("latency_ms", 0))
        post_lat.append(stages.get("post_compaction", {}).get("latency_ms", 0))

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Pre-Compaction", x=modes, y=pre_lat))
    fig.add_trace(go.Bar(name="LLM Inference", x=modes, y=llm_lat))
    fig.add_trace(go.Bar(name="Post-Compaction", x=modes, y=post_lat))

    fig.update_layout(
        title="Latency Breakdown by Stage",
        barmode="stack",
        yaxis_title="Milliseconds",
        template="plotly_white",
        height=450,
    )
    return fig


def savings_chart(runs_data: list[dict]) -> go.Figure:
    """Bar chart with quality overlay: savings vs quality retention."""
    modes = []
    savings = []
    quality_scores = []

    baseline_llm_in = None
    for run in runs_data:
        if run["mode"] == "baseline":
            baseline_llm_in = run["stages"].get("llm", {}).get("tokens_in", 1)
            break

    if not baseline_llm_in:
        baseline_llm_in = 1

    for run in runs_data:
        mode_name = run["mode"].replace("_", " ").title()
        modes.append(mode_name)

        llm_in = run["stages"].get("llm", {}).get("tokens_in", 0)
        saving_pct = (1 - llm_in / baseline_llm_in) * 100 if baseline_llm_in > 0 else 0
        savings.append(max(saving_pct, 0))

        q = run.get("quality", {})
        quality_scores.append(q.get("composite_score", q.get("rouge_l_f1", 1.0)) * 100)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(name="Token Savings %", x=modes, y=savings, opacity=0.7),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            name="Quality (Composite %)", x=modes, y=quality_scores,
            mode="lines+markers", line=dict(width=3),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="Token Savings vs Quality Retention",
        template="plotly_white",
        height=450,
    )
    fig.update_yaxes(title_text="Token Savings %", secondary_y=False, range=[0, 100])
    fig.update_yaxes(title_text="Quality (Composite %)", secondary_y=True, range=[0, 105])
    return fig


def synergy_chart(runs_data: list[dict]) -> go.Figure:
    """Shows whether pre+post savings are additive or overlap.

    Measures total pipeline savings: input tokens saved (pre-compaction)
    + output tokens saved (post-compaction). Previous version only measured
    input tokens, making post-compaction always show 0.
    """
    baseline_in = 1
    baseline_out = 0

    for run in runs_data:
        if run["mode"] == "baseline":
            baseline_in = run["stages"].get("llm", {}).get("tokens_in", 1)
            baseline_out = run["stages"].get("llm", {}).get("tokens_out", 0)

    def _total_savings(run: dict) -> int:
        """Total tokens saved vs baseline (input reduction + output compression)."""
        llm_in = run["stages"].get("llm", {}).get("tokens_in", 0)
        input_saved = max(baseline_in - llm_in, 0)

        post = run["stages"].get("post_compaction", {})
        post_in = post.get("tokens_in", 0)
        post_out = post.get("tokens_out", 0)
        output_saved = max(post_in - post_out, 0)

        return input_saved + output_saved

    savings_by_mode = {}
    for run in runs_data:
        savings_by_mode[run["mode"]] = _total_savings(run)

    pre_saving = savings_by_mode.get("pre_only", 0)
    post_saving = savings_by_mode.get("post_only", 0)
    combined_saving = savings_by_mode.get("pre_post", 0)
    additive = pre_saving + post_saving

    labels = ["Pre-Only", "Post-Only", "Pre + Post\n(Expected Additive)", "Pre + Post\n(Actual)"]
    values = [pre_saving, post_saving, additive, combined_saving]

    colors = ["#3498db", "#2ecc71", "#95a5a6", "#e74c3c"]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        text=[f"{v:,} tokens" for v in values],
        textposition="outside",
        marker_color=colors,
    ))

    fig.update_layout(
        title="Synergy Analysis: Total Pipeline Savings (Input + Output)",
        yaxis_title="Total Tokens Saved vs Baseline",
        template="plotly_white",
        height=450,
        annotations=[dict(
            text="Measures input reduction (pre) + output compression (post) combined",
            xref="paper", yref="paper", x=0.5, y=-0.15,
            showarrow=False, font=dict(size=11, color="gray"),
        )],
    )
    return fig


def summary_table(runs_data: list[dict]) -> str:
    """Build an HTML table summarising all runs."""
    rows = []
    for run in runs_data:
        stages = run["stages"]
        inp = stages.get("input", {})
        pre = stages.get("pre_compaction", {})
        llm = stages.get("llm", {})
        post = stages.get("post_compaction", {})
        q = run.get("quality", {})

        rows.append({
            "Mode": run["mode"].replace("_", " ").title(),
            "Raw Input": f'{inp.get("tokens_in", 0):,}',
            "After Pre": f'{pre.get("tokens_out", "-")}' if pre else "-",
            "LLM In": f'{llm.get("tokens_in", 0):,}',
            "LLM Out": f'{llm.get("tokens_out", 0):,}',
            "After Post": f'{post.get("tokens_out", "-")}' if post else "-",
            "ROUGE-L": _fmt_score(q.get("rouge_l_f1")),
            "NLI Pres.": _fmt_score(q.get("nli_preservation")),
            "Judge": _fmt_score(q.get("judge_overall")),
            "Composite": _fmt_score(q.get("composite_score")),
            "Latency": f'{run.get("end_to_end_latency_ms", 0):,.0f}ms',
        })

    header = "".join(f"<th>{k}</th>" for k in rows[0].keys())
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{v}</td>" for v in r.values()) + "</tr>"

    return f"""
    <table style="width:100%; border-collapse:collapse; font-size:14px;">
        <thead><tr style="background:#f0f0f0;">{header}</tr></thead>
        <tbody>{body}</tbody>
    </table>
    """


# ---------------------------------------------------------------------------
# Auto-tuning charts
# ---------------------------------------------------------------------------

def threshold_sweep_chart(trials: list) -> go.Figure:
    """Dual-axis chart showing quality and savings across thresholds."""
    thresholds = [t.threshold for t in trials]
    rouge_scores = [t.rouge_l_f1 * 100 for t in trials]
    savings = [t.compression_pct for t in trials]
    latencies = [t.latency_ms for t in trials]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            name="Quality (ROUGE-L F1 %)", x=thresholds, y=rouge_scores,
            mode="lines+markers", line=dict(width=3, color="#2ecc71"),
            marker=dict(size=8),
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Bar(
            name="Token Savings %", x=thresholds, y=savings,
            opacity=0.6, marker_color="#3498db",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            name="Latency (ms)", x=thresholds, y=latencies,
            mode="lines+markers", line=dict(width=2, dash="dot", color="#e74c3c"),
            marker=dict(size=6),
        ),
        secondary_y=False,
    )

    fig.update_layout(
        title="Threshold Sweep: Quality vs Savings vs Latency",
        xaxis_title="Pre-compaction Threshold",
        template="plotly_white",
        height=500,
    )
    fig.update_yaxes(title_text="Savings % / Latency (ms)", secondary_y=False)
    fig.update_yaxes(title_text="Quality (ROUGE-L F1 %)", secondary_y=True, range=[0, 105])
    return fig


def optimal_highlight_chart(result) -> go.Figure:
    """Highlight the optimal point on the quality-savings trade-off curve."""
    trials = result.all_trials
    thresholds = [t.threshold for t in trials]
    rouge_scores = [t.rouge_l_f1 for t in trials]
    savings = [t.compression_pct for t in trials]

    best = result.best
    colors = ["#e74c3c" if t.threshold == best.threshold else "#3498db" for t in trials]
    sizes = [18 if t.threshold == best.threshold else 10 for t in trials]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=savings, y=rouge_scores,
        mode="markers+text",
        marker=dict(size=sizes, color=colors),
        text=[f"{t.threshold}" for t in trials],
        textposition="top center",
        name="Threshold trials",
    ))

    # Quality floor line
    if result.mode == "performance":
        from compaction.auto_tune import QUALITY_FLOOR
        fig.add_hline(y=QUALITY_FLOOR, line_dash="dash", line_color="orange",
                      annotation_text=f"Quality floor ({QUALITY_FLOOR})")

    mode_labels = {
        "performance": "⚡ Optimal Performance",
        "capability": "🎯 Optimal Capability",
        "joint": "⚖️ Joint Optimal",
    }

    fig.update_layout(
        title=f"{mode_labels.get(result.mode, 'Optimal')} — Trade-off Curve",
        xaxis_title="Token Savings %",
        yaxis_title="ROUGE-L F1",
        template="plotly_white",
        height=500,
        yaxis_range=[0, 1.05],
    )
    return fig


def compactor_grading_chart(grades: list[dict]) -> go.Figure:
    """Bar chart ranking compactor combinations by grade score."""
    labels = [f"{g['pre']} + {g['post']}" for g in grades]
    scores = [g["grade_score"] for g in grades]
    rouge = [g["rouge_l_f1"] for g in grades]
    savings = [g["compression_pct"] for g in grades]
    grade_letters = [g["grade"] for g in grades]

    grade_colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "D": "#e74c3c"}
    colors = [grade_colors.get(g, "#95a5a6") for g in grade_letters]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=scores,
        text=[f"Grade: {g}\nROUGE: {r:.3f}\nSavings: {s:.1f}%"
              for g, r, s in zip(grade_letters, rouge, savings)],
        textposition="outside",
        marker_color=colors,
    ))

    fig.update_layout(
        title="Compactor Combination Rankings",
        yaxis_title="Joint Score (quality × 0.6 + savings × 0.4)",
        template="plotly_white",
        height=500,
        yaxis_range=[0, 1.0],
    )
    return fig


def grading_table(grades: list[dict]) -> str:
    """HTML table showing compactor grades."""
    rows_html = ""
    grade_colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f39c12", "D": "#e74c3c"}

    for g in grades:
        color = grade_colors.get(g["grade"], "#95a5a6")
        rows_html += f"""<tr>
            <td style="font-weight:bold; color:{color}; font-size:18px;">{g['grade']}</td>
            <td>{g['pre']}</td>
            <td>{g['post']}</td>
            <td>{g['rouge_l_f1']:.3f}</td>
            <td>{g['compression_pct']:.1f}%</td>
            <td>{g['latency_ms']:,}ms</td>
            <td>{g['speedup_pct']:+.1f}%</td>
            <td>{g['grade_score']:.3f}</td>
        </tr>"""

    return f"""
    <table style="width:100%; border-collapse:collapse; font-size:14px;">
        <thead><tr style="background:#f0f0f0;">
            <th>Grade</th><th>Pre-Compactor</th><th>Post-Compactor</th>
            <th>ROUGE-L F1</th><th>Token Savings</th><th>Latency</th>
            <th>Speedup</th><th>Joint Score</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    """
