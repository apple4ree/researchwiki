"""Unit tests for individual wiki-lint checks.

Each check is exercised in isolation with PageDoc inputs constructed
in-memory; no disk I/O. The end-to-end orchestration (loading pages
from disk, writing audit reports, append flow) is covered by
test_lint_runner.py.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from researchwiki.lint import PageDoc
from researchwiki.lint.checks import (
    check_authored_by_enum,
    check_confidence_conflicts,
    check_frontmatter_schema,
    check_intra_wiki_links,
    check_orphans,
    check_refs_code_paths,
    check_speculation_density,
    check_stale_age,
    extract_intra_wiki_link_targets,
)


def _doc(path, frontmatter=None, body=""):
    return PageDoc(
        path=path,
        frontmatter=frontmatter or {},
        body=body,
        raw_text="",
    )


# ---------- Check 1: frontmatter schema ----------


def test_check_frontmatter_schema_missing_field():
    page = _doc("wiki/concepts/x.md", frontmatter={"schema_version": 1})  # almost everything missing
    findings = check_frontmatter_schema([page])
    missing = {f.message for f in findings if f.category == "frontmatter"}
    assert any("authored_by" in m for m in missing)
    assert any("type" in m for m in missing)
    assert all(f.severity == "error" for f in findings)


def test_check_frontmatter_schema_full_passes():
    page = _doc("wiki/concepts/x.md", frontmatter=_full_valid_frontmatter())
    assert check_frontmatter_schema([page]) == []


def test_check_frontmatter_invalid_type():
    fm = _full_valid_frontmatter()
    fm["type"] = "novel"
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    findings = check_frontmatter_schema([page])
    assert any("`type: novel`" in f.message for f in findings)


def test_check_frontmatter_skips_meta_pages():
    """Meta pages (log/questions/discrepancies/index) are LLM-owned append-only
    files per CLAUDE.md §3; the §5 frontmatter schema does not apply to them."""
    meta = [
        PageDoc(path="wiki/log.md", frontmatter={}, body="", raw_text=""),
        PageDoc(path="wiki/questions.md", frontmatter={}, body="", raw_text=""),
        PageDoc(path="wiki/discrepancies.md", frontmatter={}, body="", raw_text=""),
        PageDoc(path="wiki/index.md", frontmatter={}, body="", raw_text=""),
    ]
    findings = check_frontmatter_schema(meta)
    assert findings == []


def test_check_frontmatter_parse_error():
    page = PageDoc(
        path="wiki/concepts/broken.md",
        frontmatter={},
        body="",
        raw_text="",
        parse_error="YAML parse error: ScannerError",
    )
    findings = check_frontmatter_schema([page])
    assert len(findings) == 1
    assert "Frontmatter parse failed" in findings[0].message


# ---------- Check 2: authored_by enum ----------


def test_check_authored_by_invalid():
    fm = _full_valid_frontmatter()
    fm["authored_by"] = "robot"
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    findings = check_authored_by_enum([page])
    assert any("`authored_by: robot`" in f.message for f in findings)


def test_check_authored_by_valid_passes():
    fm = _full_valid_frontmatter()
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    assert check_authored_by_enum([page]) == []


# ---------- Check 3: intra-wiki links ----------


def test_extract_intra_wiki_links():
    body = (
        "See [foo](concepts/foo.md) and [bar](papers/bar.md).\n"
        "External [Google](https://google.com) ignored.\n"
        "```\n"
        "[fenced](concepts/should-skip.md)\n"
        "```\n"
        "[anchor only](#section) ignored.\n"
        "Plain markdown [here](other.md) — relative to page_dir.\n"
    )
    targets = extract_intra_wiki_link_targets(body, "wiki/concepts/main.md", "wiki/")
    paths = [t for t, _ in targets]
    assert "wiki/concepts/foo.md" in paths
    assert "wiki/papers/bar.md" in paths
    assert "wiki/concepts/other.md" in paths
    assert not any("should-skip" in p for p in paths)
    assert not any("google.com" in p for p in paths)


def test_check_intra_wiki_links_broken():
    pages = [
        _doc("wiki/concepts/main.md", body="See [missing](concepts/ghost.md)."),
        _doc("wiki/concepts/exists.md"),
    ]
    findings = check_intra_wiki_links(pages, wiki_root="wiki/")
    assert len(findings) == 1
    assert "concepts/ghost.md" in findings[0].message


def test_check_intra_wiki_links_valid_target_passes():
    pages = [
        _doc("wiki/concepts/main.md", body="See [exists](exists.md)."),
        _doc("wiki/concepts/exists.md"),
    ]
    assert check_intra_wiki_links(pages, wiki_root="wiki/") == []


# ---------- Check 4: refs.code.path file existence ----------


def test_check_refs_code_paths(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "trainer.py").write_text("class T: ...\n")
    fm = _full_valid_frontmatter()
    fm["refs"] = {"code": [
        {"path": "src/trainer.py", "symbol": "T", "confidence": "verified"},
        {"path": "src/missing.py", "symbol": "X", "confidence": "verified"},
    ], "papers": [], "concepts": [], "experiments": []}
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    findings = check_refs_code_paths([page], repo_root=tmp_path)
    assert len(findings) == 1
    assert "src/missing.py" in findings[0].message


# ---------- Check 5: speculation density ----------


def test_check_speculation_density_above_threshold():
    body = (
        "First sentence. Second sentence. Third sentence. "
        "[speculation] Fourth tagged. [speculation] Fifth tagged."
    )
    page = _doc("wiki/concepts/x.md", body=body)
    findings = check_speculation_density([page], threshold=0.30)
    assert len(findings) == 1
    assert "exceeds threshold" in findings[0].message


def test_check_speculation_density_below_threshold():
    body = (
        "S1. S2. S3. S4. S5. S6. S7. S8. S9. S10. "
        "[speculation] one tagged."
    )
    page = _doc("wiki/concepts/x.md", body=body)
    findings = check_speculation_density([page], threshold=0.30)
    assert findings == []  # 1/11 = 0.09 < 0.30


def test_check_speculation_skips_short_pages():
    body = "Only one sentence."
    page = _doc("wiki/concepts/stub.md", body=body)
    assert check_speculation_density([page], threshold=0.30) == []


# ---------- Check 6: stale age ----------


def test_check_stale_age_above_threshold():
    fm = _full_valid_frontmatter()
    fm["refs"] = {"code": [
        {"path": "src/x.py", "symbol": "Y", "confidence": "verified",
         "stale": True, "stale_detected": "2026-04-10"},
    ], "papers": [], "concepts": [], "experiments": []}
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    today = date(2026, 4, 26)
    findings = check_stale_age([page], threshold_days=7, today=today)
    assert len(findings) == 1
    assert "16 days" in findings[0].message


def test_check_stale_age_below_threshold():
    fm = _full_valid_frontmatter()
    fm["refs"] = {"code": [
        {"path": "src/x.py", "symbol": "Y",
         "stale": True, "stale_detected": "2026-04-25"},
    ], "papers": [], "concepts": [], "experiments": []}
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    today = date(2026, 4, 26)
    assert check_stale_age([page], threshold_days=7, today=today) == []


def test_check_stale_age_ignores_non_stale_refs():
    fm = _full_valid_frontmatter()
    fm["refs"] = {"code": [
        {"path": "src/x.py", "symbol": "Y", "confidence": "verified"},
    ], "papers": [], "concepts": [], "experiments": []}
    page = _doc("wiki/concepts/x.md", frontmatter=fm)
    assert check_stale_age([page], threshold_days=7, today=date(2026, 4, 26)) == []


# ---------- Check 7: confidence conflicts ----------


def test_check_confidence_conflict_detected():
    fm_a = _full_valid_frontmatter()
    fm_a["refs"] = {"code": [
        {"path": "src/trainer.py", "symbol": "Trainer", "confidence": "verified"},
    ], "papers": [], "concepts": [], "experiments": []}
    fm_b = _full_valid_frontmatter()
    fm_b["refs"] = {"code": [
        {"path": "src/trainer.py", "symbol": "Trainer", "confidence": "inferred"},
    ], "papers": [], "concepts": [], "experiments": []}

    pages = [
        _doc("wiki/concepts/a.md", frontmatter=fm_a),
        _doc("wiki/concepts/b.md", frontmatter=fm_b),
    ]
    findings = check_confidence_conflicts(pages)
    assert len(findings) == 1
    assert findings[0].page == "src/trainer.py:Trainer"
    assert "verified" in findings[0].message and "inferred" in findings[0].message


def test_check_confidence_consistent_passes():
    fm_a = _full_valid_frontmatter()
    fm_a["refs"] = {"code": [
        {"path": "src/x.py", "symbol": "Y", "confidence": "verified"},
    ], "papers": [], "concepts": [], "experiments": []}
    fm_b = _full_valid_frontmatter()
    fm_b["refs"] = {"code": [
        {"path": "src/x.py", "symbol": "Y", "confidence": "verified"},
    ], "papers": [], "concepts": [], "experiments": []}
    pages = [
        _doc("wiki/concepts/a.md", frontmatter=fm_a),
        _doc("wiki/concepts/b.md", frontmatter=fm_b),
    ]
    assert check_confidence_conflicts(pages) == []


# ---------- Check 8: orphans ----------


def test_check_orphans_no_inbound():
    pages = [
        _doc("wiki/concepts/lonely.md", frontmatter=_full_valid_frontmatter()),
        _doc("wiki/concepts/other.md", frontmatter=_full_valid_frontmatter()),
    ]
    findings = check_orphans(pages, wiki_root="wiki/", grace_days=30, today=date(2026, 4, 26))
    paths = {f.page for f in findings}
    assert "wiki/concepts/lonely.md" in paths
    assert "wiki/concepts/other.md" in paths
    assert all(f.severity == "info" for f in findings)


def test_check_orphans_inbound_via_frontmatter_refs():
    fm_a = _full_valid_frontmatter()
    fm_a["refs"] = {"code": [], "papers": [], "concepts": ["target"], "experiments": []}
    pages = [
        _doc("wiki/concepts/source.md", frontmatter=fm_a),
        _doc("wiki/concepts/target.md", frontmatter=_full_valid_frontmatter()),
    ]
    findings = check_orphans(pages, wiki_root="wiki/", grace_days=30, today=date(2026, 4, 26))
    paths = {f.page for f in findings}
    # source has no inbound; target has 1 inbound from source.
    assert "wiki/concepts/source.md" in paths
    assert "wiki/concepts/target.md" not in paths


def test_check_orphans_inbound_via_body_link():
    pages = [
        _doc("wiki/concepts/source.md", frontmatter=_full_valid_frontmatter(),
             body="See [target](target.md)."),
        _doc("wiki/concepts/target.md", frontmatter=_full_valid_frontmatter()),
    ]
    findings = check_orphans(pages, wiki_root="wiki/", grace_days=30, today=date(2026, 4, 26))
    paths = {f.page for f in findings}
    assert "wiki/concepts/target.md" not in paths


def test_check_orphans_excludes_meta_pages():
    pages = [
        _doc("wiki/log.md", frontmatter={}),
        _doc("wiki/index.md", frontmatter={}),
        _doc("wiki/questions.md", frontmatter={}),
        _doc("wiki/discrepancies.md", frontmatter={}),
    ]
    findings = check_orphans(pages, wiki_root="wiki/", grace_days=30, today=date(2026, 4, 26))
    assert findings == []


def test_check_orphans_seeded_stub_within_grace():
    fm = _full_valid_frontmatter()
    fm["created"] = "2026-04-25"
    fm["seeded_by"] = "wiki-log"
    pages = [_doc("wiki/concepts/fresh-stub.md", frontmatter=fm)]
    findings = check_orphans(
        pages, wiki_root="wiki/",
        grace_days=30, today=date(2026, 4, 26),
    )
    assert findings == []


def test_check_orphans_seeded_stub_past_grace():
    fm = _full_valid_frontmatter()
    fm["created"] = "2026-01-01"  # 115 days ago
    fm["seeded_by"] = "wiki-log"
    pages = [_doc("wiki/concepts/old-stub.md", frontmatter=fm)]
    findings = check_orphans(
        pages, wiki_root="wiki/",
        grace_days=30, today=date(2026, 4, 26),
    )
    assert len(findings) == 1


# ---------- helpers ----------


def _full_valid_frontmatter():
    return {
        "schema_version": 1,
        "type": "concept",
        "created": "2026-04-01",
        "updated": "2026-04-01",
        "tags": [],
        "refs": {"code": [], "papers": [], "concepts": [], "experiments": []},
        "authored_by": "human",
        "source_sessions": [],
    }
