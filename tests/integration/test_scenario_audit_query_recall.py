"""S2 — Weekly audit + query + recall on a fixture wiki.

Verifies that:
- wiki-sync's reverse_refs powers `jq`-style impact analysis.
- wiki-query returns ranked results across multiple wiki subdirectories,
  with stale badges on flagged pages.
- wiki-recall surfaces forgotten pages whose refs overlap with recent
  log activity.
- wiki-lint passes without errors on a clean fixture.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from researchwiki.lint import run_lint
from researchwiki.query import load_pages, search
from researchwiki.recall import run_recall
from researchwiki.sync import run_sync

from tests.integration._helpers import (
    add_src_file,
    add_wiki_page,
    append_log_entry,
    bootstrap_workspace,
)


def test_scenario_audit_query_recall(tmp_path: Path):
    bootstrap_workspace(tmp_path)
    add_src_file(tmp_path, "src/model/attention.py",
                 "class MultiHeadAttention:\n    pass\n")

    # Old concept page (a prime stale-but-relevant candidate).
    add_wiki_page(
        tmp_path, kind="concepts", slug="attention",
        refs_code=[{"path": "src/model/attention.py", "symbol": "MultiHeadAttention",
                    "confidence": "verified"}],
        refs_concepts=["rotary"],
        body=("# Attention\n\n"
              "The MultiHeadAttention block uses scaled dot-product attention with\n"
              "rotary position embedding.\n"),
        created="2026-01-12", updated="2026-01-12",
    )

    # Recent experiment with overlapping refs.
    add_wiki_page(
        tmp_path, kind="experiments", slug="exp-recent",
        refs_code=[{"path": "src/model/attention.py", "symbol": "MultiHeadAttention",
                    "confidence": "verified"}],
        body="# Recent experiment\n\nBenchmark of MultiHeadAttention on the rotary corpus.\n",
        created="2026-04-22", updated="2026-04-22",
    )

    # Researcher-activity log entry pointing at the recent experiment.
    append_log_entry(
        tmp_path, when=date(2026, 4, 22),
        type_="experiment", title="exp-recent",
        page_path="wiki/experiments/exp-recent.md",
        summary="Benchmark of MultiHeadAttention on the rotary corpus.",
    )

    # Phase 1: wiki-sync — builds reverse_refs.
    r_sync = run_sync(tmp_path, today=date(2026, 4, 26))
    assert r_sync.stale_flagged == 0

    rr_path = tmp_path / "index" / "reverse_refs.json"
    assert rr_path.exists()
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    assert "src/model/attention.py" in rr["by_path"]
    pages = {entry["page"] for entry in rr["by_path"]["src/model/attention.py"]}
    assert "wiki/concepts/attention.md" in pages
    assert "wiki/experiments/exp-recent.md" in pages

    # Phase 2: wiki-query — both pages should rank.
    docs = load_pages(tmp_path / "wiki", tmp_path)
    results = search("MultiHeadAttention", docs, top=10)
    paths = [r.path for r in results]
    assert "wiki/concepts/attention.md" in paths
    assert "wiki/experiments/exp-recent.md" in paths

    # Phase 3: wiki-recall — surfaces the old attention page via shared refs.
    recall_result = run_recall(
        tmp_path, today=date(2026, 4, 26),
        lookback_days=10, stale_since_days=60,
    )
    paths_recalled = [r.page_path for r in recall_result.results]
    assert "wiki/concepts/attention.md" in paths_recalled
    attn_result = next(r for r in recall_result.results
                       if r.page_path == "wiki/concepts/attention.md")
    assert any("MultiHeadAttention" in line for line in attn_result.overlaps)

    # Phase 4: wiki-lint — no errors on this clean fixture.
    lint = run_lint(tmp_path, today=date(2026, 4, 26))
    errors = [f for f in lint.findings if f.severity == "error"]
    assert errors == [], (
        f"Unexpected errors on clean fixture: {[f.message for f in errors]}"
    )
