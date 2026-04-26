"""P1 — wiki-recall ignores skill-meta log entries.

`wiki-sync`, `wiki-lint`, `wiki-deepscan`, and `wiki-fix-stale` all
append to `wiki/log.md` with headers like `## [...] from <skill>`.
These describe wiki-meta events, not researcher activity, and must
NOT appear in the recall skill's recent-activity corpus — otherwise
the wiki's own automation would drive recall scoring.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from researchwiki.recall import run_recall

from tests.integration._helpers import (
    add_src_file,
    add_wiki_page,
    append_skill_meta_entry,
    bootstrap_workspace,
)


def test_pair_recall_filters_skill_meta_log_entries(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/x.py", "class Y:\n    pass\n")

    # Old page that *would* match if a recent log entry mentioned it.
    add_wiki_page(
        tmp_path, kind="concepts", slug="old-page",
        refs_code=[{"path": "src/x.py", "symbol": "Y", "confidence": "verified"}],
        body="Old.", created="2026-01-10", updated="2026-01-10",
    )
    # A "recent" experiment that shares refs with the old page.
    add_wiki_page(
        tmp_path, kind="experiments", slug="recent-but-meta-only",
        refs_code=[{"path": "src/x.py", "symbol": "Y", "confidence": "verified"}],
        body="Recent.", created="2026-04-22", updated="2026-04-22",
    )

    # ONLY a skill-meta entry references the recent experiment — should be
    # filtered out of the recent-activity corpus.
    append_skill_meta_entry(
        tmp_path,
        when=datetime(2026, 4, 22, 10, 0),
        source="wiki-sync",
        body=("**Stale ref:** wiki/experiments/recent-but-meta-only.md still references "
              "src/x.py:Y, which no longer exists in the index.\n\n"
              "→ wiki/experiments/recent-but-meta-only.md\n"),
    )

    result = run_recall(tmp_path, today=date(2026, 4, 26), lookback_days=30)
    # Recall should treat the corpus as empty — only skill-meta entries exist.
    assert result.log_entries_in_window == 0
    assert result.results == [], (
        "Skill-meta log entries should not contribute to the recall corpus."
    )
