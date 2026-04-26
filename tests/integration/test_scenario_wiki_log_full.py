"""S5 — End-to-end wiki-log CLI flow as the LLM would drive it.

Simulates the LLM's conversational pass *without* an LLM: we hand-write
the payload that the LLM would have assembled after talking to the
researcher (section answers, approved refs, summary). Exercises the
4 read-only commands plus `run` and asserts all downstream side
effects: entry file, log.md append, index.md update, bidirectional
back-ref, concept stub, questions.md append.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

from researchwiki.sync import run_sync

from tests.integration._helpers import (
    add_src_file,
    add_wiki_page,
    bootstrap_workspace,
)


def _run_cli(repo: Path, *args: str, stdin: str | None = None) -> dict:
    """Invoke `python -m researchwiki log <args...>` and return parsed JSON."""
    cmd = [sys.executable, "-m", "researchwiki", "log", *args]
    proc = subprocess.run(
        cmd, cwd=str(repo), capture_output=True, text=True,
        input=stdin, timeout=15,
    )
    assert proc.returncode == 0, (
        f"wiki-log {args} failed: rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def test_scenario_wiki_log_full_experiment_flow(tmp_path: Path):
    bootstrap_workspace(tmp_path, today=date(2026, 4, 22))
    add_src_file(tmp_path, "src/trainer.py",
                 "class Trainer:\n    def train_one_epoch(self, x):\n        return x\n")
    # Need signatures.json so the symbol auto-link finds Trainer.train_one_epoch.
    run_sync(tmp_path, today=date(2026, 4, 22))

    # Pre-existing experiment for back-ref testing.
    add_wiki_page(
        tmp_path, kind="experiments", slug="exp-2026-04-22-bs128",
        body="Earlier run of the same setup.\n",
        created="2026-04-22", updated="2026-04-22",
    )

    # Phase 1 — LLM calls `inspect` to learn template + path + sections.
    insp = _run_cli(
        tmp_path, "inspect", "--type", "experiment",
        "--title", "lr-sweep-bs256", "--today", "2026-04-23",
        "--session-id", "2026-04-23-s3", "--git-ref", "5a3f9e2",
    )
    assert insp["entry_path"].endswith("wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md")
    assert insp["signatures_available"] is True
    section_titles = [s["title"] for s in insp["template"]["sections"]]
    assert "가설" in section_titles and "관련 코드" in section_titles
    auto_link = insp["template"]["template_directives"]["auto_link"]
    assert auto_link["experiments"]["link_bidirectional"] is True

    # Phase 2 — LLM extracts identifier tokens from researcher's prose,
    # asks `lookup-symbols` which ones are in the index.
    sym = _run_cli(
        tmp_path, "lookup-symbols",
        "--tokens", "Trainer,train_one_epoch,bs,lr,grad,val_loss",
    )
    by_token = {m["token"]: m for m in sym}
    assert by_token["Trainer"]["matched"] is True
    assert by_token["train_one_epoch"]["matched"] is True
    assert by_token["bs"]["matched"] is False
    assert by_token["val_loss"]["matched"] is False

    # Phase 3 — LLM finds prior experiment IDs mentioned in 셋업.
    exp = _run_cli(
        tmp_path, "find-pages", "--kind", "experiments",
        "--ids", "exp-2026-04-22-bs128,exp-2026-04-21-missing",
    )
    by_id = {m["id"]: m for m in exp}
    assert by_id["exp-2026-04-22-bs128"]["matched"] is True
    assert by_id["exp-2026-04-21-missing"]["matched"] is False

    # Phase 4 — LLM assembles the payload (after researcher approval) and
    # invokes `run`.
    payload = {
        "type": "experiment",
        "title": "lr-sweep-bs256",
        "today": "2026-04-23",
        "session_id": "2026-04-23-s3",
        "git_ref": "5a3f9e2",
        "section_answers": {
            "가설": "batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것",
            "셋업": "exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일",
            "결과": "3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.",
            "관찰": "NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐",
            "관련 코드": "trainer.py 메인 루프, 특히 train_one_epoch",
        },
        "approved_refs": {
            "code": [{"path": "src/trainer.py", "symbol": "train_one_epoch",
                      "confidence": "verified"}],
            "experiments": ["exp-2026-04-22-bs128"],
            "concepts": [],
            "papers": [],
        },
        "approved_stubs": [
            {"slug": "rotary-embedding", "from_phrase": "rotary embedding"},
        ],
        "questions": [
            {"question": "왜 bs=256, lr=3e-4 조합에서 NaN이 발생했는가?",
             "context": "관찰 섹션에서 분리. grad norm 단조 증가 사실은 기록됨. 원인 귀속은 로그로 확정되지 않음."},
        ],
        "summary_line": "batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것",
        "authored_by": "hybrid",
        "extra_frontmatter": {"run_duration": "2h 14m", "seed": [1, 2, 3]},
    }
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = _run_cli(tmp_path, "run", "--payload", str(payload_file))

    # Entry written.
    entry_rel = "wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md"
    assert result["entry_path"].endswith(entry_rel)
    assert result["log_md_appended"] is True
    assert result["index_md_updated"] is True
    assert result["backrefs_added"] == 1
    assert result["questions_appended"] == 1
    assert len(result["stubs_created"]) == 1

    entry = (tmp_path / entry_rel).read_text(encoding="utf-8")
    parts = entry.split("---", 2)
    fm = yaml.safe_load(parts[1])
    assert fm["type"] == "experiment"
    assert fm["created"] == "2026-04-23"
    assert fm["git_ref"] == "5a3f9e2"
    assert fm["seed"] == [1, 2, 3]
    assert fm["refs"]["code"][0]["symbol"] == "train_one_epoch"
    assert fm["refs"]["experiments"] == ["exp-2026-04-22-bs128"]
    assert "## 가설" in parts[2]
    assert "batch size 256" in parts[2]

    # log.md picked up the block.
    log_text = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "log | experiment | lr-sweep-bs256" in log_text

    # index.md insertion.
    idx_text = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "## Experiments" in idx_text
    assert f"[lr-sweep-bs256](experiments/exp-2026-04-23-lr-sweep-bs256.md)" in idx_text

    # Bidirectional back-ref on the prior experiment's frontmatter.
    prior = (tmp_path / "wiki" / "experiments" / "exp-2026-04-22-bs128.md") \
        .read_text(encoding="utf-8")
    prior_fm = yaml.safe_load(prior.split("---", 2)[1])
    assert "exp-2026-04-23-lr-sweep-bs256" in prior_fm["refs"]["experiments"]
    # P3 — body untouched.
    assert "Earlier run of the same setup." in prior

    # Concept stub created with seeded_by tag (for lint orphan grace period).
    stub = (tmp_path / "wiki" / "concepts" / "rotary-embedding.md") \
        .read_text(encoding="utf-8")
    stub_fm = yaml.safe_load(stub.split("---", 2)[1])
    assert stub_fm["seeded_by"] == "wiki-log"
    assert stub_fm["seed_context"]["from_phrase"] == "rotary embedding"
    assert "Stub created by wiki-log" in stub.split("---", 2)[2]

    # questions.md got the P8-route-c entry.
    q_text = (tmp_path / "wiki" / "questions.md").read_text(encoding="utf-8")
    assert "from wiki-log" in q_text
    assert "NaN이 발생했는가" in q_text
    assert "**Status:** open" in q_text


def test_scenario_wiki_log_collision_refused(tmp_path: Path):
    """If the entry path already exists, `run` refuses (exit 2) — no
    silent overwrite. The LLM's contract is to detect collision via
    `inspect.collision` first, but the CLI guards as well."""
    bootstrap_workspace(tmp_path, today=date(2026, 4, 22))
    target = tmp_path / "wiki" / "experiments" / "exp-2026-04-23-foo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\nschema_version: 1\ntype: experiment\n---\nbody\n",
                      encoding="utf-8")

    payload = {
        "type": "experiment", "title": "foo", "today": "2026-04-23",
        "session_id": "s1",
        "section_answers": {"가설": "x", "셋업": "y", "결과": "z",
                            "관찰": "w", "관련 코드": "v"},
        "summary_line": "x", "authored_by": "hybrid",
    }
    payload_file = tmp_path / "p.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    cmd = [sys.executable, "-m", "researchwiki", "log", "run",
           "--payload", str(payload_file)]
    proc = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True)
    assert proc.returncode == 2
    assert "already exists" in proc.stderr
