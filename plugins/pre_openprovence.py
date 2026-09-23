"""OpenProvence — sentence-level reranker-pruner.

Install: uv add open-provence
Repo:    https://github.com/hotchpotch/open_provence
"""

from compaction.registry import PreCompactor
from compaction.logger import StageMetrics, Timer


class OpenProvencePreCompactor(PreCompactor):

    name = "OpenProvence"
    description = "ModernBERT cross-encoder reranker — scores & prunes sentences by query relevance"
    url = "https://github.com/hotchpotch/open_provence"

    _model = None

    def compact(self, query: str, context: str, threshold: float = 0.1):
        model = self._load_model()

        tokens_in = max(1, len(context) // 4)

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
        tokens_out = max(1, len(pruned) // 4)

        kept = result.get("sentence_texts", {}).get("kept", [])
        removed = result.get("sentence_texts", {}).get("removed", [])

        return pruned, StageMetrics(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            chars_in=len(context),
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

    def warm_up(self):
        self._load_model()

    def _load_model(self):
        if self._model is None:
            from transformers import AutoModel
            print(f"Loading OpenProvence model...")
            self._model = AutoModel.from_pretrained(
                "hotchpotch/open-provence-reranker-xsmall-v1",
                trust_remote_code=True,
            )
            print("  Model loaded.")
        return self._model
