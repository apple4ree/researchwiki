"""End-to-end tests for `wiki-lint`.

Builds a fixture wiki containing intentional findings across several
checks, runs `run_lint`, verifies the audit report and append flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from researchwiki.lint import run_lint


def _build_fixture(root: Path) -> None:
    (root / "CLAUDE.md").write_text("# placeholder\n", encoding="utf-8")
    (root / "research-wiki.config.yaml").write_text("schema_version: 1\n", encoding="utf-8")

    (root / "src").mkdir()
    (root / "src" / "trainer.py").write_text("class Trainer: ...\n", encoding="utf-8")

    wiki = root / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "papers").mkdir(parents=True)
    (wiki / "experiments").mkdir(parents=True)
    (wiki / "decisions").mkdir(parents=True)

    # Page A — fully well-formed, references existing src + a concept stub.
    (wiki / "concepts" / "training-loop.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/trainer.py\n"
        "      symbol: Trainer\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: [rotary]\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "\n"
        "# Training loop\n"
        "\n"
        "See [intro](broken-target.md) for context.\n"  # broken intra-wiki link
        "Cross-reference: [rotary](rotary.md).\n",      # valid intra-wiki link
        encoding="utf-8",
    )

    # Page B — missing required frontmatter field (authored_by); broken ref.code.path.
    (wiki / "concepts" / "rotary.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/missing.py\n"  # file does not exist → Check 4
        "      symbol: Z\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "source_sessions: []\n"  # NOTE: authored_by missing → Check 1
        "---\n"
        "\n"
        "# Rotary\n"
        "\n"
        "Body content.\n",
        encoding="utf-8",
    )

    # Page C — confidence conflict with Page A on the same code symbol.
    (wiki / "experiments" / "exp-001.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: experiment\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/trainer.py\n"
        "      symbol: Trainer\n"
        "      confidence: inferred\n"  # conflicts with training-loop.md → Check 7
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "\n"
        "# Exp 001\n"
        "\n"
        "First sentence. Second. Third. Fourth. Fifth.\n",
        encoding="utf-8",
    )

    # Page D — orphan (nothing references it, not a meta page, not a stub).
    (wiki / "decisions" / "lonely.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: decision\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
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
        "# Lonely decision\n"
        "\n"
        "Body content.\n",
        encoding="utf-8",
    )

    # Meta files — required for various checks but should be excluded from orphan.
    (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
    (wiki / "questions.md").write_text("# Questions\n", encoding="utf-8")
    (wiki / "discrepancies.md").write_text("# Discrepancies\n", encoding="utf-8")
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")


def test_end_to_end_lint(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_lint(tmp_path)

    findings_by_category = {}
    for f in result.findings:
        findings_by_category.setdefault(f.category, []).append(f)

    # Check 1 (frontmatter): rotary.md missing authored_by
    fm_findings = findings_by_category.get("frontmatter", [])
    assert any(
        f.page == "wiki/concepts/rotary.md" and "authored_by" in f.message
        for f in fm_findings
    )
    assert all(f.severity == "error" for f in fm_findings)

    # Check 3 (links): training-loop.md → broken-target.md
    link_findings = findings_by_category.get("links", [])
    assert any(
        "broken-target.md" in f.message for f in link_findings
    )
    # Check 4 (links): rotary.md → src/missing.py
    assert any(
        "src/missing.py" in f.message for f in link_findings
    )

    # Check 7 (contradictions): src/trainer.py:Trainer
    contra = findings_by_category.get("contradictions", [])
    assert len(contra) == 1
    assert contra[0].page == "src/trainer.py:Trainer"
    assert "verified" in contra[0].message and "inferred" in contra[0].message

    # Check 8 (orphans): decisions/lonely.md
    orphans = findings_by_category.get("orphans", [])
    orphan_paths = {f.page for f in orphans}
    assert "wiki/decisions/lonely.md" in orphan_paths
    # Meta files NOT flagged.
    assert "wiki/log.md" not in orphan_paths
    assert "wiki/index.md" not in orphan_paths

    # Audit report written.
    assert result.report_path is not None
    assert result.report_path.exists()
    report_text = result.report_path.read_text(encoding="utf-8")
    assert "# Lint audit" in report_text
    assert "## Summary" in report_text
    assert "## Findings" in report_text

    # questions.md got entries (frontmatter, links, etc., excluding contradictions + info-orphans)
    q_text = (tmp_path / "wiki/questions.md").read_text(encoding="utf-8")
    assert "from wiki-lint" in q_text
    assert "rotary.md" in q_text  # frontmatter finding
    # Contradictions go to discrepancies.md, NOT questions.md
    assert "Confidence conflict" not in q_text

    # discrepancies.md got the conflict entry.
    d_text = (tmp_path / "wiki/discrepancies.md").read_text(encoding="utf-8")
    assert "from wiki-lint" in d_text
    assert "src/trainer.py:Trainer" in d_text


def test_strict_mode_exit_code(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_lint(tmp_path, strict=True)
    assert result.exit_code == 1
    # All findings escalated to error.
    assert all(f.severity == "error" for f in result.findings)


def test_no_write_does_not_create_files(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_lint(tmp_path, no_write=True)
    assert result.report_path is None
    audits_dir = tmp_path / "index" / "audits"
    if audits_dir.exists():
        assert not list(audits_dir.glob("lint_*.md"))
    q_text = (tmp_path / "wiki/questions.md").read_text(encoding="utf-8")
    assert "from wiki-lint" not in q_text


def test_scope_filter(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_lint(tmp_path, scope=["frontmatter"], no_write=True)
    categories = {f.category for f in result.findings}
    assert categories <= {"frontmatter"}


def test_scope_invalid_raises(tmp_path: Path):
    _build_fixture(tmp_path)
    with pytest.raises(ValueError):
        run_lint(tmp_path, scope=["nonexistent"], no_write=True)


def test_missing_wiki_raises(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    with pytest.raises(FileNotFoundError):
        run_lint(tmp_path)
