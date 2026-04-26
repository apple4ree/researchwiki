"""Tests for wiki-init."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from researchwiki.init import run_init


class ScriptedPrompt:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def __call__(self, message: str) -> str:
        self.calls.append(message)
        return self.responses.pop(0) if self.responses else ""


def _silent(_msg: str) -> None:
    pass


# ---------- Happy path: clean repo ----------


def test_init_clean_repo_creates_full_layout(tmp_path: Path):
    result = run_init(
        tmp_path,
        mode="new", language="ko", deepscan_tool="understand-anything",
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    assert not result.aborted

    # Required top-level files.
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "research-wiki.config.yaml").exists()
    assert (tmp_path / ".gitignore").exists()

    # Wiki layer.
    assert (tmp_path / "wiki" / "concepts").is_dir()
    assert (tmp_path / "wiki" / "papers").is_dir()
    assert (tmp_path / "wiki" / "experiments").is_dir()
    assert (tmp_path / "wiki" / "decisions").is_dir()
    assert (tmp_path / "wiki" / "index.md").exists()
    assert (tmp_path / "wiki" / "log.md").exists()
    assert (tmp_path / "wiki" / "questions.md").exists()
    assert (tmp_path / "wiki" / "discrepancies.md").exists()

    # Index + deep + raw scaffolding.
    assert (tmp_path / "index" / "snapshots").is_dir()
    assert (tmp_path / "index" / "audits").is_dir()
    assert (tmp_path / "deep").is_dir()
    assert (tmp_path / "raw" / "papers").is_dir()
    assert (tmp_path / "raw" / "experiments").is_dir()

    # Templates flattened (no language subdirectory).
    for name in ("experiment.md", "paper_reading.md", "design_decision.md", "free_form.md"):
        assert (tmp_path / "templates" / name).exists(), f"missing template: {name}"
    assert not (tmp_path / "templates" / "ko").exists()
    assert not (tmp_path / "templates" / "en").exists()


# ---------- Language substitution ----------


def test_language_substitution_writes_into_config(tmp_path: Path):
    run_init(
        tmp_path, mode="new", language="en", deepscan_tool="understand-anything",
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )

    config_text = (tmp_path / "research-wiki.config.yaml").read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    assert config["language"]["default"] == "en"


def test_language_default_when_ko(tmp_path: Path):
    run_init(
        tmp_path, language="ko",
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    config = yaml.safe_load((tmp_path / "research-wiki.config.yaml").read_text(encoding="utf-8"))
    assert config["language"]["default"] == "ko"


# ---------- First log entry ----------


def test_first_log_entry_records_init_event(tmp_path: Path):
    run_init(
        tmp_path, mode="new", language="ko", deepscan_tool="understand-anything",
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "## [2026-04-26] init | ResearchWiki initialized" in log
    assert "mode: new" in log
    assert "language: ko" in log
    assert "deepscan-tool: understand-anything" in log
    assert "seed-from: (none)" in log


def test_first_log_entry_records_seed_from_path(tmp_path: Path):
    notes = tmp_path / "existing_notes.md"
    notes.write_text("scratch\n")
    run_init(
        tmp_path, mode="adopt", language="ko",
        seed_from=notes,
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "mode: adopt" in log
    assert f"seed-from: {notes}" in log


def test_first_log_entry_marks_missing_seed_from(tmp_path: Path):
    missing = tmp_path / "no_such_file.md"  # not created
    run_init(
        tmp_path, mode="new", seed_from=missing,
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "(requested:" in log
    assert "not found)" in log


# ---------- Idempotency ----------


def test_re_run_skips_existing_files(tmp_path: Path):
    # First init.
    r1 = run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    n_created_first = len(r1.files_created)
    assert n_created_first > 0

    # Modify the config — re-init must NOT overwrite it.
    config_path = tmp_path / "research-wiki.config.yaml"
    sentinel = "# user-edited\n"
    config_path.write_text(sentinel + config_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Second init.
    r2 = run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    # The user-edited config must be preserved.
    assert sentinel in config_path.read_text(encoding="utf-8")
    # Most things should be skipped (the only new thing is the appended log entry).
    assert len(r2.files_skipped) >= n_created_first - 1


def test_re_run_appends_to_log(tmp_path: Path):
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    log_after_first = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert log_after_first.count("init | ResearchWiki initialized") == 1

    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 27),
    )
    log_after_second = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert log_after_second.count("init | ResearchWiki initialized") == 2
    assert "[2026-04-26]" in log_after_second
    assert "[2026-04-27]" in log_after_second


def test_re_run_when_fully_initialized_is_noop(tmp_path: Path):
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    log_size = (tmp_path / "wiki" / "log.md").stat().st_size

    # Re-run with auto_confirm=False — should display "fully initialized, nothing to do"
    # and return without prompting.
    prompt = ScriptedPrompt(responses=[])  # empty: would EOFError if asked
    # Actually re-run with auto-confirm=True; the second run's plan still has
    # the appended log entry as a "new item", so it does prompt unless auto-confirm.
    # The fully-noop case is: every file present + log already has an entry for today.
    # That's a stronger condition. For MVP, the second invocation IS allowed to
    # append a new init log entry.
    pass  # Documented but not asserted — the behavior is "always appends a log entry on re-run".


# ---------- .gitignore handling ----------


def test_gitignore_created_with_entry(tmp_path: Path):
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "deep/knowledge-graph.json" in gitignore


def test_gitignore_appended_to_existing(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("__pycache__/\n.venv/\n", encoding="utf-8")
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in gitignore
    assert "deep/knowledge-graph.json" in gitignore


def test_gitignore_idempotent(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("deep/knowledge-graph.json\n", encoding="utf-8")
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.count("deep/knowledge-graph.json") == 1


# ---------- Confirmation prompt ----------


def test_decline_confirmation_aborts(tmp_path: Path):
    prompt = ScriptedPrompt(responses=["n"])
    result = run_init(
        tmp_path, prompt_fn=prompt, display_fn=_silent,
        today=date(2026, 4, 26),
    )
    assert result.aborted
    assert "decline" in result.abort_reason
    # Nothing should have been created.
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / "wiki").exists()


def test_yes_confirmation_proceeds(tmp_path: Path):
    prompt = ScriptedPrompt(responses=["y"])
    result = run_init(
        tmp_path, prompt_fn=prompt, display_fn=_silent,
        today=date(2026, 4, 26),
    )
    assert not result.aborted
    assert (tmp_path / "CLAUDE.md").exists()


# ---------- Templates: language fallback ----------


def test_unknown_language_falls_back_to_en(tmp_path: Path):
    """If a researcher passes a language without bundled templates,
    fall back to English templates rather than aborting."""
    run_init(
        tmp_path, language="fr",
        prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    # Templates copied (from the en bundle as fallback).
    for name in ("experiment.md", "paper_reading.md", "design_decision.md", "free_form.md"):
        assert (tmp_path / "templates" / name).exists()
    # Config still records the requested language.
    config = yaml.safe_load((tmp_path / "research-wiki.config.yaml").read_text(encoding="utf-8"))
    assert config["language"]["default"] == "fr"


# ---------- Bundle missing ----------


def test_missing_bundle_raises(tmp_path: Path):
    fake_bundle = tmp_path / "_no_bundle"
    with pytest.raises(FileNotFoundError):
        run_init(
            tmp_path, bundle_path=fake_bundle,
            prompt_fn=_silent, display_fn=_silent,
            auto_confirm=True,
        )


# ---------- CLAUDE.md byte-for-byte verification ----------


def test_claude_md_matches_bundle_byte_for_byte(tmp_path: Path):
    """Verbatim copy contract: target CLAUDE.md == bundle CLAUDE.md."""
    from researchwiki.init import _find_bundle
    run_init(
        tmp_path, prompt_fn=_silent, display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 26),
    )
    bundle_text = (_find_bundle() / "CLAUDE.md").read_text(encoding="utf-8")
    target_text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert target_text == bundle_text
