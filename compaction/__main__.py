"""CLI tool for scaffolding new compactor plugins.

Usage:
    uv run python -m compaction scaffold pre "LLMLingua-2" llmlingua
    uv run python -m compaction scaffold post "MyCompressor" my-package

This generates a template file in plugins/ with TODOs showing exactly
what to fill in.
"""

import sys
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"

PRE_TEMPLATE = '''"""{name} — pre-compaction plugin.

Install: uv add {package}
Repo:    {url}
"""

from compaction.registry import PreCompactor
from compaction.logger import StageMetrics, Timer


class {class_name}(PreCompactor):

    name = "{name}"
    description = "TODO: one-sentence description"
    url = "{url}"

    _model = None

    def compact(self, query: str, context: str, threshold: float = 0.1):
        # TODO: Import and call your compaction library here.
        #
        # Example — adapt this to your repo's API:
        #
        #   from some_library import Compressor
        #   if self._model is None:
        #       self._model = Compressor(model="some-model")
        #   result = self._model.compress(text=context, query=query, rate=threshold)
        #   pruned = result.compressed_text
        #
        # The `threshold` parameter (0.01 to 0.50) controls aggressiveness.
        # Map it to whatever your repo uses (rate, ratio, top_k, etc.)

        tokens_in = max(1, len(context) // 4)

        with Timer() as t:
            # ── TODO: Replace this block ──────────────────────────
            pruned = context  # <-- replace with your compaction call
            # ─────────────────────────────────────────────────────

        tokens_out = max(1, len(pruned) // 4)

        return pruned, StageMetrics(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            chars_in=len(context),
            chars_out=len(pruned),
            compression_ratio=1 - len(pruned) / max(1, len(context)),
            latency_ms=t.elapsed_ms,
            extra={{}},  # add any repo-specific metadata here
        )

    def warm_up(self):
        """Optional: pre-load models so the first call isn't slow."""
        pass  # TODO: load your model here if needed
'''

POST_TEMPLATE = '''"""{name} — post-compaction plugin.

Install: uv add {package}
Repo:    {url}
"""

from compaction.registry import PostCompactor
from compaction.logger import StageMetrics, Timer


class {class_name}(PostCompactor):

    name = "{name}"
    description = "TODO: one-sentence description"
    url = "{url}"

    def compact(self, messages: list[dict], model: str = ""):
        # `messages` is a list of OpenAI-format dicts:
        #   [{{"role": "system", "content": "..."}},
        #    {{"role": "user", "content": "..."}},
        #    {{"role": "assistant", "content": "..."}}]
        #
        # TODO: Import and call your compression library here.
        #
        # Example:
        #   from some_library import compress
        #   result = compress(messages)
        #   compressed = result.messages
        #
        # Return the compressed messages in the same format.

        chars_in = sum(len(m.get("content", "") or "") for m in messages)

        with Timer() as t:
            # ── TODO: Replace this block ──────────────────────────
            compressed = messages  # <-- replace with your compression call
            # ─────────────────────────────────────────────────────

        chars_out = sum(len(m.get("content", "") or "") for m in compressed)

        return compressed, StageMetrics(
            tokens_in=max(1, chars_in // 4),
            tokens_out=max(1, chars_out // 4),
            chars_in=chars_in,
            chars_out=chars_out,
            compression_ratio=1 - chars_out / max(1, chars_in),
            latency_ms=t.elapsed_ms,
            extra={{}},  # add any repo-specific metadata here
        )
'''


def scaffold(kind: str, name: str, package: str, url: str = ""):
    """Generate a plugin template file."""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{kind}_{safe_name}.py"
    filepath = PLUGINS_DIR / filename

    if filepath.exists():
        print(f"⚠️  {filepath} already exists. Delete it first or pick a different name.")
        return

    class_name = "".join(word.capitalize() for word in name.replace("-", " ").split())
    if kind == "pre":
        class_name += "PreCompactor"
        template = PRE_TEMPLATE
    else:
        class_name += "PostCompactor"
        template = POST_TEMPLATE

    content = template.format(
        name=name,
        package=package,
        url=url or f"https://github.com/.../{package}",
        class_name=class_name,
    )

    filepath.write_text(content)

    print(f"""
✅ Created {filepath}

Next steps:
  1. Install the package:   uv add {package}
  2. Edit {filename} — fill in the TODO sections (~5 lines)
  3. Restart dashboard:     uv run python app.py

Your tool will appear in the dropdown automatically.
""")


def list_plugins():
    """Show all discovered plugin files."""
    if not PLUGINS_DIR.exists():
        print("No plugins directory found.")
        return

    files = sorted(PLUGINS_DIR.glob("*.py"))
    if not files:
        print("No plugin files found in plugins/")
        return

    print(f"\nPlugin files in {PLUGINS_DIR}:\n")
    for f in files:
        kind = "pre" if f.name.startswith("pre_") else "post" if f.name.startswith("post_") else "???"
        print(f"  [{kind:>4}] {f.name}")


def remove_plugin(name: str):
    """Remove a plugin file by tool name or filename."""
    if not PLUGINS_DIR.exists():
        print("No plugins directory found.")
        return

    for f in PLUGINS_DIR.glob("*.py"):
        if f.stem == name or name in f.stem:
            f.unlink()
            print(f"✅ Removed {f.name}")
            print(f"   Restart the dashboard to apply: uv run python app.py")
            return

    print(f"No plugin matching '{name}' found.")


USAGE = """
LLM Compaction Benchmarking Tool — Plugin Manager

Commands:
  scaffold pre  "Name" package    Create a pre-compactor plugin template
  scaffold post "Name" package    Create a post-compactor plugin template
  list                            Show all plugin files
  remove <name>                   Remove a plugin file

Examples:
  uv run python -m compaction scaffold pre "LLMLingua-2" llmlingua
  uv run python -m compaction scaffold post "TextCompressor" text-compressor
  uv run python -m compaction list
  uv run python -m compaction remove llmlingua
"""


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return

    cmd = args[0]

    if cmd == "scaffold" and len(args) >= 4:
        kind = args[1]
        if kind not in ("pre", "post"):
            print(f"Unknown type '{kind}'. Use 'pre' or 'post'.")
            return
        name = args[2]
        package = args[3]
        url = args[4] if len(args) > 4 else ""
        scaffold(kind, name, package, url)

    elif cmd == "list":
        list_plugins()

    elif cmd == "remove" and len(args) >= 2:
        remove_plugin(args[1])

    else:
        print(USAGE)


if __name__ == "__main__":
    main()
