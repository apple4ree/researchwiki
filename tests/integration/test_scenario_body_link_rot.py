"""S4 — wiki-sync --scan-body produces body_stale_mentions; wiki-fix-stale
walks them and applies researcher-approved edits.

Verifies the data flow:
  sync --scan-body  →  frontmatter `body_stale_mentions: [...]`
                    →  fix-stale walks each mention as an occurrence
                    →  body modified per researcher choice
                    →  re-sync no longer detects the resolved mentions
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from researchwiki.fixstale import run_fix_stale
from researchwiki.sync import run_sync

from tests.integration._helpers import (
    ScriptedPrompt,
    add_src_file,
    add_wiki_page,
    bootstrap_workspace,
    silent_display,
)


def test_scenario_body_link_rot_round_trip(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    # Only RealClass exists in code.
    add_src_file(tmp_path, "src/x.py", "class RealClass:\n    pass\n")

    # Wiki page mentions both real and removed symbols (no frontmatter refs;
    # this exercises the body-link-rot path explicitly).
    add_wiki_page(
        tmp_path, kind="concepts", slug="training",
        refs_code=[],
        body=("# Training\n\n"
              "We use RealClass and OldRemovedClass for the experiment.\n"),
        created="2026-04-01", updated="2026-04-01",
    )

    # Phase 1: sync --scan-body — records body_stale_mentions.
    r1 = run_sync(tmp_path, scan_body=True, today=date(2026, 4, 1))
    assert r1.body_mentions_recorded >= 1
    assert r1.pages_with_body_mentions == 1

    page_text = (tmp_path / "wiki/concepts/training.md").read_text(encoding="utf-8")
    fm_yaml = page_text.split("---", 2)[1]
    fm = yaml.safe_load(fm_yaml)
    tokens = {m["token"] for m in fm.get("body_stale_mentions", [])}
    assert "OldRemovedClass" in tokens
    # RealClass should NOT be flagged.
    assert "RealClass" not in tokens

    # Phase 2: fix-stale — replace OldRemovedClass with NewClass.
    prompt = ScriptedPrompt([
        "y",            # continue
        "1",            # action: replace
        "NewClass",     # new symbol name
        "y",            # apply
    ])
    fix_result = run_fix_stale(
        tmp_path, prompt_fn=prompt, display_fn=silent_display,
        today=date(2026, 4, 1),
    )
    assert fix_result.body_edits_applied == 1

    # Body should now contain NewClass; OldRemovedClass should be gone (from body).
    page_text2 = (tmp_path / "wiki/concepts/training.md").read_text(encoding="utf-8")
    body2 = page_text2.split("---", 2)[2]
    assert "NewClass" in body2
    assert "OldRemovedClass" not in body2

    # Phase 3: re-sync --scan-body — OldRemovedClass no longer in body, so
    # no longer reported. NewClass also missing from src, so might be reported
    # — depends on whether the regex catches it (single-cap PascalCase).
    # NewClass is multi-cap (N+C), so YES regex catches it.
    r2 = run_sync(tmp_path, scan_body=True, today=date(2026, 4, 1))
    fm_after = yaml.safe_load(
        (tmp_path / "wiki/concepts/training.md").read_text(encoding="utf-8").split("---", 2)[1]
    )
    tokens_after = {m["token"] for m in fm_after.get("body_stale_mentions", [])}
    # OldRemovedClass is resolved (no longer in body) → not in mentions.
    assert "OldRemovedClass" not in tokens_after
    # NewClass is the replacement researcher chose; if it's not in src, it WILL
    # appear as a new heuristic mention. The researcher would address this in
    # the next fix-stale session (or, more typically, by updating src to add it).
