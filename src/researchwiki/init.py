"""wiki-init — bootstrap a repository into a ResearchWiki workspace.

Copies the bundle (`skills/wiki-init/reference/bundle/`) into the target
repo: `CLAUDE.md` + `research-wiki.config.yaml` (with `language.default`
substituted per `--language`) + 4 templates (flattened from
`templates/<lang>/`). Creates the directory scaffolding and the four
seed wiki meta files. Appends a first log entry recording the init
event itself.

P3·P8 — wiki-init does NOT analyze existing code, papers, or notes.
Seed pages are structural scaffolding only.

Idempotent: never overwrites existing files; on re-run, only missing
items are created.

The interactive confirmation prompt is dependency-injected via
`prompt_fn` so tests can script responses without monkey-patching
`input()`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Literal

PromptFn = Callable[[str], str]
DisplayFn = Callable[[str], None]

DEFAULT_PROMPT_FN: PromptFn = input


def _default_display(message: str) -> None:
    print(message)


# ---------------------------------------------------------------------
# Spec — what wiki-init creates.
# ---------------------------------------------------------------------

DIRECTORIES = (
    "wiki/concepts",
    "wiki/papers",
    "wiki/experiments",
    "wiki/decisions",
    "index/snapshots",
    "index/audits",
    "deep",
    "raw/papers",
    "raw/experiments",
    "templates",
)

# Files generated from scratch (no bundle source).
SEED_WIKI_META = {
    "wiki/index.md": "# wiki/index.md\n\nContent catalog. wiki-log adds entries here as they are created.\n",
    "wiki/questions.md": "# wiki/questions.md\n\nOpen questions (LLM-appended; researcher resolves).\n",
    "wiki/discrepancies.md": "# wiki/discrepancies.md\n\nUnresolved cross-page contradictions surfaced by wiki-lint / wiki-deepscan.\n",
}

# Templates that the bundle ships under `templates/<lang>/`. Flattened to
# `templates/<name>.md` in the target.
TEMPLATE_NAMES = (
    "experiment.md",
    "paper_reading.md",
    "design_decision.md",
    "free_form.md",
)


# ---------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------


@dataclass
class InitResult:
    target: Path
    files_created: list[Path] = field(default_factory=list)
    directories_created: list[Path] = field(default_factory=list)
    files_skipped: list[Path] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------


def run_init(
    target: Path,
    *,
    mode: Literal["new", "adopt"] = "new",
    language: str = "ko",
    deepscan_tool: str = "understand-anything",
    seed_from: Path | None = None,
    bundle_path: Path | None = None,
    prompt_fn: PromptFn = DEFAULT_PROMPT_FN,
    display_fn: DisplayFn = _default_display,
    today: date | None = None,
    auto_confirm: bool = False,
) -> InitResult:
    """Bootstrap `target` into a ResearchWiki workspace.

    Returns an `InitResult` describing what was created/skipped.

    Idempotent — re-invocation against an already-initialized repo
    creates only the missing items and reports the rest as skipped.

    `auto_confirm=True` skips the y/N prompt (useful for tests and
    programmatic invocation; CLI default is False).
    """
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    bundle = bundle_path or _find_bundle()
    if not bundle.is_dir():
        raise FileNotFoundError(
            f"wiki-init bundle not found at {bundle}. "
            f"Pass `bundle_path=...` or set the path manually."
        )

    today = today or datetime.now().date()
    result = InitResult(target=target)

    # Compute the set of items to create vs skip.
    plan = _build_plan(target, bundle=bundle, language=language)

    if not plan["new_items"]:
        display_fn(
            "wiki-init: target is already fully initialized. "
            "Nothing to do."
        )
        return result

    # Show proposed layout + ask confirmation.
    layout_text = _render_proposed_layout(plan, target=target)
    display_fn(layout_text)

    if not auto_confirm:
        response = prompt_fn("Proceed? [y/N]").strip().lower()
        if response not in ("y", "yes"):
            result.aborted = True
            result.abort_reason = "researcher declined confirmation"
            return result

    # Create directories.
    for rel_dir in plan["new_directories"]:
        path = target / rel_dir
        path.mkdir(parents=True, exist_ok=True)
        result.directories_created.append(path)

    # Copy bundle assets (CLAUDE.md, config, templates).
    for src, dst, transform in plan["bundle_copies"]:
        if dst.exists():
            result.files_skipped.append(dst)
            continue
        text = src.read_text(encoding="utf-8")
        if transform is not None:
            text = transform(text)
        dst.write_text(text, encoding="utf-8")
        result.files_created.append(dst)

    # Generate seed wiki meta files (only those missing).
    for rel, content in SEED_WIKI_META.items():
        path = target / rel
        if path.exists():
            result.files_skipped.append(path)
            continue
        path.write_text(content, encoding="utf-8")
        result.files_created.append(path)

    # First log entry — append (or create with the entry as content).
    log_md = target / "wiki" / "log.md"
    _write_first_log_entry(
        log_md,
        mode=mode,
        language=language,
        deepscan_tool=deepscan_tool,
        seed_from=seed_from,
        today=today,
    )
    if log_md not in result.files_created and log_md not in result.files_skipped:
        result.files_created.append(log_md)

    # .gitignore handling.
    _ensure_gitignore(target / ".gitignore", entry="deep/knowledge-graph.json")

    # Show next-steps summary.
    display_fn(
        f"\n✓ Created {len(result.files_created)} file(s), "
        f"{len(result.directories_created)} directory(ies); "
        f"skipped {len(result.files_skipped)} pre-existing file(s).\n"
        f"\nNext steps:\n"
        f"  1. wiki sync       — generate the first Index Layer snapshot.\n"
        f"  2. wiki deepscan   — (optional, requires Understand-Anything) refresh the deep layer.\n"
        f"  3. wiki log ...    — record experiments, paper readings, decisions, notes."
    )
    return result


# ---------------------------------------------------------------------
# Plan computation
# ---------------------------------------------------------------------


def _build_plan(target: Path, *, bundle: Path, language: str) -> dict:
    """Walk the would-be outputs; partition into new vs already-existing.

    Returns:
        {
            "new_items": list[str]         — relative paths to create
            "existing_items": list[str]    — relative paths already present
            "new_directories": list[str]   — directories to create
            "bundle_copies": list[(src, dst, transform_fn|None)]
        }
    """
    new_items: list[str] = []
    existing_items: list[str] = []
    new_directories: list[str] = []

    # Directories.
    for d in DIRECTORIES:
        if not (target / d).exists():
            new_directories.append(d)

    # Bundle copies.
    bundle_copies: list[tuple[Path, Path, Callable | None]] = []

    constitution_src = bundle / "CLAUDE.md"
    constitution_dst = target / "CLAUDE.md"
    bundle_copies.append((constitution_src, constitution_dst, None))

    config_src = bundle / "research-wiki.config.yaml"
    config_dst = target / "research-wiki.config.yaml"

    def _substitute_language(text: str) -> str:
        # The bundle's reference config carries `default: ko` baked in.
        # Substitute per the requested language.
        return text.replace("default: ko", f"default: {language}")

    bundle_copies.append((config_src, config_dst, _substitute_language))

    # Templates: flattened from bundle/templates/<lang>/<name>.md →
    # target/templates/<name>.md.
    templates_lang_dir = bundle / "templates" / language
    if not templates_lang_dir.is_dir():
        # Fallback to en if requested language not bundled.
        templates_lang_dir = bundle / "templates" / "en"
    for name in TEMPLATE_NAMES:
        src = templates_lang_dir / name
        dst = target / "templates" / name
        bundle_copies.append((src, dst, None))

    # Track which planned files are new vs existing.
    for src, dst, _t in bundle_copies:
        rel = dst.relative_to(target).as_posix()
        if dst.exists():
            existing_items.append(rel)
        else:
            new_items.append(rel)

    for rel in SEED_WIKI_META:
        if (target / rel).exists():
            existing_items.append(rel)
        else:
            new_items.append(rel)

    # First log entry — always appended (idempotent: appends to existing
    # wiki/log.md if present, creates with content if not). Treated as
    # always-new for planning purposes only when log.md is missing.
    if not (target / "wiki" / "log.md").exists():
        new_items.append("wiki/log.md (first init log entry)")
    else:
        new_items.append("wiki/log.md (append init log entry)")

    return {
        "new_items": new_items,
        "existing_items": existing_items,
        "new_directories": new_directories,
        "bundle_copies": bundle_copies,
    }


def _render_proposed_layout(plan: dict, *, target: Path) -> str:
    lines = [
        f"\nwiki-init: proposed layout under {target}/:\n",
    ]
    for d in plan["new_directories"]:
        lines.append(f"  + {d}/")
    for item in plan["new_items"]:
        lines.append(f"  + {item}")
    if plan["existing_items"]:
        lines.append("\nAlready present (will not overwrite):")
        for e in plan["existing_items"]:
            lines.append(f"  - {e}")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# First log entry
# ---------------------------------------------------------------------


def _write_first_log_entry(
    log_md: Path,
    *,
    mode: str,
    language: str,
    deepscan_tool: str,
    seed_from: Path | None,
    today: date,
) -> None:
    seed_str = (
        str(seed_from) if (seed_from is not None and seed_from.exists())
        else f"(requested: {seed_from}, not found)" if seed_from is not None
        else "(none)"
    )
    entry = (
        f"\n## [{today.isoformat()}] init | ResearchWiki initialized\n"
        f"\n"
        f"- mode: {mode}\n"
        f"- language: {language}\n"
        f"- deepscan-tool: {deepscan_tool}\n"
        f"- seed-from: {seed_str}\n"
    )

    log_md.parent.mkdir(parents=True, exist_ok=True)
    if log_md.exists():
        existing = log_md.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
        log_md.write_text(existing + entry, encoding="utf-8")
    else:
        log_md.write_text(
            "# wiki/log.md\n\nAppend-only research journal. wiki-log writes here.\n"
            + entry,
            encoding="utf-8",
        )


# ---------------------------------------------------------------------
# .gitignore handling
# ---------------------------------------------------------------------


def _ensure_gitignore(gitignore: Path, *, entry: str) -> None:
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        if entry in existing.splitlines():
            return
        if existing and not existing.endswith("\n"):
            existing += "\n"
        gitignore.write_text(existing + entry + "\n", encoding="utf-8")
    else:
        gitignore.write_text(
            f"# Added by wiki-init.\n{entry}\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------
# Bundle location
# ---------------------------------------------------------------------


def _find_bundle() -> Path:
    """Locate the wiki-init bundle.

    Resolution order (first existing match wins):

      1. `RESEARCHWIKI_BUNDLE` env override — explicit user/test override.
      2. `CLAUDE_PLUGIN_ROOT` env (set by Claude Code when a plugin is
         active) → `<root>/skills/wiki-init/reference/bundle/`.
      3. Source-relative walk up from this module — works for
         `pip install -e .` (editable) and any layout where
         `skills/wiki-init/reference/bundle/` lives as a sibling of
         `src/researchwiki/`.
      4. Packaged bundle next to this module (`<package>/_bundle/`) —
         the canonical location for wheel installs (`pip install
         researchwiki`). Kept in byte-sync with the source-tree bundle
         via `tests/test_bundle_sync.py`.

    Returns the first option that resolves to an existing directory; if
    none do, returns the source-relative path so the caller can produce
    a meaningful error message naming the expected location.
    """
    import os

    override = os.environ.get("RESEARCHWIKI_BUNDLE")
    if override:
        return Path(override)

    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = Path(plugin_root) / "skills" / "wiki-init" / "reference" / "bundle"
        if candidate.is_dir():
            return candidate

    here = Path(__file__).resolve()
    # here = .../<repo>/src/researchwiki/init.py
    source_relative = here.parent.parent.parent / "skills" / "wiki-init" / "reference" / "bundle"
    if source_relative.is_dir():
        return source_relative

    packaged = here.parent / "_bundle"
    if packaged.is_dir():
        return packaged

    # Nothing found — return the source-relative path so the caller's
    # FileNotFoundError carries a reasonable hint.
    return source_relative
