"""Auto-tuning engine for finding optimal compaction settings.

Sweeps thresholds and compactor combinations to find:
- Optimal Performance: max speed/savings without quality degradation
- Optimal Capability: best answer quality regardless of cost
- Joint Decision: best balance of both (Pareto-optimal)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from compaction.logger import StageMetrics, Timer
from compaction.pipeline import call_llm, build_messages, count_tokens, OLLAMA_MODEL
from compaction.registry import REGISTRY, PreCompactor, PostCompactor
from evaluation.metrics import compute_quality_fast, compute_rouge_l


@dataclass
class TuningResult:
    """Result from a single threshold/compactor trial."""
    pre_compactor: str
    post_compactor: str
    threshold: float
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    latency_ms: float = 0.0
    compression_pct: float = 0.0
    rouge_l_f1: float = 0.0
    answer: str = ""
    pre_metrics: dict = field(default_factory=dict)
    post_metrics: dict = field(default_factory=dict)


@dataclass
class OptimalResult:
    """The recommended optimal setting from a tuning sweep."""
    mode: str  # "performance", "capability", "joint"
    best: TuningResult | None = None
    all_trials: list[TuningResult] = field(default_factory=list)
    baseline_latency: float = 0.0
    baseline_tokens: int = 0
    explanation: str = ""


def _run_single_trial(
    query: str,
    context: str,
    pre: PreCompactor,
    post: PostCompactor,
    threshold: float,
    baseline_answer: str,
    baseline_llm_in: int,
) -> TuningResult:
    """Run one pre+LLM+post trial and score it."""

    pruned, pre_metrics = pre.compact(query, context, threshold=threshold)
    answer, llm_metrics = call_llm(pruned, query)

    msgs = build_messages(pruned, query, answer)
    compressed_msgs, post_metrics = post.compact(msgs, model=OLLAMA_MODEL)

    # Use fast quality (ROUGE-L only) for sweeps/grading to avoid slow judge calls
    quality = compute_quality_fast(baseline_answer, answer) if baseline_answer else {}
    rouge_f1 = quality.get("rouge_l_f1", 1.0)

    compression = (1 - llm_metrics.tokens_in / baseline_llm_in) * 100 if baseline_llm_in > 0 else 0
    total_latency = pre_metrics.latency_ms + llm_metrics.latency_ms + post_metrics.latency_ms

    return TuningResult(
        pre_compactor=pre.name,
        post_compactor=post.name,
        threshold=threshold,
        llm_input_tokens=llm_metrics.tokens_in,
        llm_output_tokens=llm_metrics.tokens_out,
        latency_ms=total_latency,
        compression_pct=max(compression, 0),
        rouge_l_f1=rouge_f1,
        answer=answer,
        pre_metrics=asdict(pre_metrics),
        post_metrics=asdict(post_metrics),
    )


THRESHOLD_SWEEP = [0.01, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
QUALITY_FLOOR = 0.70


def find_optimal_performance(
    query: str,
    context: str,
    pre_name: str = "OpenProvence",
    post_name: str = "Headroom",
    quality_floor: float = QUALITY_FLOOR,
    progress_fn=None,
) -> OptimalResult:
    """Sweep thresholds to find max savings without quality dropping below floor."""
    pre = REGISTRY.get_pre(pre_name)
    post = REGISTRY.get_post(post_name)
    if hasattr(pre, "warm_up"):
        pre.warm_up()

    if progress_fn:
        progress_fn(0.05, desc="Running baseline...")
    baseline_answer, baseline_metrics = call_llm(context, query)
    baseline_llm_in = baseline_metrics.tokens_in
    baseline_latency = baseline_metrics.latency_ms

    trials = []
    for i, thresh in enumerate(THRESHOLD_SWEEP):
        if progress_fn:
            progress_fn(0.1 + 0.8 * (i / len(THRESHOLD_SWEEP)), desc=f"Testing threshold {thresh}...")
        trial = _run_single_trial(query, context, pre, post, thresh, baseline_answer, baseline_llm_in)
        trials.append(trial)
        print(f"  threshold={thresh:.2f}  tokens={trial.llm_input_tokens:,}  "
              f"rouge={trial.rouge_l_f1:.3f}  latency={trial.latency_ms:.0f}ms  "
              f"savings={trial.compression_pct:.1f}%")

    qualifying = [t for t in trials if t.rouge_l_f1 >= quality_floor]
    if qualifying:
        best = max(qualifying, key=lambda t: t.compression_pct)
        explanation = (
            f"**Optimal Performance**: threshold **{best.threshold}** gives "
            f"**{best.compression_pct:.1f}%** token savings with ROUGE-L F1 of "
            f"**{best.rouge_l_f1:.3f}** (above floor of {quality_floor}).\n\n"
            f"Latency: **{best.latency_ms:,.0f}ms** vs baseline **{baseline_latency:,.0f}ms** "
            f"({(1 - best.latency_ms / baseline_latency) * 100:.0f}% faster)."
        )
    else:
        best = min(trials, key=lambda t: abs(t.rouge_l_f1 - quality_floor))
        explanation = (
            f"⚠️ No threshold met the quality floor of {quality_floor}. "
            f"Closest was threshold **{best.threshold}** with ROUGE-L F1 **{best.rouge_l_f1:.3f}**. "
            f"Consider lowering the quality floor or using a different compactor."
        )

    return OptimalResult(
        mode="performance",
        best=best,
        all_trials=trials,
        baseline_latency=baseline_latency,
        baseline_tokens=baseline_llm_in,
        explanation=explanation,
    )


def find_optimal_capability(
    query: str,
    context: str,
    pre_name: str = "OpenProvence",
    post_name: str = "Headroom",
    progress_fn=None,
) -> OptimalResult:
    """Find the threshold that produces the highest quality answer."""
    pre = REGISTRY.get_pre(pre_name)
    post = REGISTRY.get_post(post_name)
    if hasattr(pre, "warm_up"):
        pre.warm_up()

    if progress_fn:
        progress_fn(0.05, desc="Running baseline...")
    baseline_answer, baseline_metrics = call_llm(context, query)
    baseline_llm_in = baseline_metrics.tokens_in
    baseline_latency = baseline_metrics.latency_ms

    trials = []
    for i, thresh in enumerate(THRESHOLD_SWEEP):
        if progress_fn:
            progress_fn(0.1 + 0.8 * (i / len(THRESHOLD_SWEEP)), desc=f"Testing threshold {thresh}...")
        trial = _run_single_trial(query, context, pre, post, thresh, baseline_answer, baseline_llm_in)
        trials.append(trial)
        print(f"  threshold={thresh:.2f}  tokens={trial.llm_input_tokens:,}  "
              f"rouge={trial.rouge_l_f1:.3f}  latency={trial.latency_ms:.0f}ms")

    best = max(trials, key=lambda t: t.rouge_l_f1)

    if best.rouge_l_f1 > 0.95:
        explanation = (
            f"**Optimal Capability**: threshold **{best.threshold}** produces the best quality "
            f"(ROUGE-L F1 **{best.rouge_l_f1:.3f}**) while still saving "
            f"**{best.compression_pct:.1f}%** tokens.\n\n"
            f"At this setting, answer quality is near-identical to baseline."
        )
    else:
        explanation = (
            f"**Optimal Capability**: threshold **{best.threshold}** gave the highest quality "
            f"(ROUGE-L F1 **{best.rouge_l_f1:.3f}**). Token savings: **{best.compression_pct:.1f}%**.\n\n"
            f"Quality loss is noticeable — consider whether the compression is worth the trade-off."
        )

    return OptimalResult(
        mode="capability",
        best=best,
        all_trials=trials,
        baseline_latency=baseline_latency,
        baseline_tokens=baseline_llm_in,
        explanation=explanation,
    )


def find_joint_optimal(
    query: str,
    context: str,
    pre_name: str = "OpenProvence",
    post_name: str = "Headroom",
    quality_weight: float = 0.6,
    performance_weight: float = 0.4,
    quality_floor: float = QUALITY_FLOOR,
    progress_fn=None,
) -> OptimalResult:
    """Find the best balance of quality and performance."""
    pre = REGISTRY.get_pre(pre_name)
    post = REGISTRY.get_post(post_name)
    if hasattr(pre, "warm_up"):
        pre.warm_up()

    if progress_fn:
        progress_fn(0.05, desc="Running baseline...")
    baseline_answer, baseline_metrics = call_llm(context, query)
    baseline_llm_in = baseline_metrics.tokens_in
    baseline_latency = baseline_metrics.latency_ms

    trials = []
    for i, thresh in enumerate(THRESHOLD_SWEEP):
        if progress_fn:
            progress_fn(0.1 + 0.8 * (i / len(THRESHOLD_SWEEP)), desc=f"Testing threshold {thresh}...")
        trial = _run_single_trial(query, context, pre, post, thresh, baseline_answer, baseline_llm_in)
        trials.append(trial)
        print(f"  threshold={thresh:.2f}  tokens={trial.llm_input_tokens:,}  "
              f"rouge={trial.rouge_l_f1:.3f}  savings={trial.compression_pct:.1f}%")

    max_savings = max(t.compression_pct for t in trials) or 1.0

    qualifying = [t for t in trials if t.rouge_l_f1 >= quality_floor]
    if not qualifying:
        qualifying = trials

    def joint_score(t: TuningResult) -> float:
        normalised_savings = t.compression_pct / max_savings
        return quality_weight * t.rouge_l_f1 + performance_weight * normalised_savings

    best = max(qualifying, key=joint_score)
    score = joint_score(best)

    explanation = (
        f"**Joint Optimal**: threshold **{best.threshold}** balances quality and performance.\n\n"
        f"- Quality: ROUGE-L F1 **{best.rouge_l_f1:.3f}**\n"
        f"- Token savings: **{best.compression_pct:.1f}%**\n"
        f"- Latency: **{best.latency_ms:,.0f}ms** vs baseline **{baseline_latency:,.0f}ms**\n"
        f"- Joint score: **{score:.3f}** "
        f"(weights: quality={quality_weight}, performance={performance_weight})\n\n"
        f"This threshold gives you the best of both worlds — meaningful savings without "
        f"significant quality degradation."
    )

    return OptimalResult(
        mode="joint",
        best=best,
        all_trials=trials,
        baseline_latency=baseline_latency,
        baseline_tokens=baseline_llm_in,
        explanation=explanation,
    )


def grade_compactors(
    query: str,
    context: str,
    threshold: float = 0.1,
    progress_fn=None,
) -> list[dict]:
    """Grade every registered pre×post compactor combination."""
    pre_names = REGISTRY.pre_choices()
    post_names = REGISTRY.post_choices()
    combos = [(p, q) for p in pre_names for q in post_names]

    if progress_fn:
        progress_fn(0.05, desc="Running baseline...")
    baseline_answer, baseline_metrics = call_llm(context, query)
    baseline_llm_in = baseline_metrics.tokens_in
    baseline_latency = baseline_metrics.latency_ms

    results = []
    for i, (pre_name, post_name) in enumerate(combos):
        if progress_fn:
            progress_fn(0.1 + 0.8 * (i / len(combos)), desc=f"Testing {pre_name} + {post_name}...")

        pre = REGISTRY.get_pre(pre_name)
        post = REGISTRY.get_post(post_name)
        if hasattr(pre, "warm_up"):
            pre.warm_up()

        trial = _run_single_trial(query, context, pre, post, threshold, baseline_answer, baseline_llm_in)
        print(f"  {pre_name} + {post_name}: rouge={trial.rouge_l_f1:.3f}  "
              f"savings={trial.compression_pct:.1f}%  latency={trial.latency_ms:.0f}ms")

        results.append({
            "pre": pre_name,
            "post": post_name,
            "threshold": threshold,
            "llm_input_tokens": trial.llm_input_tokens,
            "compression_pct": round(trial.compression_pct, 1),
            "rouge_l_f1": round(trial.rouge_l_f1, 3),
            "latency_ms": round(trial.latency_ms),
            "answer_preview": trial.answer[:200],
            "baseline_tokens": baseline_llm_in,
            "baseline_latency_ms": round(baseline_latency),
            "speedup_pct": round((1 - trial.latency_ms / baseline_latency) * 100, 1) if baseline_latency > 0 else 0,
        })

    for r in results:
        r["grade_score"] = round(0.6 * r["rouge_l_f1"] + 0.4 * (r["compression_pct"] / 100), 3)

    results.sort(key=lambda r: r["grade_score"], reverse=True)

    for r in results:
        if r["rouge_l_f1"] >= 0.85 and r["compression_pct"] >= 20:
            r["grade"] = "A"
        elif r["rouge_l_f1"] >= 0.70 and r["compression_pct"] >= 10:
            r["grade"] = "B"
        elif r["rouge_l_f1"] >= 0.50:
            r["grade"] = "C"
        else:
            r["grade"] = "D"

    return results
