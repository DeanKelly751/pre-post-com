"""Post-compaction wrapper using Headroom.

Compresses LLM conversation messages using Headroom's content-aware pipeline:
SmartCrusher (JSON), CodeCompressor (AST), Kompress-v2-base (prose).
"""

from __future__ import annotations

from compaction.logger import StageMetrics, Timer


def post_compact(
    messages: list[dict],
    model: str = "qwen2.5:7b-instruct",
) -> tuple[list[dict], StageMetrics]:
    """Compress messages using Headroom.

    Args:
        messages: OpenAI-format message list to compress.
        model: Model name (used for token counting heuristics).

    Returns:
        Tuple of (compressed_messages, stage_metrics).
    """
    from headroom import compress

    with Timer() as t:
        result = compress(messages, model=model)

    metrics = StageMetrics(
        tokens_in=result.tokens_before,
        tokens_out=result.tokens_after,
        chars_in=sum(len(m.get("content", "") or "") for m in messages),
        chars_out=sum(len(m.get("content", "") or "") for m in result.messages),
        compression_ratio=(
            result.compression_ratio if result.tokens_before > 0 else 0.0
        ),
        latency_ms=t.elapsed_ms,
        extra={
            "tokens_saved": result.tokens_saved,
            "transforms_applied": result.transforms_applied,
        },
    )

    return result.messages, metrics
