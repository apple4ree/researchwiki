"""Integration test helpers.

`bootstrap_workspace` wraps the real `wiki-init` Python implementation
so the workspace setup matches what a researcher would actually have.
The `add_wiki_page` and `append_log_entry` helpers stand in for
`wiki-log` (which is not yet Python-coded) — they produce the same
*output shape* a wiki-log session would have, without exercising
wiki-log's conversational/judgmental flow.

This means integration tests cover the *cross-skill data contracts*
between the 7 code-implemented skills (init, sync, lint, deepscan,
query, recall, fix-stale). They do NOT exercise wiki-log's
speculation detection, noun-phrase extraction, or template
paraphrasing — that requires LLM and is tested separately (or via
manual smoke tests, when implemented).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import yaml

from researchwiki.init import run_init


# ---------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------


def bootstrap_workspace(tmp_path: Path, *, language: str = "ko",
                       today: date | None = None) -> Path:
    """Create a real ResearchWiki workspace via wiki-init. Returns the path."""
    today = today or date(2026, 4, 1)
    run_init(
        tmp_path,
        mode="new",
        language=language,
        deepscan_tool="understand-anything",
        prompt_fn=lambda _: "",
        display_fn=lambda _: None,
        auto_confirm=True,
        today=today,
    )
    return tmp_path


# ---------------------------------------------------------------------
# Source code
# ---------------------------------------------------------------------


def add_src_file(tmp_path: Path, rel_path: str, content: str) -> Path:
    """Create / overwrite a source file under the workspace."""
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# Wiki pages — substitute for wiki-log output
# ---------------------------------------------------------------------


def add_wiki_page(
    tmp_path: Path,
    *,
    kind: str,                            # "concepts" | "papers" | "experiments" | "decisions"
    slug: str,
    body: str = "Body content.",
    refs_code: list[dict] | None = None,
    refs_papers: list[str] | None = None,
    refs_concepts: list[str] | None = None,
    refs_experiments: list[str] | None = None,
    body_stale_mentions: list[dict] | None = None,
    authored_by: str = "human",
    seeded_by: str | None = None,
    created: str = "2026-01-01",
    updated: str = "2026-01-01",
    tags: list[str] | None = None,
    extra_fm: dict | None = None,
) -> Path:
    """Hand-author a wiki page.

    Substitutes for wiki-log's *output*. Frontmatter follows CLAUDE.md §5
    plus optional skill-added fields per the schema's optional-fields list.
    """
    page_type = "concept" if kind == "concepts" else kind.rstrip("s")
    fm = {
        "schema_version": 1,
        "type": page_type,
        "created": created,
        "updated": updated,
        "tags": tags or [],
        "refs": {
            "code": refs_code or [],
            "papers": refs_papers or [],
            "concepts": refs_concepts or [],
            "experiments": refs_experiments or [],
        },
        "authored_by": authored_by,
        "source_sessions": [],
    }
    if seeded_by:
        fm["seeded_by"] = seeded_by
    if body_stale_mentions:
        fm["body_stale_mentions"] = body_stale_mentions
    if extra_fm:
        fm.update(extra_fm)

    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    path = tmp_path / "wiki" / kind / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm_yaml}---\n\n{body}\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# Log entries — substitute for wiki-log's log.md append
# ---------------------------------------------------------------------


def append_log_entry(
    tmp_path: Path,
    *,
    when: date | datetime,
    type_: str,                          # "experiment" | "paper" | "decision" | "free"
    title: str,
    page_path: str,                       # repo-relative POSIX
    summary: str = "",
) -> None:
    """Append a researcher-activity entry (not skill-meta) to wiki/log.md."""
    log_md = tmp_path / "wiki" / "log.md"
    if isinstance(when, date) and not isinstance(when, datetime):
        timestamp = when.strftime("%Y-%m-%d 10:00")
    else:
        timestamp = when.strftime("%Y-%m-%d %H:%M")

    block = f"\n## [{timestamp}] log | {type_} | {title}\n"
    if summary:
        block += f"\n{summary}\n"
    block += f"\n→ {page_path}\n"

    existing = log_md.read_text(encoding="utf-8") if log_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    log_md.write_text(existing + block, encoding="utf-8")


def append_skill_meta_entry(
    tmp_path: Path,
    *,
    when: datetime,
    source: str,                          # "wiki-sync" | "wiki-lint" | "wiki-deepscan" | "wiki-fix-stale"
    body: str,
) -> None:
    """Append a skill-meta entry (`from <source>`). Used to verify that
    recall *filters these out* of the recent-activity corpus."""
    log_md = tmp_path / "wiki" / "log.md"
    timestamp = when.strftime("%Y-%m-%d %H:%M")
    block = f"\n## [{timestamp}] from {source}\n\n{body}\n"
    existing = log_md.read_text(encoding="utf-8") if log_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    log_md.write_text(existing + block, encoding="utf-8")


# ---------------------------------------------------------------------
# Frontmatter helpers (post-init field tweaks for tests)
# ---------------------------------------------------------------------


def set_page_created(tmp_path: Path, page_rel: str, *, created: str) -> None:
    """Override a page's `created:` frontmatter — used to test grace periods
    without parametrizing the underlying skill's `today`."""
    path = tmp_path / page_rel
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    fm = yaml.safe_load(parts[1])
    fm["created"] = created
    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{new_yaml}---{parts[2]}", encoding="utf-8")


# ---------------------------------------------------------------------
# Scripted prompt for fix-stale tests
# ---------------------------------------------------------------------


class ScriptedPrompt:
    """Replay a list of responses for `fix-stale` interactive prompts."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def __call__(self, message: str) -> str:
        self.calls.append(message)
        return self.responses.pop(0) if self.responses else ""


def silent_display(_msg: str) -> None:
    pass
