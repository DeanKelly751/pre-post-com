"""Structured JSON logger for the compaction pipeline.

Every pipeline run produces a log entry with per-stage metrics:
tokens, latency, compression ratios, and the actual text at each stage.
"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LOGS_DIR = Path(__file__).parent.parent / "logs"


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""
    tokens_in: int = 0
    tokens_out: int = 0
    chars_in: int = 0
    chars_out: int = 0
    compression_ratio: float = 0.0
    latency_ms: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class RunLog:
    """Complete log for a single pipeline run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    mode: str = ""
    paper_id: str = ""
    paper_title: str = ""
    query: str = ""
    stages: dict[str, StageMetrics] = field(default_factory=dict)
    quality: dict[str, float] = field(default_factory=dict)
    answer_baseline: str = ""
    answer_final: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_savings_pct: float = 0.0
    end_to_end_latency_ms: float = 0.0


class PipelineLogger:
    """Logs pipeline runs to JSON files."""

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self._runs: list[RunLog] = []

    def new_run(self, mode: str, paper_id: str, paper_title: str, query: str) -> RunLog:
        run = RunLog(mode=mode, paper_id=paper_id, paper_title=paper_title, query=query)
        self._runs.append(run)
        return run

    def log_stage(self, run: RunLog, stage_name: str, metrics: StageMetrics):
        run.stages[stage_name] = metrics

    def finalise_run(self, run: RunLog):
        """Compute totals and save."""
        input_stage = run.stages.get("input", StageMetrics())
        llm_stage = run.stages.get("llm", StageMetrics())
        post_stage = run.stages.get("post_compaction", None)

        run.total_input_tokens = input_stage.tokens_in
        # Final output: post-compacted tokens if available, else LLM output
        if post_stage:
            run.total_output_tokens = post_stage.tokens_out
        else:
            run.total_output_tokens = llm_stage.tokens_out

        # Savings: compare LLM input tokens to raw input tokens
        # (measures how much the pre-compactor reduced what the LLM saw)
        if input_stage.tokens_in > 0:
            run.total_savings_pct = (
                1 - llm_stage.tokens_in / input_stage.tokens_in
            ) * 100

        run.end_to_end_latency_ms = sum(
            s.latency_ms for s in run.stages.values()
        )

    def save(self, filename: str = "runs.json"):
        path = LOGS_DIR / filename
        data = [_run_to_dict(r) for r in self._runs]

        existing = []
        if path.exists():
            with open(path) as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []

        existing.extend(data)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(data)} run(s) to {path}")
        return path

    def get_runs(self) -> list[RunLog]:
        return list(self._runs)

    def clear(self):
        self._runs.clear()


def load_logs(filename: str = "runs.json") -> list[dict]:
    path = LOGS_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


class Timer:
    """Simple context manager for timing stages."""

    def __init__(self):
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


def _run_to_dict(run: RunLog) -> dict:
    d = {
        "run_id": run.run_id,
        "mode": run.mode,
        "paper_id": run.paper_id,
        "paper_title": run.paper_title,
        "query": run.query,
        "stages": {k: asdict(v) for k, v in run.stages.items()},
        "quality": run.quality,
        "answer_baseline": run.answer_baseline,
        "answer_final": run.answer_final,
        "total_input_tokens": run.total_input_tokens,
        "total_output_tokens": run.total_output_tokens,
        "total_savings_pct": round(run.total_savings_pct, 2),
        "end_to_end_latency_ms": round(run.end_to_end_latency_ms, 1),
    }
    return d
