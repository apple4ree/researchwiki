"""Tests for wiki-sync's optional --scan-body body link rot pass."""

from __future__ import annotations

from pathlib import Path

import yaml

from researchwiki.sync import _scan_body_for_stale_tokens, run_sync


def test_scan_body_finds_pascalcase_unknowns():
    body = (
        "The Trainer class uses RotaryEmbedding internally.\n"
        "We compared against OldAttention as baseline.\n"
    )
    known = {"Trainer", "RotaryEmbedding"}
    mentions = _scan_body_for_stale_tokens(body, known, "2026-04-26")
    tokens = {m["token"] for m in mentions}
    assert "OldAttention" in tokens
    assert "Trainer" not in tokens
    assert "RotaryEmbedding" not in tokens


def test_scan_body_finds_snake_case_with_paren():
    body = "Call train_one_epoch() then save_checkpoint()."
    known: set[str] = set()
    mentions = _scan_body_for_stale_tokens(body, known, "2026-04-26")
    tokens = {m["token"] for m in mentions}
    assert "train_one_epoch" in tokens
    assert "save_checkpoint" in tokens


def test_scan_body_skips_code_fences():
    body = (
        "Real prose mentions OldAttention.\n"
        "\n"
        "```\n"
        "OldAttention is inside a code fence — should be skipped.\n"
        "```\n"
        "\n"
        "More prose: AnotherUnknown is outside.\n"
    )
    mentions = _scan_body_for_stale_tokens(body, set(), "2026-04-26")
    tokens = [(m["line"], m["token"]) for m in mentions]
    # Line 1 has OldAttention (real prose)
    assert (1, "OldAttention") in tokens
    # Line 7 has AnotherUnknown (real prose)
    assert (7, "AnotherUnknown") in tokens
    # Line 4 (inside fence) should NOT be in mentions
    assert not any(line == 4 for line, _t in tokens)


def test_scan_body_dotted_form_recognized():
    body = "We benchmarked Trainer.train_one_epoch against the baseline.\n"
    # If Trainer.train_one_epoch is in symbols, the dotted token should not be flagged.
    known = {"Trainer.train_one_epoch", "Trainer"}
    mentions = _scan_body_for_stale_tokens(body, known, "2026-04-26")
    assert mentions == []


def test_scan_body_dotted_falls_back_to_last_component():
    body = "Use Trainer.save_checkpoint to persist.\n"
    # save_checkpoint is in known names (without parent prefix).
    known = {"Trainer", "save_checkpoint"}
    mentions = _scan_body_for_stale_tokens(body, known, "2026-04-26")
    assert mentions == []


def test_run_sync_scan_body_writes_frontmatter(tmp_path: Path):
    # Build minimal repo with one wiki page that has body mentions.
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    (tmp_path / "research-wiki.config.yaml").write_text("schema_version: 1\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("class Trainer: ...\n")
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "training.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code: []\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "\n"
        "We use Trainer (real) and OldAttention (gone).\n",
        encoding="utf-8",
    )
    for name in ("log.md", "questions.md", "discrepancies.md", "index.md"):
        (wiki / name).write_text("\n", encoding="utf-8")

    result = run_sync(tmp_path, scan_body=True)
    assert result.body_mentions_recorded >= 1

    # body_stale_mentions should be in frontmatter now.
    page_text = (wiki / "concepts" / "training.md").read_text(encoding="utf-8")
    assert "body_stale_mentions" in page_text
    fm_yaml = page_text.split("---", 2)[1]
    fm_data = yaml.safe_load(fm_yaml)
    tokens = [m["token"] for m in fm_data["body_stale_mentions"]]
    assert "OldAttention" in tokens
    assert "Trainer" not in tokens

    # Body must be untouched.
    assert "We use Trainer (real) and OldAttention (gone)." in page_text


def test_run_sync_scan_body_idempotent(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("class Known: ...\n")
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "p.md").write_text(
        "---\nschema_version: 1\ntype: concept\ntags: []\n"
        "refs: {code: [], papers: [], concepts: [], experiments: []}\n"
        "authored_by: human\nsource_sessions: []\n---\n"
        "Mentions UnknownThing in body.\n",
        encoding="utf-8",
    )
    for name in ("log.md", "questions.md", "discrepancies.md", "index.md"):
        (wiki / name).write_text("\n", encoding="utf-8")

    run_sync(tmp_path, scan_body=True)
    text_after_first = (wiki / "concepts" / "p.md").read_text(encoding="utf-8")
    run_sync(tmp_path, scan_body=True)
    text_after_second = (wiki / "concepts" / "p.md").read_text(encoding="utf-8")
    assert text_after_first == text_after_second
