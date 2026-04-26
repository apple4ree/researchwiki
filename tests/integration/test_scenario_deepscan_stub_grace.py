"""S3 — wiki-deepscan seeds a stub; wiki-lint orphan-check honors grace.

Verifies the seeded_by + grace_days cooperation between wiki-deepscan
and wiki-lint Check 8 (orphan).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from researchwiki.deepscan import run_deepscan
from researchwiki.lint import run_lint

from tests.integration._helpers import (
    add_src_file,
    bootstrap_workspace,
    set_page_created,
)


def _write_synthetic_graph(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": "2026-04-01T00:00:00+00:00",
        "git_ref": "abc1234",
        "tool": "understand-anything",
        "tool_version": "0.4.2",
        "scope": ".",
        "nodes": [{
            "path": "src/data/loader.py",
            "name": "DataLoader",
            "kind": "class",
            "symbols": ["DataLoader"],
            "inbound_edges": 5,
            "inbound_callers": [],
            "outbound_dependencies": [],
            "architecturally_significant": True,
            "suggested_slug": "data-loader",
        }],
        "edges_total": 5,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scenario_deepscan_stub_within_grace_not_flagged(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/data/loader.py", "class DataLoader:\n    pass\n")
    graph = tmp_path / "_graph.json"
    _write_synthetic_graph(graph)

    # deepscan seeds a stub at wiki/concepts/data-loader.md
    deep_result = run_deepscan(tmp_path, from_graph=graph)
    assert len(deep_result.stubs_created) == 1

    stub = tmp_path / "wiki" / "concepts" / "data-loader.md"
    assert stub.exists()

    # Force the stub's `created:` field to a known date so we can test the
    # grace-period boundary deterministically (deepscan's internal date is
    # `datetime.now()`, not parametrized).
    set_page_created(tmp_path, "wiki/concepts/data-loader.md", created="2026-04-01")

    # Lint within the grace period (5 days after creation, default grace = 30).
    lint_within = run_lint(tmp_path, today=date(2026, 4, 6))
    orphan_findings = [f for f in lint_within.findings if f.category == "orphans"]
    stub_orphans = [f for f in orphan_findings if "data-loader" in f.page]
    assert stub_orphans == [], (
        "seeded_by stub within grace period should NOT be reported as orphan."
    )


def test_scenario_deepscan_stub_past_grace_is_flagged(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/data/loader.py", "class DataLoader:\n    pass\n")
    graph = tmp_path / "_graph.json"
    _write_synthetic_graph(graph)

    run_deepscan(tmp_path, from_graph=graph)
    set_page_created(tmp_path, "wiki/concepts/data-loader.md", created="2026-04-01")

    # 35 days later — grace expired (default grace_days = 30).
    lint_past = run_lint(tmp_path, today=date(2026, 5, 6))
    orphan_findings = [f for f in lint_past.findings if f.category == "orphans"]
    stub_orphans = [f for f in orphan_findings if "data-loader" in f.page]
    assert len(stub_orphans) == 1, (
        "seeded_by stub past grace period SHOULD be reported as orphan."
    )
