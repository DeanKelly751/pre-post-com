"""Headroom — content-aware structural compression.

Install: uv add headroom-ai[all]
Repo:    https://github.com/headroomlabs-ai/headroom
"""

from compaction.registry import PostCompactor
from compaction.logger import StageMetrics, Timer


class HeadroomPostCompactor(PostCompactor):

    name = "Headroom"
    description = "Content-aware compression — routes JSON/code/prose to specialised compressors"
    url = "https://github.com/headroomlabs-ai/headroom"

    def compact(self, messages: list[dict], model: str = ""):
        from headroom import compress

        with Timer() as t:
            result = compress(messages, model=model)

        return result.messages, StageMetrics(
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
