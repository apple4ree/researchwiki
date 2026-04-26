"""Tests for the Markdown ATX heading scanner."""

from researchwiki.scanner import markdown


def test_extracts_atx_headings():
    source = (
        "# Title\n"
        "\n"
        "## Section A\n"
        "Some prose.\n"
        "\n"
        "### Subsection\n"
        "More prose.\n"
        "\n"
        "## Section B\n"
    )
    symbols, errors = markdown.scan("docs/intro.md", source)
    assert errors == []

    headings = [s.name for s in symbols]
    assert headings == ["Title", "Section A", "Subsection", "Section B"]

    depths = [s.extra["depth"] for s in symbols]
    assert depths == ["1", "2", "3", "2"]


def test_skips_frontmatter():
    source = (
        "---\n"
        "title: Foo\n"
        "tags: []\n"
        "---\n"
        "\n"
        "# Real Title\n"
    )
    symbols, _ = markdown.scan("docs/foo.md", source)
    assert [s.name for s in symbols] == ["Real Title"]


def test_skips_headings_inside_code_fence():
    source = (
        "# Real\n"
        "\n"
        "```\n"
        "# Not a heading — this is inside a code block\n"
        "```\n"
        "\n"
        "## Also Real\n"
    )
    symbols, _ = markdown.scan("docs/x.md", source)
    assert [s.name for s in symbols] == ["Real", "Also Real"]


def test_alternate_fence_marker():
    source = (
        "# A\n"
        "~~~\n"
        "# nope\n"
        "~~~\n"
        "## B\n"
    )
    symbols, _ = markdown.scan("docs/y.md", source)
    assert [s.name for s in symbols] == ["A", "B"]


def test_unterminated_frontmatter_treated_as_no_frontmatter():
    # If `---` appears at line 1 but is never closed, the rest of the file
    # should be treated as body. The first `---` is *not* a heading.
    source = (
        "---\n"
        "title: Foo\n"
        "# Looks like a heading inside frontmatter\n"
    )
    symbols, _ = markdown.scan("docs/z.md", source)
    # Frontmatter parser searches up to 200 lines for closing `---`. It
    # won't find one, so will treat as no frontmatter and scan from line 1.
    # But line 1 is `---` which is not an ATX heading — that's fine.
    # Line 3 is `# Looks like a heading...` — that should be picked up.
    assert any(s.name.startswith("Looks like") for s in symbols)
