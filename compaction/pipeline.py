"""Pipeline orchestrator: runs the same query through four compaction modes.

Uses the pluggable compactor registry so pre/post tools can be swapped.
"""

from __future__ import annotations

from openai import OpenAI

from compaction.logger import PipelineLogger, RunLog, StageMetrics, Timer
from compaction.registry import REGISTRY

OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
SYSTEM_PROMPT = "You are a helpful research assistant. Answer based on the provided context. Be thorough but concise."

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    return _client


def count_tokens(text: str) -> int:
    """Approximate token count (~4 chars per token)."""
    return max(1, len(text) // 4)


def call_llm(context: str, query: str) -> tuple[str, StageMetrics]:
    """Send a query with context to the local LLM. Deterministic (temperature=0)."""
    client = _get_client()

    user_msg = f"Context:\n{context}\n\n---\nQuestion: {query}"
    prompt_tokens = count_tokens(SYSTEM_PROMPT + user_msg)

    with Timer() as t:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=1024,
        )

    answer = response.choices[0].message.content or ""
    completion_tokens = count_tokens(answer)

    usage = response.usage
    if usage:
        prompt_tokens = usage.prompt_tokens or prompt_tokens
        completion_tokens = usage.completion_tokens or completion_tokens

    metrics = StageMetrics(
        tokens_in=prompt_tokens,
        tokens_out=completion_tokens,
        chars_in=len(user_msg),
        chars_out=len(answer),
        latency_ms=t.elapsed_ms,
        extra={
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )

    return answer, metrics


def build_messages(context: str, query: str, answer: str | None = None) -> list[dict]:
    """Build OpenAI-format messages for post-compaction."""
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\n---\nQuestion: {query}"},
    ]
    if answer:
        msgs.append({"role": "assistant", "content": answer})
    return msgs


def extract_assistant_answer(messages: list[dict]) -> str | None:
    """Extract the assistant's answer from a message list (post-compaction may have changed it)."""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return None


def run_baseline(
    logger: PipelineLogger,
    paper_id: str,
    paper_title: str,
    query: str,
    context: str,
) -> RunLog:
    """Mode 1: No compaction — raw context in, raw output out."""
    run = logger.new_run("baseline", paper_id, paper_title, query)

    input_tokens = count_tokens(context)
    logger.log_stage(run, "input", StageMetrics(
        tokens_in=input_tokens, tokens_out=input_tokens,
        chars_in=len(context), chars_out=len(context),
    ))

    answer, llm_metrics = call_llm(context, query)
    logger.log_stage(run, "llm", llm_metrics)

    run.answer_baseline = answer
    run.answer_final = answer
    logger.finalise_run(run)
    return run


def run_pre_only(
    logger: PipelineLogger,
    paper_id: str,
    paper_title: str,
    query: str,
    context: str,
    threshold: float = 0.1,
    pre_name: str = "OpenProvence",
) -> RunLog:
    """Mode 2: Pre-compaction only (pluggable)."""
    pre = REGISTRY.get_pre(pre_name)
    run = logger.new_run("pre_only", paper_id, paper_title, query)

    input_tokens = count_tokens(context)
    logger.log_stage(run, "input", StageMetrics(
        tokens_in=input_tokens, tokens_out=input_tokens,
        chars_in=len(context), chars_out=len(context),
    ))

    pruned, pre_metrics = pre.compact(query, context, threshold=threshold)
    pre_metrics.extra["compactor_name"] = pre.name
    logger.log_stage(run, "pre_compaction", pre_metrics)

    answer, llm_metrics = call_llm(pruned, query)
    logger.log_stage(run, "llm", llm_metrics)

    run.answer_final = answer
    logger.finalise_run(run)
    return run


def run_post_only(
    logger: PipelineLogger,
    paper_id: str,
    paper_title: str,
    query: str,
    context: str,
    post_name: str = "Headroom",
) -> RunLog:
    """Mode 3: Post-compaction only (pluggable)."""
    post = REGISTRY.get_post(post_name)
    run = logger.new_run("post_only", paper_id, paper_title, query)

    input_tokens = count_tokens(context)
    logger.log_stage(run, "input", StageMetrics(
        tokens_in=input_tokens, tokens_out=input_tokens,
        chars_in=len(context), chars_out=len(context),
    ))

    answer, llm_metrics = call_llm(context, query)
    logger.log_stage(run, "llm", llm_metrics)

    messages = build_messages(context, query, answer)
    compressed_msgs, post_metrics = post.compact(messages, model=OLLAMA_MODEL)
    post_metrics.extra["compactor_name"] = post.name
    logger.log_stage(run, "post_compaction", post_metrics)

    compressed_answer = extract_assistant_answer(compressed_msgs)
    run.answer_final = compressed_answer if compressed_answer is not None else answer
    logger.finalise_run(run)
    return run


def run_pre_post(
    logger: PipelineLogger,
    paper_id: str,
    paper_title: str,
    query: str,
    context: str,
    threshold: float = 0.1,
    pre_name: str = "OpenProvence",
    post_name: str = "Headroom",
) -> RunLog:
    """Mode 4: Pre + Post compaction combined (pluggable)."""
    pre = REGISTRY.get_pre(pre_name)
    post = REGISTRY.get_post(post_name)
    run = logger.new_run("pre_post", paper_id, paper_title, query)

    input_tokens = count_tokens(context)
    logger.log_stage(run, "input", StageMetrics(
        tokens_in=input_tokens, tokens_out=input_tokens,
        chars_in=len(context), chars_out=len(context),
    ))

    pruned, pre_metrics = pre.compact(query, context, threshold=threshold)
    pre_metrics.extra["compactor_name"] = pre.name
    logger.log_stage(run, "pre_compaction", pre_metrics)

    answer, llm_metrics = call_llm(pruned, query)
    logger.log_stage(run, "llm", llm_metrics)

    messages = build_messages(pruned, query, answer)
    compressed_msgs, post_metrics = post.compact(messages, model=OLLAMA_MODEL)
    post_metrics.extra["compactor_name"] = post.name
    logger.log_stage(run, "post_compaction", post_metrics)

    compressed_answer = extract_assistant_answer(compressed_msgs)
    run.answer_final = compressed_answer if compressed_answer is not None else answer
    logger.finalise_run(run)
    return run


def run_all_modes(
    paper_id: str,
    paper_title: str,
    query: str,
    context: str,
    threshold: float = 0.1,
    logger: PipelineLogger | None = None,
    pre_name: str = "OpenProvence",
    post_name: str = "Headroom",
) -> tuple[PipelineLogger, list[RunLog]]:
    """Run all four modes for a single scenario with pluggable compactors."""
    if logger is None:
        logger = PipelineLogger()

    print(f"\n{'='*60}")
    print(f"Paper: {paper_title[:60]}")
    print(f"Query: {query}")
    print(f"Pre: {pre_name} | Post: {post_name} | Threshold: {threshold}")
    print(f"{'='*60}")

    runs = []

    print("\n[1/4] Running baseline...")
    runs.append(run_baseline(logger, paper_id, paper_title, query, context))
    baseline_answer = runs[0].answer_baseline

    print(f"[2/4] Running pre-compaction only ({pre_name})...")
    runs.append(run_pre_only(logger, paper_id, paper_title, query, context, threshold, pre_name))

    print(f"[3/4] Running post-compaction only ({post_name})...")
    runs.append(run_post_only(logger, paper_id, paper_title, query, context, post_name))

    print(f"[4/4] Running {pre_name} + {post_name} combined...")
    runs.append(run_pre_post(logger, paper_id, paper_title, query, context, threshold, pre_name, post_name))

    for r in runs:
        r.answer_baseline = baseline_answer

    _print_summary(runs)
    return logger, runs


def _print_summary(runs: list[RunLog]):
    """Print a quick comparison table."""
    print(f"\n{'Mode':<15} {'Input Tok':>10} {'LLM In':>10} {'LLM Out':>10} {'Latency':>10}")
    print("-" * 60)
    for run in runs:
        input_tok = run.stages.get("input", StageMetrics()).tokens_in
        llm = run.stages.get("llm", StageMetrics())
        llm_in = llm.tokens_in
        llm_out = llm.tokens_out
        latency = run.end_to_end_latency_ms

        print(f"{run.mode:<15} {input_tok:>10,} {llm_in:>10,} {llm_out:>10,} {latency:>9,.0f}ms")
