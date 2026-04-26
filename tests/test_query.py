"""Tests for wiki-query (BM25 lexical search)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from researchwiki.query import (
    build_index,
    load_pages,
    score_doc,
    search,
    stale_badge,
    tokenize,
)


# ---------- Tokenizer ----------


def test_tokenize_camel_case():
    tokens = tokenize("RotaryEmbedding")
    assert "rotaryembedding" in tokens  # whole chunk
    assert "rotary" in tokens
    assert "embedding" in tokens


def test_tokenize_snake_case():
    tokens = tokenize("train_one_epoch")
    assert "train_one_epoch" in tokens
    assert "train" in tokens
    assert "one" in tokens
    assert "epoch" in tokens


def test_tokenize_kebab_case():
    tokens = tokenize("data-loader")
    assert "data-loader" in tokens
    assert "data" in tokens
    assert "loader" in tokens


def test_tokenize_path():
    tokens = tokenize("src/trainer.py")
    assert "src/trainer.py" in tokens
    assert "src" in tokens
    assert "trainer" in tokens
    assert "py" in tokens


def test_tokenize_korean():
    tokens = tokenize("로터리 임베딩")
    assert "로터리" in tokens
    assert "임베딩" in tokens


def test_tokenize_strips_punctuation():
    tokens = tokenize("Hello, world!")
    assert "hello" in tokens
    assert "world" in tokens
    # Should not have trailing punctuation in the cleaned tokens.
    assert "hello," not in tokens
    assert "world!" not in tokens


# ---------- BM25 scoring ----------


def test_score_doc_higher_for_more_matches():
    from researchwiki.query import Doc

    doc_a = Doc(path="a.md", raw_text="", body="", frontmatter={},
                tokens=["rotary", "embedding"], token_freq={"rotary": 1, "embedding": 1}, length=2)
    doc_b = Doc(path="b.md", raw_text="", body="", frontmatter={},
                tokens=["rotary"], token_freq={"rotary": 1}, length=1)
    doc_c = Doc(path="c.md", raw_text="", body="", frontmatter={},
                tokens=["unrelated"], token_freq={"unrelated": 1}, length=1)
    index = build_index([doc_a, doc_b, doc_c])

    s_a = score_doc(["rotary", "embedding"], doc_a, index)
    s_b = score_doc(["rotary", "embedding"], doc_b, index)
    s_c = score_doc(["rotary", "embedding"], doc_c, index)

    assert s_a > s_b > s_c
    assert s_c == 0.0


# ---------- Stale badge ----------


def test_stale_badge_with_age():
    fm = {
        "refs": {
            "code": [
                {"path": "src/x.py", "symbol": "Y", "stale": True, "stale_detected": "2026-04-01"},
                {"path": "src/x.py", "symbol": "Z", "stale": True, "stale_detected": "2026-04-20"},
            ],
        }
    }
    badge = stale_badge(fm, today=date(2026, 4, 26))
    assert "2 ref" in badge
    assert "25d" in badge  # oldest = 25 days ago


def test_stale_badge_returns_none_when_no_stale():
    fm = {"refs": {"code": [{"path": "src/x.py", "symbol": "Y", "confidence": "verified"}]}}
    assert stale_badge(fm, today=date(2026, 4, 26)) is None


# ---------- End-to-end search via load_pages ----------


def _build_wiki(tmp_path: Path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "papers").mkdir(parents=True)

    (tmp_path / "wiki" / "concepts" / "attention.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/model/attention.py\n"
        "      symbol: MultiHeadAttention\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "---\n"
        "# Attention\n"
        "\n"
        "The MultiHeadAttention block uses scaled dot-product attention with\n"
        "rotary position embedding. We chose this over sinusoidal embeddings.\n",
        encoding="utf-8",
    )

    (tmp_path / "wiki" / "papers" / "sparse-attention.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: paper\n"
        "tags: []\n"
        "refs:\n"
        "  code: []\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "---\n"
        "# Sparse attention paper\n"
        "\n"
        "Authors propose sparse patterns to reduce O(n²) cost. They do not\n"
        "address rotary embeddings.\n",
        encoding="utf-8",
    )

    (tmp_path / "wiki" / "log.md").write_text("# Log — meta page\n", encoding="utf-8")
    (tmp_path / "wiki" / "questions.md").write_text("# Q\n", encoding="utf-8")
    (tmp_path / "wiki" / "discrepancies.md").write_text("# D\n", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("# I\n", encoding="utf-8")


def test_search_ranks_relevant_first(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path)
    results = search("rotary attention", docs, top=5)
    assert results, "expected at least one result"
    assert results[0].path == "wiki/concepts/attention.md"


def test_search_excludes_meta_pages_by_default(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path)
    paths = {d.path for d in docs}
    assert "wiki/log.md" not in paths
    assert "wiki/index.md" not in paths


def test_search_include_meta_flag(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path, include_meta=True)
    paths = {d.path for d in docs}
    assert "wiki/log.md" in paths


def test_search_scope_filter(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path, scope="papers")
    assert all(d.path.startswith("wiki/papers/") for d in docs)


def test_search_scope_invalid(tmp_path: Path):
    _build_wiki(tmp_path)
    with pytest.raises(ValueError):
        load_pages(tmp_path / "wiki", tmp_path, scope="nonexistent")


def test_search_empty_query_raises(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path)
    with pytest.raises(ValueError):
        search("   ", docs)


def test_search_zero_results_returns_empty(tmp_path: Path):
    _build_wiki(tmp_path)
    docs = load_pages(tmp_path / "wiki", tmp_path)
    results = search("blockchain", docs)
    assert results == []


def test_search_frontmatter_only(tmp_path: Path):
    _build_wiki(tmp_path)
    # Search for a path that appears only in frontmatter, not in body.
    docs = load_pages(tmp_path / "wiki", tmp_path, frontmatter_only=True)
    results = search("MultiHeadAttention", docs)
    paths = {r.path for r in results}
    assert "wiki/concepts/attention.md" in paths


def test_search_stale_badge_in_results(tmp_path: Path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts" / "training.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/old.py\n"
        "      symbol: Old\n"
        "      confidence: verified\n"
        "      stale: true\n"
        "      stale_detected: '2026-04-01'\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "---\n"
        "# Training\n"
        "\n"
        "Body about Old.\n",
        encoding="utf-8",
    )
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    (tmp_path / "wiki" / "questions.md").write_text("# Q\n", encoding="utf-8")
    (tmp_path / "wiki" / "discrepancies.md").write_text("# D\n", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("# I\n", encoding="utf-8")

    docs = load_pages(tmp_path / "wiki", tmp_path)
    results = search("Old", docs, today=date(2026, 4, 26))
    assert results[0].badge is not None
    assert "stale" in results[0].badge


def test_search_no_stale_warnings(tmp_path: Path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts" / "training.md").write_text(
        "---\n"
        "type: concept\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/old.py\n"
        "      symbol: Old\n"
        "      stale: true\n"
        "      stale_detected: '2026-04-01'\n"
        "---\n"
        "# Training\n"
        "Body about Old.\n",
        encoding="utf-8",
    )
    (tmp_path / "wiki" / "log.md").write_text("\n")
    (tmp_path / "wiki" / "questions.md").write_text("\n")
    (tmp_path / "wiki" / "discrepancies.md").write_text("\n")
    (tmp_path / "wiki" / "index.md").write_text("\n")

    docs = load_pages(tmp_path / "wiki", tmp_path)
    results = search("Old", docs, stale_warnings=False)
    assert results[0].badge is None
