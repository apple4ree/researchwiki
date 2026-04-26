"""Tests for wiki-recall."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from researchwiki.recall import (
    RESEARCHER_VERBS,
    parse_log_entries,
    run_recall,
)


# ---------- log parser ----------


def test_parse_log_entries_classifies_verbs():
    text = (
        "## [2026-04-26 10:30] log | experiment | exp-001\n"
        "summary line\n"
        "→ wiki/experiments/exp-001.md\n"
        "\n"
        "## [2026-04-26 09:00] from wiki-sync\n"
        "stale ref note\n"
        "\n"
        "## [2026-04-25 14:00] amend | experiment | exp-001\n"
        "→ wiki/experiments/exp-001.md\n"
        "\n"
        "## [2026-04-20 12:00] from wiki-lint\n"
        "audit note\n"
    )
    entries = parse_log_entries(text)
    verbs = [e.verb for e in entries]
    assert verbs == ["log", "from", "amend", "from"]
    # Only researcher activity entries have a useful page_path.
    log_entry = entries[0]
    assert log_entry.page_path == "wiki/experiments/exp-001.md"
    assert log_entry.title == "exp-001"

    researcher_entries = [e for e in entries if e.verb in RESEARCHER_VERBS]
    assert len(researcher_entries) == 2


def test_parse_log_entries_handles_no_link():
    text = (
        "## [2026-04-26 10:30] log | free | one-liner\n"
        "Just a free-form note with no link.\n"
    )
    entries = parse_log_entries(text)
    assert len(entries) == 1
    assert entries[0].page_path is None


# ---------- end-to-end ----------


def _build_workspace(root: Path):
    wiki = root / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "papers").mkdir(parents=True)
    (wiki / "experiments").mkdir(parents=True)
    (wiki / "decisions").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "questions.md").write_text("", encoding="utf-8")
    (wiki / "discrepancies.md").write_text("", encoding="utf-8")
    (wiki / "index.md").write_text("", encoding="utf-8")


def _add_page(wiki: Path, sub: str, slug: str, *, updated: str, refs: dict, authored_by="human", seeded_by=None, body="Body."):
    p = wiki / sub / f"{slug}.md"
    fm = (
        "---\n"
        f"schema_version: 1\n"
        f"type: {sub.rstrip('s') if sub != 'concepts' else 'concept'}\n"
        f"created: 2026-01-01\n"
        f"updated: {updated}\n"
        "tags: []\n"
    )
    refs_block = ["refs:"]
    for kind in ("code", "papers", "concepts", "experiments"):
        items = refs.get(kind, [])
        if kind == "code":
            if items:
                refs_block.append("  code:")
                for it in items:
                    refs_block.append(f"    - path: {it['path']}")
                    refs_block.append(f"      symbol: {it['symbol']}")
                    refs_block.append(f"      confidence: {it.get('confidence', 'verified')}")
            else:
                refs_block.append("  code: []")
        else:
            if items:
                refs_block.append(f"  {kind}: [{', '.join(items)}]")
            else:
                refs_block.append(f"  {kind}: []")
    fm += "\n".join(refs_block) + "\n"
    fm += f"authored_by: {authored_by}\n"
    fm += "source_sessions: []\n"
    if seeded_by:
        fm += f"seeded_by: {seeded_by}\n"
    fm += "---\n\n"
    fm += body + "\n"
    p.write_text(fm, encoding="utf-8")


def test_recall_surfaces_stale_with_overlap(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    # Old page with refs that overlap with recent log activity.
    _add_page(wiki, "concepts", "auth-flow",
              updated="2026-01-12",
              refs={"code": [{"path": "src/trainer.py", "symbol": "Trainer"}],
                    "concepts": ["rotary"]})
    # Old page that does NOT overlap.
    _add_page(wiki, "concepts", "isolated",
              updated="2026-01-10",
              refs={"code": [{"path": "src/unrelated.py", "symbol": "Other"}]})

    # Recent log entry pointing to an experiment with refs.code: src/trainer.py:Trainer.
    _add_page(wiki, "experiments", "exp-recent",
              updated="2026-04-22",
              refs={"code": [{"path": "src/trainer.py", "symbol": "Trainer"}]})
    log_text = (
        "## [2026-04-22 10:00] log | experiment | exp-recent\n"
        "summary\n"
        "→ wiki/experiments/exp-recent.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26))
    paths = [r.page_path for r in result.results]
    assert "wiki/concepts/auth-flow.md" in paths
    assert "wiki/concepts/isolated.md" not in paths

    auth_result = next(r for r in result.results if r.page_path == "wiki/concepts/auth-flow.md")
    assert auth_result.score >= 2.0  # weight for code = 2.0
    assert any("src/trainer.py:Trainer" in line for line in auth_result.overlaps)


def test_recall_filters_skill_meta_log_entries(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    _add_page(wiki, "concepts", "old",
              updated="2026-01-10",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})
    _add_page(wiki, "experiments", "fake-recent",
              updated="2026-04-22",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})

    # Only a skill-meta entry references the experiment — should be filtered.
    log_text = (
        "## [2026-04-22 10:00] from wiki-sync\n"
        "Stale ref note about wiki/experiments/fake-recent.md.\n"
        "→ wiki/experiments/fake-recent.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26))
    # Skill-meta entries don't contribute to the recent corpus.
    assert result.log_entries_in_window == 0
    assert result.results == []


def test_recall_excludes_stubs_by_default(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    # Stub: seeded_by + minimal body
    _add_page(wiki, "concepts", "stub",
              updated="2026-01-10",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]},
              authored_by="llm",
              seeded_by="wiki-deepscan",
              body="*Stub.*")
    _add_page(wiki, "experiments", "exp",
              updated="2026-04-22",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})

    log_text = (
        "## [2026-04-22 10:00] log | experiment | exp\n"
        "→ wiki/experiments/exp.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26))
    paths = [r.page_path for r in result.results]
    assert "wiki/concepts/stub.md" not in paths

    # With include_stubs=True, the stub should appear.
    result2 = run_recall(tmp_path, today=date(2026, 4, 26), include_stubs=True)
    paths2 = [r.page_path for r in result2.results]
    assert "wiki/concepts/stub.md" in paths2


def test_recall_lookback_window(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    _add_page(wiki, "concepts", "old",
              updated="2026-01-10",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})
    _add_page(wiki, "experiments", "ancient",
              updated="2026-04-22",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})

    # Log entry from 60 days ago — outside the default 30-day lookback.
    log_text = (
        "## [2026-02-22 10:00] log | experiment | ancient\n"
        "→ wiki/experiments/ancient.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26))
    assert result.log_entries_in_window == 0
    assert result.results == []

    # With a 90-day lookback, it should appear.
    result2 = run_recall(tmp_path, today=date(2026, 4, 26), lookback_days=90)
    assert result2.log_entries_in_window == 1


def test_recall_stale_since_threshold(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    # Page updated recently — below the stale threshold.
    _add_page(wiki, "concepts", "fresh",
              updated="2026-04-20",  # 6 days ago
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})
    _add_page(wiki, "experiments", "exp",
              updated="2026-04-22",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})

    log_text = (
        "## [2026-04-22 10:00] log | experiment | exp\n"
        "→ wiki/experiments/exp.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26), stale_since_days=60)
    paths = [r.page_path for r in result.results]
    # `fresh` is 6 days old, well below stale_since=60 → should NOT appear.
    assert "wiki/concepts/fresh.md" not in paths


def test_recall_scope_filter(tmp_path: Path):
    _build_workspace(tmp_path)
    wiki = tmp_path / "wiki"

    _add_page(wiki, "concepts", "c1",
              updated="2026-01-10",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})
    _add_page(wiki, "decisions", "d1",
              updated="2026-01-10",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})
    _add_page(wiki, "experiments", "exp",
              updated="2026-04-22",
              refs={"code": [{"path": "src/x.py", "symbol": "Y"}]})

    log_text = (
        "## [2026-04-22 10:00] log | experiment | exp\n"
        "→ wiki/experiments/exp.md\n"
    )
    (wiki / "log.md").write_text(log_text, encoding="utf-8")

    result = run_recall(tmp_path, today=date(2026, 4, 26), scope="decisions")
    paths = [r.page_path for r in result.results]
    assert all(p.startswith("wiki/decisions/") for p in paths)


def test_recall_missing_log_md_raises(tmp_path: Path):
    _build_workspace(tmp_path)
    (tmp_path / "wiki" / "log.md").unlink()
    with pytest.raises(FileNotFoundError):
        run_recall(tmp_path, today=date(2026, 4, 26))


def test_recall_missing_wiki_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        run_recall(tmp_path, today=date(2026, 4, 26))
