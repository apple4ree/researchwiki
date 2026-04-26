"""S1 — Refactor invalidates wiki refs; full sync × lint × fix-stale cycle.

Verifies the cross-skill data flow from a code rename through the
remediation chain:

  src refactored → wiki-sync detects stale + rename heuristic
                 → wiki-lint reports stale finding past grace
                 → wiki-fix-stale resolves via researcher-approved edit
                 → frontmatter flag cleared
                 → re-sync re-flags (documented cycle: frontmatter symbol
                   field is preserved per SPEC; researcher must update it
                   separately if they want a clean re-sync)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from researchwiki.fixstale import run_fix_stale
from researchwiki.lint import run_lint
from researchwiki.sync import run_sync

from tests.integration._helpers import (
    ScriptedPrompt,
    add_src_file,
    add_wiki_page,
    bootstrap_workspace,
    silent_display,
)


def test_scenario_refactor_remediation(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/trainer.py",
                 "class Trainer:\n"
                 "    def train_one_epoch(self, x):\n"
                 "        return x\n")
    add_wiki_page(
        tmp_path, kind="concepts", slug="training-loop",
        refs_code=[
            {"path": "src/trainer.py", "symbol": "Trainer", "confidence": "verified"},
            {"path": "src/trainer.py", "symbol": "train_one_epoch", "confidence": "verified"},
        ],
        body="The Trainer class drives train_one_epoch.\n",
        created="2026-04-01", updated="2026-04-01",
    )

    # Phase 1: initial sync — no stale flags.
    r1 = run_sync(tmp_path, today=date(2026, 4, 1))
    assert r1.stale_flagged == 0
    assert r1.rename_candidates == []

    # Phase 2: refactor — train_one_epoch removed, replaced with train_step.
    add_src_file(tmp_path, "src/trainer.py",
                 "class Trainer:\n"
                 "    def train_step(self, x):\n"
                 "        return x\n")

    r2 = run_sync(tmp_path, today=date(2026, 4, 2))
    # Stale flag set on the train_one_epoch ref.
    assert r2.stale_flagged == 1
    assert r2.questions_appended == 1
    # Rename heuristic catches the close-by, similar-signature swap.
    assert len(r2.rename_candidates) >= 1
    rename = r2.rename_candidates[0]
    assert rename.removed.name == "train_one_epoch"
    assert rename.added.name == "train_step"
    assert rename.similarity > 0.80

    # Phase 3: same-day lint — stale ref too recent for Check 6 (< 7 days).
    lint_today = run_lint(tmp_path, today=date(2026, 4, 2))
    stale_findings = [f for f in lint_today.findings if f.category == "stale"]
    assert stale_findings == []

    # Phase 4: 9 days later — Check 6 fires.
    lint_later = run_lint(tmp_path, today=date(2026, 4, 11))
    stale_findings = [f for f in lint_later.findings if f.category == "stale"]
    assert len(stale_findings) >= 1
    assert "train_one_epoch" in stale_findings[0].message

    # Phase 5: researcher invokes fix-stale, replaces token.
    # The stale ref's `train_one_epoch` mention in body line:
    # "The Trainer class drives train_one_epoch." → wiki-fix-stale finds it.
    prompt = ScriptedPrompt(["y", "1", "train_step", "y"])
    fix_result = run_fix_stale(
        tmp_path, prompt_fn=prompt, display_fn=silent_display,
        today=date(2026, 4, 11),
    )
    assert fix_result.body_edits_applied == 1
    assert fix_result.stale_flags_cleared == 1
    assert fix_result.pages_fully_cleared == 1

    # Phase 6: body now reads "train_step"; flag cleared in frontmatter.
    page_text = (tmp_path / "wiki/concepts/training-loop.md").read_text(encoding="utf-8")
    body_section = page_text.split("---", 2)[2]
    assert "train_step" in body_section
    assert "train_one_epoch" not in body_section
    fm_section = page_text.split("---", 2)[1]
    assert "stale: true" not in fm_section

    # Phase 7: re-sync exposes the documented cycle.
    # Frontmatter still declares `symbol: train_one_epoch` (per SPEC — fix-stale
    # only edits body). The symbol is still missing from signatures.json, so
    # the next sync re-flags. Researcher must update the ref symbol manually
    # (or invoke wiki-log to file a superseding entry) to break the cycle.
    r3 = run_sync(tmp_path, today=date(2026, 4, 11))
    assert r3.stale_flagged == 1, (
        "Documented cycle: fix-stale clears the flag but does not update the "
        "frontmatter symbol; re-sync re-flags."
    )
    # questions.md should NOT get a duplicate entry — wiki-sync deduplicates
    # against pages that already had stale: true before the run.
    # However, since fix-stale cleared the flag, sync sees it as a fresh
    # detection and DOES append a new question. This is expected.
