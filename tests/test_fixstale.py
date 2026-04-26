"""Tests for wiki-fix-stale.

The interactive prompt is dependency-injected, so tests construct a
scripted prompt that returns canned responses in order.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from researchwiki.fixstale import run_fix_stale


class ScriptedPrompt:
    """Test helper: replays a list of responses in order. Records the
    sequence of prompt messages for assertions."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def __call__(self, message: str) -> str:
        self.calls.append(message)
        if not self.responses:
            return ""
        return self.responses.pop(0)


def _silent_display(_message: str) -> None:
    """Drop informational output during tests."""


def _build_workspace(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    (tmp_path / "research-wiki.config.yaml").write_text("schema_version: 1\n")
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True, exist_ok=True)
    for name in ("log.md", "questions.md", "discrepancies.md", "index.md"):
        (wiki / name).write_text("\n", encoding="utf-8")


def _add_stale_page(
    tmp_path: Path,
    *,
    slug: str,
    body_lines: list[str],
    stale_refs: list[dict],  # [{path, symbol, stale_detected}, ...]
    body_stale_mentions: list[dict] | None = None,
) -> Path:
    """Write a wiki page at wiki/concepts/<slug>.md with stale flags set.
    `body_lines` is the body content (no leading frontmatter)."""
    _build_workspace(tmp_path)
    fm = {
        "schema_version": 1,
        "type": "concept",
        "created": "2026-01-01",
        "updated": "2026-01-01",
        "tags": [],
        "refs": {
            "code": [
                {
                    "path": r["path"],
                    "symbol": r["symbol"],
                    "confidence": "verified",
                    "stale": True,
                    "stale_detected": r["stale_detected"],
                }
                for r in stale_refs
            ],
            "papers": [],
            "concepts": [],
            "experiments": [],
        },
        "authored_by": "human",
        "source_sessions": [],
    }
    if body_stale_mentions is not None:
        fm["body_stale_mentions"] = body_stale_mentions
    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    body = "\n".join(body_lines)
    page = tmp_path / "wiki" / "concepts" / f"{slug}.md"
    page.write_text(f"---\n{fm_yaml}---\n{body}\n", encoding="utf-8")
    return page


# ---------- Replace ----------


def test_replace_substitutes_token_and_clears_flag(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "# Training",
            "",
            "OldAttention is the baseline.",
        ],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=[
        "y",                # continue with the run
        "1",                # action: replace
        "LegacyAttention",  # new symbol name
        "y",                # apply page edits
    ])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))

    assert result.body_edits_applied == 1
    assert result.stale_flags_cleared == 1
    assert result.pages_fully_cleared == 1

    text = page.read_text(encoding="utf-8")
    # Body should have the replacement; frontmatter retains original symbol
    # (per SPEC — replace edits body verbatim only; frontmatter ref symbol
    # is preserved unchanged. The `stale: true` flag is cleared instead.)
    body_section = text.split("---", 2)[2]
    assert "LegacyAttention is the baseline." in body_section
    assert "OldAttention" not in body_section
    # Frontmatter flag cleared.
    fm_yaml = text.split("---", 2)[1]
    fm_data = yaml.safe_load(fm_yaml)
    code_entry = fm_data["refs"]["code"][0]
    assert code_entry["symbol"] == "OldAttention"  # preserved per SPEC
    assert "stale" not in code_entry
    assert "stale_detected" not in code_entry


# ---------- Wrap ----------


def test_wrap_prepends_deprecated_tag(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "# Training",
            "",
            "OldAttention is the baseline.",
        ],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=[
        "y",
        "2",   # wrap
        "y",   # apply
    ])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.body_edits_applied == 1

    body = page.read_text(encoding="utf-8")
    assert "[deprecated 2026-04-26] OldAttention is the baseline." in body


# ---------- Delete ----------


def test_delete_removes_line(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "# Training",
            "",
            "Keep this line.",
            "OldAttention is the baseline.",
            "Also keep this line.",
        ],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=[
        "y",
        "3",   # delete
        "y",
    ])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.body_edits_applied == 1

    text = page.read_text(encoding="utf-8")
    body_section = text.split("---", 2)[2]
    assert "OldAttention" not in body_section
    assert "Keep this line." in body_section
    assert "Also keep this line." in body_section


# ---------- Skip ----------


def test_skip_preserves_flag_and_body(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "# Training",
            "OldAttention is here.",
        ],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )
    original_body = page.read_text(encoding="utf-8")

    prompt = ScriptedPrompt(responses=["y", "4", "y"])  # skip, then apply (no-op)
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))

    # All skipped → not fully cleared.
    assert result.pages_fully_cleared == 0
    assert result.pages_partial == 1
    assert result.stale_flags_cleared == 0

    body_after = page.read_text(encoding="utf-8")
    assert "stale: true" in body_after
    # Body is unchanged.
    assert "OldAttention is here." in body_after


# ---------- N (discard whole page) ----------


def test_discard_at_apply_prompt(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "OldAttention is here.",
        ],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )
    original_body = page.read_text(encoding="utf-8")

    prompt = ScriptedPrompt(responses=[
        "y",         # continue
        "2",         # wrap
        "n",         # don't apply
    ])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.pages_discarded == 1
    assert result.body_edits_applied == 0
    assert page.read_text(encoding="utf-8") == original_body


# ---------- Frontmatter-only false-positive ----------


def test_clear_flag_only_when_symbol_not_in_body(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=["# Training", "", "Body never mentions the symbol."],
        stale_refs=[{"path": "src/x.py", "symbol": "GhostSymbol", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=["y", "1", "y"])  # clear-flag-only, apply
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.body_edits_applied == 0
    # The flag should be cleared.
    assert result.stale_flags_cleared == 1

    body = page.read_text(encoding="utf-8")
    fm_yaml = body.split("---", 2)[1]
    fm_data = yaml.safe_load(fm_yaml)
    code_entry = fm_data["refs"]["code"][0]
    assert "stale" not in code_entry


# ---------- body_stale_mentions input ----------


def test_walks_body_stale_mentions(tmp_path: Path):
    page = _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=[
            "# Training",
            "",
            "Use UnknownThing here.",  # line 3
        ],
        stale_refs=[],  # no frontmatter stale ref
        body_stale_mentions=[{"line": 3, "token": "UnknownThing", "detected": "2026-04-20"}],
    )

    prompt = ScriptedPrompt(responses=[
        "y",          # continue
        "1",          # replace
        "RealThing",  # new symbol
        "y",          # apply
    ])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.body_edits_applied == 1
    body = page.read_text(encoding="utf-8")
    assert "Use RealThing here." in body
    # body_stale_mentions cleared.
    fm_yaml = body.split("---", 2)[1]
    fm_data = yaml.safe_load(fm_yaml)
    assert "body_stale_mentions" not in fm_data


# ---------- Session record ----------


def test_session_record_appended_to_log_md(tmp_path: Path):
    _add_stale_page(
        tmp_path,
        slug="training",
        body_lines=["OldAttention is here."],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=["y", "2", "y"])  # wrap, apply
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.log_record_appended

    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "from wiki-fix-stale" in log
    assert "Body edits applied:  1" in log


# ---------- No-stale state ----------


def test_no_stale_pages_does_nothing(tmp_path: Path):
    _build_workspace(tmp_path)
    prompt = ScriptedPrompt(responses=[])
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.pages_walked == 0
    assert result.body_edits_applied == 0


# ---------- Page filter ----------


def test_page_filter_restricts_to_one_page(tmp_path: Path):
    _build_workspace(tmp_path)
    # Two pages, both stale.
    for slug in ("a", "b"):
        _add_stale_page(
            tmp_path, slug=slug,
            body_lines=[f"OldAttention in {slug}."],
            stale_refs=[{"path": "src/x.py", "symbol": "OldAttention",
                         "stale_detected": "2026-04-10"}],
        )

    prompt = ScriptedPrompt(responses=["y", "4", "y"])  # skip, "apply" (no-op)
    result = run_fix_stale(
        tmp_path, prompt_fn=prompt, display_fn=_silent_display,
        today=date(2026, 4, 26),
        page_filter="wiki/concepts/a.md",
    )
    assert result.pages_walked == 1


# ---------- Researcher refuses to continue ----------


def test_initial_no_aborts_session(tmp_path: Path):
    _add_stale_page(
        tmp_path, slug="training",
        body_lines=["OldAttention is here."],
        stale_refs=[{"path": "src/x.py", "symbol": "OldAttention", "stale_detected": "2026-04-10"}],
    )

    prompt = ScriptedPrompt(responses=["n"])  # decline
    result = run_fix_stale(tmp_path, prompt_fn=prompt, display_fn=_silent_display, today=date(2026, 4, 26))
    assert result.pages_walked == 0


# ---------- Missing repo ----------


def test_missing_wiki_raises(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    with pytest.raises(FileNotFoundError):
        run_fix_stale(tmp_path, prompt_fn=ScriptedPrompt(responses=[]))
