"""End-to-end test for `wiki-sync` v0.1.

Builds a minimal ResearchWiki workspace in tmp_path with one Python
file, one JSON config, one non-wiki Markdown file, and one wiki page
that references a removed symbol. Runs `run_sync` and verifies all
three outputs (signatures.json, reverse_refs.json, snapshot) plus
the stale-link side effects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchwiki.sync import run_sync


def _build_fixture(root: Path) -> None:
    """Create a tiny mock target ResearchWiki repo."""
    # CLAUDE.md and config — bootstrap markers (their content doesn't matter for
    # wiki-sync v0.1; the orchestrator does not read them yet).
    (root / "CLAUDE.md").write_text("# Constitution placeholder\n", encoding="utf-8")
    (root / "research-wiki.config.yaml").write_text("schema_version: 1\n", encoding="utf-8")

    # Source code
    (root / "src").mkdir()
    (root / "src" / "trainer.py").write_text(
        "class Trainer:\n"
        "    def train_one_epoch(self, loader):\n"
        "        return {}\n"
        "\n"
        "def helper(x):\n"
        "    return x\n",
        encoding="utf-8",
    )

    # Config
    (root / "configs").mkdir()
    (root / "configs" / "default.json").write_text(
        '{"batch_size": 256, "lr": 0.0003}\n',
        encoding="utf-8",
    )

    # Non-wiki markdown
    (root / "docs").mkdir()
    (root / "docs" / "intro.md").write_text(
        "# Intro\n\n## Setup\n",
        encoding="utf-8",
    )

    # Wiki layer — one concept page that references an existing symbol and
    # a removed symbol (LegacyTrainer is not in src/).
    wiki = root / "wiki"
    (wiki / "concepts").mkdir(parents=True)
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
        "    - path: src/trainer.py\n"
        "      symbol: LegacyTrainer\n"
        "      confidence: verified\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "\n"
        "# Training loop\n"
        "\n"
        "Body content. Should NOT be modified by wiki-sync.\n",
        encoding="utf-8",
    )
    (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
    (wiki / "questions.md").write_text("# Questions\n", encoding="utf-8")
    (wiki / "discrepancies.md").write_text("# Discrepancies\n", encoding="utf-8")
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")


def test_end_to_end(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_sync(tmp_path)

    # --- signatures.json ---
    sig_path = tmp_path / "index" / "signatures.json"
    assert sig_path.exists()
    sig = json.loads(sig_path.read_text(encoding="utf-8"))

    sym_index = {(s["path"], s["name"]): s for s in sig["symbols"]}

    # Python: class + method + function.
    assert ("src/trainer.py", "Trainer") in sym_index
    assert sym_index[("src/trainer.py", "Trainer")]["kind"] == "class"
    assert ("src/trainer.py", "train_one_epoch") in sym_index
    assert sym_index[("src/trainer.py", "train_one_epoch")]["parent"] == "Trainer"
    assert ("src/trainer.py", "helper") in sym_index

    # JSON: top-level keys.
    assert ("configs/default.json", "batch_size") in sym_index
    assert ("configs/default.json", "lr") in sym_index

    # Markdown (non-wiki) headings.
    assert ("docs/intro.md", "Intro") in sym_index
    assert ("docs/intro.md", "Setup") in sym_index

    # Wiki Markdown — should NOT be in signatures (interpretation layer).
    assert not any(s["path"].startswith("wiki/") for s in sig["symbols"])

    # --- reverse_refs.json ---
    rr_path = tmp_path / "index" / "reverse_refs.json"
    assert rr_path.exists()
    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    by_path = rr["by_path"]
    assert "src/trainer.py" in by_path
    refs = by_path["src/trainer.py"]
    pages = {r["page"]: r["symbols"] for r in refs}
    # Wiki page declared two refs against src/trainer.py
    assert "wiki/concepts/training-loop.md" in pages
    assert set(pages["wiki/concepts/training-loop.md"]) == {"Trainer", "LegacyTrainer"}

    # --- Stale-link pass ---
    assert result.stale_flagged == 1  # only LegacyTrainer (Trainer exists)
    assert result.questions_appended == 1

    # Frontmatter mutation: only the LegacyTrainer entry should be marked.
    page_text = (tmp_path / "wiki/concepts/training-loop.md").read_text(encoding="utf-8")
    assert "stale: true" in page_text
    # Body untouched.
    assert "Body content. Should NOT be modified by wiki-sync." in page_text

    # questions.md got a new entry.
    q_text = (tmp_path / "wiki/questions.md").read_text(encoding="utf-8")
    assert "from wiki-sync" in q_text
    assert "LegacyTrainer" in q_text

    # --- Snapshot ---
    snap = result.snapshot_path
    assert snap.exists()
    assert snap.parent == tmp_path / "index" / "snapshots"
    snap_text = snap.read_text(encoding="utf-8")
    assert "# Sync snapshot" in snap_text
    assert "## File tree" in snap_text
    assert "## Modules" in snap_text
    assert "## Changes since previous snapshot" in snap_text


def test_idempotent_re_run(tmp_path: Path):
    """A second sync against the same state should not append a new
    question to wiki/questions.md (the stale ref is already flagged)."""
    _build_fixture(tmp_path)
    first = run_sync(tmp_path)
    assert first.questions_appended == 1

    second = run_sync(tmp_path)
    assert second.stale_flagged == 0  # already flagged in frontmatter
    assert second.questions_appended == 0  # idempotent on questions.md


def test_no_stale_check_skips_wiki_edits(tmp_path: Path):
    _build_fixture(tmp_path)
    result = run_sync(tmp_path, no_stale_check=True)

    page_text = (tmp_path / "wiki/concepts/training-loop.md").read_text(encoding="utf-8")
    assert "stale: true" not in page_text

    q_text = (tmp_path / "wiki/questions.md").read_text(encoding="utf-8")
    assert "from wiki-sync" not in q_text

    assert result.stale_flagged == 0
    assert result.questions_appended == 0


def test_signatures_diff_on_second_run(tmp_path: Path):
    _build_fixture(tmp_path)
    run_sync(tmp_path)

    # Add a new symbol; remove one.
    (tmp_path / "src" / "trainer.py").write_text(
        "class Trainer:\n"
        "    def train_one_epoch(self, loader):\n"
        "        return {}\n"
        "    def save_checkpoint(self, path):\n"  # NEW
        "        pass\n"
        "\n"
        # `helper` removed
        "def helper2(x):\n"  # different name
        "    return x\n",
        encoding="utf-8",
    )
    result = run_sync(tmp_path)
    assert result.symbols_added >= 2  # save_checkpoint + helper2
    assert result.symbols_removed >= 1  # helper


def test_repo_without_wiki_runs_clean(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f(): pass\n", encoding="utf-8")
    result = run_sync(tmp_path)
    assert result.signatures_path.exists()
    assert result.stale_flagged == 0
    assert result.questions_appended == 0


def test_missing_repo_raises():
    with pytest.raises(FileNotFoundError):
        run_sync(Path("/no/such/path/exists"))


# ---------- v0.2: rename heuristic ----------


def _v2_fixture(tmp_path: Path):
    """Minimal repo for v0.2 tests."""
    (tmp_path / "CLAUDE.md").write_text("placeholder\n")
    (tmp_path / "research-wiki.config.yaml").write_text("schema_version: 1\n")
    (tmp_path / "src").mkdir()
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    for name in ("log.md", "questions.md", "discrepancies.md", "index.md"):
        (wiki / name).write_text("\n", encoding="utf-8")


def test_rename_heuristic_detects_same_file_similar_signature(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "trainer.py").write_text(
        "class Trainer:\n"
        "    def forward_v1(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    run_sync(tmp_path)  # establish baseline

    # Rename: forward_v1 -> forward at adjacent line, near-identical body.
    (tmp_path / "src" / "trainer.py").write_text(
        "class Trainer:\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    result = run_sync(tmp_path)
    candidates = result.rename_candidates
    assert len(candidates) == 1
    c = candidates[0]
    assert c.removed.name == "forward_v1"
    assert c.added.name == "forward"
    assert c.similarity > 0.80


def test_rename_heuristic_skips_different_files(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "a.py").write_text("def helper(x): return x\n", encoding="utf-8")
    run_sync(tmp_path)
    # Move helper to b.py — different file → should NOT be flagged as rename.
    (tmp_path / "src" / "a.py").write_text("# emptied\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def helper(x): return x\n", encoding="utf-8")
    result = run_sync(tmp_path)
    assert result.rename_candidates == []


def test_rename_heuristic_skips_low_similarity(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text(
        "def short(): pass\n",
        encoding="utf-8",
    )
    run_sync(tmp_path)
    # New function with totally different signature.
    (tmp_path / "src" / "x.py").write_text(
        "def something_completely_unrelated_with_long_name(arg_a, arg_b, arg_c, arg_d): pass\n",
        encoding="utf-8",
    )
    result = run_sync(tmp_path)
    assert result.rename_candidates == []


def test_rename_heuristic_disabled(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text("def forward_v1(x): return x\n", encoding="utf-8")
    run_sync(tmp_path)
    (tmp_path / "src" / "x.py").write_text("def forward(x): return x\n", encoding="utf-8")
    result = run_sync(tmp_path, rename_heuristic=False)
    assert result.rename_candidates == []


def test_rename_heuristic_appears_in_snapshot(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "trainer.py").write_text(
        "def forward_v1(x): return x\n", encoding="utf-8",
    )
    run_sync(tmp_path)
    (tmp_path / "src" / "trainer.py").write_text(
        "def forward(x): return x\n", encoding="utf-8",
    )
    result = run_sync(tmp_path)
    snap_text = result.snapshot_path.read_text(encoding="utf-8")
    assert "## Possible renames (heuristic, [unverified])" in snap_text
    assert "forward_v1" in snap_text
    assert "forward" in snap_text


# ---------- v0.2: nag mechanism ----------


def test_nag_fires_for_old_stale_flags(tmp_path: Path):
    """A stale flag older than nag_after_days should produce a nag message."""
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text("class Real: pass\n", encoding="utf-8")

    # Wiki page with a stale ref that's 30 days old.
    (tmp_path / "wiki" / "concepts" / "p.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/x.py\n"
        "      symbol: Gone\n"
        "      stale: true\n"
        "      stale_detected: '2026-03-27'\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = run_sync(tmp_path, today=date(2026, 4, 26), nag_after_days=7)
    assert result.nag_message is not None
    assert "1" in result.nag_message  # one old flag


def test_nag_silent_for_recent_stale(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text("class Real: pass\n", encoding="utf-8")
    (tmp_path / "wiki" / "concepts" / "p.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/x.py\n"
        "      symbol: Gone\n"
        "      stale: true\n"
        "      stale_detected: '2026-04-25'\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    result = run_sync(tmp_path, today=date(2026, 4, 26), nag_after_days=7)
    # Stale was detected 1 day ago, threshold is 7. No nag.
    assert result.nag_message is None


def test_nag_suppressed_with_no_nag(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text("class Real: pass\n", encoding="utf-8")
    (tmp_path / "wiki" / "concepts" / "p.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "type: concept\n"
        "tags: []\n"
        "refs:\n"
        "  code:\n"
        "    - path: src/x.py\n"
        "      symbol: Gone\n"
        "      stale: true\n"
        "      stale_detected: '2026-03-01'\n"
        "  papers: []\n"
        "  concepts: []\n"
        "  experiments: []\n"
        "authored_by: human\n"
        "source_sessions: []\n"
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    result = run_sync(tmp_path, today=date(2026, 4, 26), no_nag=True)
    assert result.nag_message is None


def test_nag_silent_when_no_stale(tmp_path: Path):
    _v2_fixture(tmp_path)
    (tmp_path / "src" / "x.py").write_text("class Real: pass\n", encoding="utf-8")
    result = run_sync(tmp_path, today=date(2026, 4, 26))
    assert result.nag_message is None


# Need the date import only for v0.2 tests.
from datetime import date  # noqa: E402
