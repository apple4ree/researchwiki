"""Tests for the YAML frontmatter parser + stale-marker writer."""

from datetime import date

from researchwiki import frontmatter as fm


def _make_page(tmp_path, content):
    p = tmp_path / "page.md"
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_with_frontmatter(tmp_path):
    p = _make_page(tmp_path, (
        "---\n"
        "type: concept\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/trainer.py\n"
        "      symbol: Trainer\n"
        "      confidence: verified\n"
        "---\n"
        "\n"
        "# Body\n"
    ))
    doc = fm.load(p)
    assert doc.has_frontmatter
    assert doc.frontmatter["type"] == "concept"
    refs = fm.code_refs(doc)
    assert len(refs) == 1
    assert refs[0]["path"] == "src/trainer.py"
    assert refs[0]["symbol"] == "Trainer"


def test_parse_no_frontmatter(tmp_path):
    p = _make_page(tmp_path, "# Just body, no frontmatter\n")
    doc = fm.load(p)
    assert not doc.has_frontmatter
    assert doc.frontmatter == {}
    assert fm.code_refs(doc) == []


def test_mark_refs_stale_idempotent(tmp_path):
    p = _make_page(tmp_path, (
        "---\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/trainer.py\n"
        "      symbol: Trainer\n"
        "      confidence: verified\n"
        "    - path: src/trainer.py\n"
        "      symbol: Helper\n"
        "      confidence: verified\n"
        "---\n"
        "Body content stays.\n"
    ))
    today = date(2026, 4, 26)

    n1 = fm.mark_refs_stale(
        p,
        stale_keys={("src/trainer.py", "Helper")},
        detected=today,
    )
    assert n1 == 1

    # Second invocation with the same key should be a no-op.
    n2 = fm.mark_refs_stale(
        p,
        stale_keys={("src/trainer.py", "Helper")},
        detected=today,
    )
    assert n2 == 0

    # Verify body untouched (P3 — wiki-sync only edits frontmatter).
    text = p.read_text(encoding="utf-8")
    assert "Body content stays." in text

    # Verify the targeted ref got the flag and the other did not.
    doc = fm.load(p)
    refs = fm.code_refs(doc)
    by_symbol = {r["symbol"]: r for r in refs}
    assert by_symbol["Helper"].get("stale") is True
    assert by_symbol["Helper"].get("stale_detected") == "2026-04-26"
    assert "stale" not in by_symbol["Trainer"]
