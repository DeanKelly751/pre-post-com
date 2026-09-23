"""Pre-compaction wrapper using OpenProvence.

Prunes irrelevant sentences from retrieved documents before they reach the LLM.
Uses a lightweight ModernBERT-based reranker-pruner model.
"""

from __future__ import annotations

from transformers import AutoModel

from compaction.logger import StageMetrics, Timer


_model = None

MODEL_NAME = "hotchpotch/open-provence-reranker-xsmall-v1"


def _get_model():
    global _model
    if _model is None:
        print(f"Loading OpenProvence model: {MODEL_NAME}")
        _model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)
        print("  Model loaded.")
    return _model


def _count_tokens(text: str) -> int:
    """Approximate token count (~4 chars per token)."""
    return max(1, len(text) // 4)


def pre_compact(
    query: str,
    context: str,
    threshold: float = 0.1,
) -> tuple[str, StageMetrics]:
    """Prune context using OpenProvence.

    Args:
        query: The user's question.
        context: The full retrieved document text.
        threshold: Pruning threshold (0.05-0.5). Higher = more aggressive.

    Returns:
        Tuple of (pruned_context, stage_metrics).
    """
    model = _get_model()

    tokens_in = _count_tokens(context)
    chars_in = len(context)

    with Timer() as t:
        result = model.process(
            question=query,
            context=context,
            threshold=threshold,
            show_progress=False,
            return_sentence_metrics=True,
            return_sentence_texts=True,
        )

    pruned = result["pruned_context"]
    tokens_out = _count_tokens(pruned)

    kept = result.get("sentence_texts", {}).get("kept", [])
    removed = result.get("sentence_texts", {}).get("removed", [])

    metrics = StageMetrics(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        chars_in=chars_in,
        chars_out=len(pruned),
        compression_ratio=result.get("compression_rate", 0) / 100,
        latency_ms=t.elapsed_ms,
        extra={
            "reranking_score": round(result.get("reranking_score", 0), 4),
            "threshold": threshold,
            "sentences_kept": len(kept),
            "sentences_removed": len(removed),
            "kept_sentences": kept[:10],
            "removed_sentences": removed[:5],
        },
    )

    return pruned, metrics
