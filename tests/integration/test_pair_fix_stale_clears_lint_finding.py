"""P2 — wiki-fix-stale clears the same `stale` finding wiki-lint reports.

Both skills read the same frontmatter `stale: true` flag set by
wiki-sync. After wiki-fix-stale resolves the page (with auto-clear-flags
on), wiki-lint should no longer report a `stale` finding for that page.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from researchwiki.fixstale import run_fix_stale
from researchwiki.lint import run_lint

from tests.integration._helpers import (
    ScriptedPrompt,
    add_src_file,
    add_wiki_page,
    bootstrap_workspace,
    silent_display,
)


def test_pair_fix_stale_clears_what_lint_reported(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/x.py", "class Real:\n    pass\n")

    add_wiki_page(
        tmp_path, kind="concepts", slug="p",
        refs_code=[{
            "path": "src/x.py",
            "symbol": "Gone",
            "confidence": "verified",
            "stale": True,
            "stale_detected": "2026-04-01",
        }],
        body="The Gone symbol is mentioned here.",
        created="2026-04-01", updated="2026-04-01",
    )

    # Lint at day 26 → 25 days past stale_detected → Check 6 fires.
    lint_before = run_lint(tmp_path, today=date(2026, 4, 26))
    stale_findings_before = [f for f in lint_before.findings if f.category == "stale"]
    assert len(stale_findings_before) >= 1
    assert "Gone" in stale_findings_before[0].message

    # fix-stale: wrap-deprecated (option 2 — non-destructive, preserves text).
    prompt = ScriptedPrompt(["y", "2", "y"])
    fix_result = run_fix_stale(
        tmp_path, prompt_fn=prompt, display_fn=silent_display,
        today=date(2026, 4, 26),
    )
    assert fix_result.body_edits_applied == 1
    assert fix_result.stale_flags_cleared == 1

    # Lint again: same finding should be gone.
    lint_after = run_lint(tmp_path, today=date(2026, 4, 26))
    stale_findings_after = [f for f in lint_after.findings if f.category == "stale"]
    assert stale_findings_after == [], (
        "After fix-stale clears the flag, lint Check 6 should no longer report it."
    )
