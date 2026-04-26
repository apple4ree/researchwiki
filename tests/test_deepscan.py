"""Tests for wiki-deepscan.

Tests use the `from_graph` parameter to load synthetic JSON fixtures —
they do not require the Understand-Anything binary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from researchwiki.deepscan import KnowledgeGraph, run_deepscan


def _build_workspace(root: Path) -> None:
    (root / "CLAUDE.md").write_text("placeholder\n")
    (root / "research-wiki.config.yaml").write_text("schema_version: 1\n")
    (root / "src").mkdir()
    (root / "src" / "trainer.py").write_text("class Trainer: ...\n")
    (root / "src" / "loader.py").write_text("class DataLoader: ...\n")
    (root / "wiki").mkdir()
    (root / "wiki" / "concepts").mkdir()
    (root / "wiki" / "papers").mkdir()
    (root / "wiki" / "experiments").mkdir()
    (root / "wiki" / "decisions").mkdir()
    (root / "wiki" / "log.md").write_text("# Log\n")
    (root / "wiki" / "questions.md").write_text("# Q\n")
    (root / "wiki" / "discrepancies.md").write_text("# D\n")
    (root / "wiki" / "index.md").write_text("# I\n")


def _write_graph(path: Path, nodes: list[dict]) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": "2026-04-27T10:00:00+09:00",
        "git_ref": "abc1234",
        "tool": "understand-anything",
        "tool_version": "0.4.2",
        "scope": ".",
        "nodes": nodes,
        "edges_total": sum(n.get("inbound_edges", 0) for n in nodes),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_seeds_stub_for_significant_node(tmp_path: Path):
    _build_workspace(tmp_path)
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/loader.py",
        "name": "DataLoader",
        "kind": "class",
        "symbols": ["DataLoader", "DataLoader.__iter__"],
        "inbound_edges": 18,
        "inbound_callers": [{"path": "src/trainer.py", "lines": [10, 20]}],
        "outbound_dependencies": [{"path": "src/dataset.py", "symbol": "Dataset"}],
        "architecturally_significant": True,
        "suggested_slug": "data-loader",
    }])

    result = run_deepscan(tmp_path, from_graph=graph_path)

    assert len(result.stubs_created) == 1
    stub = tmp_path / "wiki" / "concepts" / "data-loader.md"
    assert stub.exists()
    text = stub.read_text(encoding="utf-8")
    # Frontmatter
    assert "type: concept" in text
    assert "authored_by: llm" in text
    assert "seeded_by: wiki-deepscan" in text
    assert "src/loader.py" in text
    # Body — structural facts only, no purpose prose.
    assert "## Structural facts" in text
    assert "## Notes from researcher" in text
    assert "## Open questions for researcher" in text
    # Should NOT contain LLM prose about "what this is for".
    assert "responsible for" not in text.lower()
    assert "designed to" not in text.lower()


def test_skips_nodes_below_threshold(tmp_path: Path):
    _build_workspace(tmp_path)
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/utils.py",
        "name": "Utility",
        "kind": "class",
        "symbols": ["Utility"],
        "inbound_edges": 1,  # below default threshold of 3
        "inbound_callers": [],
        "outbound_dependencies": [],
        "architecturally_significant": True,
        "suggested_slug": "utility",
    }])
    result = run_deepscan(tmp_path, from_graph=graph_path)
    assert result.stubs_created == []
    assert not (tmp_path / "wiki" / "concepts" / "utility.md").exists()


def test_skips_non_significant_nodes(tmp_path: Path):
    _build_workspace(tmp_path)
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/big.py",
        "name": "Big",
        "kind": "class",
        "symbols": ["Big"],
        "inbound_edges": 50,
        "inbound_callers": [],
        "outbound_dependencies": [],
        "architecturally_significant": False,
        "suggested_slug": "big",
    }])
    result = run_deepscan(tmp_path, from_graph=graph_path)
    assert result.stubs_created == []


def test_naming_conflict_logs_to_questions_md(tmp_path: Path):
    _build_workspace(tmp_path)
    # Pre-existing concept page at the same slug, but for a *different* path.
    (tmp_path / "wiki" / "concepts" / "loader.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/config.py\n"  # different path
        "      symbol: ConfigLoader\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body — should not be touched.\n",
        encoding="utf-8",
    )

    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/loader.py",
        "name": "DataLoader",
        "kind": "class",
        "symbols": ["DataLoader"],
        "inbound_edges": 10,
        "inbound_callers": [],
        "outbound_dependencies": [],
        "architecturally_significant": True,
        "suggested_slug": "loader",  # collides
    }])

    result = run_deepscan(tmp_path, from_graph=graph_path)
    assert result.stubs_created == []
    assert len(result.naming_conflicts) == 1
    assert result.naming_conflicts[0].incoming_path == "src/loader.py"

    q_text = (tmp_path / "wiki" / "questions.md").read_text(encoding="utf-8")
    assert "Naming conflict" in q_text
    assert "src/loader.py" in q_text

    # Body of pre-existing page must be untouched.
    body = (tmp_path / "wiki" / "concepts" / "loader.md").read_text(encoding="utf-8")
    assert "Body — should not be touched." in body


def test_appends_refs_to_existing_same_concept_page(tmp_path: Path):
    _build_workspace(tmp_path)
    # Pre-existing page that ALREADY references src/loader.py, but only the class.
    (tmp_path / "wiki" / "concepts" / "loader.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/loader.py\n"
        "      symbol: DataLoader\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body untouched.\n",
        encoding="utf-8",
    )

    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/loader.py",
        "name": "DataLoader",
        "kind": "class",
        "symbols": ["DataLoader", "DataLoader.__iter__", "DataLoader.shuffle"],  # 2 new
        "inbound_edges": 18,
        "inbound_callers": [],
        "outbound_dependencies": [],
        "architecturally_significant": True,
        "suggested_slug": "loader",
    }])

    result = run_deepscan(tmp_path, from_graph=graph_path)
    assert result.stubs_created == []
    assert len(result.frontmatter_appends) == 1
    appended_symbols = [r["symbol"] for r in result.frontmatter_appends[0].added_refs]
    assert set(appended_symbols) == {"DataLoader.__iter__", "DataLoader.shuffle"}

    page_text = (tmp_path / "wiki" / "concepts" / "loader.md").read_text(encoding="utf-8")
    assert "DataLoader.__iter__" in page_text
    assert "DataLoader.shuffle" in page_text
    # Body still untouched.
    assert "Body untouched." in page_text


def test_detects_graph_vs_frontmatter_discrepancy(tmp_path: Path):
    _build_workspace(tmp_path)
    # Wiki page declares Trainer at src/legacy/trainer.py.
    (tmp_path / "wiki" / "concepts" / "training.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "created: 2026-04-01\n"
        "updated: 2026-04-01\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/legacy/trainer.py\n"
        "      symbol: Trainer\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )

    # Graph reports Trainer at src/trainer.py — different path.
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [{
        "path": "src/trainer.py",
        "name": "Trainer",
        "kind": "class",
        "symbols": ["Trainer"],
        "inbound_edges": 5,
        "inbound_callers": [],
        "outbound_dependencies": [],
        "architecturally_significant": True,
        "suggested_slug": "trainer",
    }])

    result = run_deepscan(tmp_path, from_graph=graph_path)
    assert len(result.discrepancies) == 1
    d = result.discrepancies[0]
    assert d.symbol == "Trainer"
    assert d.frontmatter_path == "src/legacy/trainer.py"
    assert d.graph_path == "src/trainer.py"

    disc_text = (tmp_path / "wiki" / "discrepancies.md").read_text(encoding="utf-8")
    assert "Graph vs frontmatter mismatch" in disc_text
    assert "src/legacy/trainer.py" in disc_text
    assert "src/trainer.py" in disc_text


def test_writes_deep_artifacts(tmp_path: Path):
    _build_workspace(tmp_path)
    graph_path = tmp_path / "graph.json"
    _write_graph(graph_path, [])
    result = run_deepscan(tmp_path, from_graph=graph_path)

    assert (tmp_path / "deep" / "knowledge-graph.json").exists()
    assert (tmp_path / "deep" / "last-scan.yaml").exists()
    last_scan = yaml.safe_load((tmp_path / "deep" / "last-scan.yaml").read_text(encoding="utf-8"))
    assert last_scan["tool"] == "understand-anything"
    assert last_scan["tool_version"] == "0.4.2"
    assert last_scan["nodes"] == 0

    assert result.report_path.exists()
    report = result.report_path.read_text(encoding="utf-8")
    assert "# Deepscan report" in report
    assert "## Graph summary" in report


def test_missing_repo_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        run_deepscan(tmp_path / "nonexistent")


def test_missing_external_tool_raises(tmp_path: Path, monkeypatch):
    _build_workspace(tmp_path)
    # No `from_graph` and no UA installed → must raise FileNotFoundError.
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="understand-anything binary not found"):
        run_deepscan(tmp_path)
