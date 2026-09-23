"""Pluggable compaction registry with auto-discovery.

Base classes for pre- and post-compactors, plus automatic loading of
plugin files from the plugins/ directory.

To add a new tool:
  1. Drop a .py file in plugins/
  2. Define a class extending PreCompactor or PostCompactor
  3. Restart the dashboard — it's registered automatically
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from compaction.logger import StageMetrics


PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------

class PreCompactor(ABC):
    """Base class for all pre-compaction tools."""

    name: str = "base"
    description: str = ""
    url: str = ""

    @abstractmethod
    def compact(
        self, query: str, context: str, threshold: float = 0.1,
    ) -> tuple[str, StageMetrics]:
        """Prune context before the LLM sees it.

        Returns:
            (pruned_context, stage_metrics)
        """

    def warm_up(self) -> None:
        """Optional: pre-load models so first call isn't slow."""


class PostCompactor(ABC):
    """Base class for all post-compaction tools."""

    name: str = "base"
    description: str = ""
    url: str = ""

    @abstractmethod
    def compact(
        self, messages: list[dict], model: str = "",
    ) -> tuple[list[dict], StageMetrics]:
        """Compress a message sequence after LLM generation.

        Returns:
            (compressed_messages, stage_metrics)
        """


# ---------------------------------------------------------------------------
# Built-in null compactors (always available)
# ---------------------------------------------------------------------------

class NullPreCompactor(PreCompactor):
    """No-op pre-compactor (passthrough). Used as baseline."""

    name = "none"
    description = "No pre-compaction (baseline passthrough)"

    def compact(self, query: str, context: str, threshold: float = 0.1):
        tokens = max(1, len(context) // 4)
        return context, StageMetrics(
            tokens_in=tokens, tokens_out=tokens,
            chars_in=len(context), chars_out=len(context),
            compression_ratio=0.0, latency_ms=0.0,
        )


class NullPostCompactor(PostCompactor):
    """No-op post-compactor (passthrough). Used as baseline."""

    name = "none"
    description = "No post-compaction (baseline passthrough)"

    def compact(self, messages: list[dict], model: str = ""):
        chars = sum(len(m.get("content", "") or "") for m in messages)
        tokens = max(1, chars // 4)
        return messages, StageMetrics(
            tokens_in=tokens, tokens_out=tokens,
            chars_in=chars, chars_out=chars,
            compression_ratio=0.0, latency_ms=0.0,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class CompactorRegistry:
    """Central registry of available pre- and post-compactors."""

    pre_compactors: dict[str, PreCompactor] = field(default_factory=dict)
    post_compactors: dict[str, PostCompactor] = field(default_factory=dict)

    def register_pre(self, compactor: PreCompactor) -> None:
        self.pre_compactors[compactor.name] = compactor

    def register_post(self, compactor: PostCompactor) -> None:
        self.post_compactors[compactor.name] = compactor

    def get_pre(self, name: str) -> PreCompactor:
        if name not in self.pre_compactors:
            raise KeyError(f"Pre-compactor '{name}' not found. Available: {list(self.pre_compactors)}")
        return self.pre_compactors[name]

    def get_post(self, name: str) -> PostCompactor:
        if name not in self.post_compactors:
            raise KeyError(f"Post-compactor '{name}' not found. Available: {list(self.post_compactors)}")
        return self.post_compactors[name]

    def pre_choices(self) -> list[str]:
        return list(self.pre_compactors.keys())

    def post_choices(self) -> list[str]:
        return list(self.post_compactors.keys())


# ---------------------------------------------------------------------------
# Plugin auto-discovery
# ---------------------------------------------------------------------------

def _discover_plugins(registry: CompactorRegistry) -> None:
    """Scan plugins/ directory and register any PreCompactor/PostCompactor classes found."""
    if not PLUGINS_DIR.exists():
        return

    for py_file in sorted(PLUGINS_DIR.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"plugins.{py_file.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"⚠️  Failed to load plugin {py_file.name}: {e}")
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is PreCompactor or obj is PostCompactor:
                continue
            if obj is NullPreCompactor or obj is NullPostCompactor:
                continue

            if issubclass(obj, PreCompactor) and hasattr(obj, 'name') and obj.name != "base":
                try:
                    instance = obj()
                    registry.register_pre(instance)
                    print(f"  ✓ Pre-compactor: {instance.name} (from {py_file.name})")
                except Exception as e:
                    print(f"  ✗ Failed to instantiate {obj.__name__}: {e}")

            elif issubclass(obj, PostCompactor) and hasattr(obj, 'name') and obj.name != "base":
                try:
                    instance = obj()
                    registry.register_post(instance)
                    print(f"  ✓ Post-compactor: {instance.name} (from {py_file.name})")
                except Exception as e:
                    print(f"  ✗ Failed to instantiate {obj.__name__}: {e}")


def build_default_registry() -> CompactorRegistry:
    """Create the registry with null baselines + auto-discovered plugins."""
    reg = CompactorRegistry()

    # Always-available baselines
    reg.register_pre(NullPreCompactor())
    reg.register_post(NullPostCompactor())

    # Auto-discover from plugins/
    print("Loading plugins...")
    _discover_plugins(reg)

    pre_count = len(reg.pre_compactors) - 1  # exclude 'none'
    post_count = len(reg.post_compactors) - 1
    print(f"  Loaded {pre_count} pre-compactor(s), {post_count} post-compactor(s)\n")

    return reg


# Module-level singleton
REGISTRY = build_default_registry()
