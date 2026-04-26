"""Unit tests for wiki-log mechanical core (`src/researchwiki/log.py`).

These tests cover the deterministic surface only — template parsing,
path computation, signature/page lookups, amend window, and the atomic
`run_log` write phase. The conversational layer is the LLM's job and
is not tested here.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from researchwiki.init import run_init
from researchwiki.log import (
    LogPayload,
    find_amend_target,
    find_pages,
    inspect_template,
    lookup_code_symbols,
    run_log,
)
from researchwiki.sync import run_sync


def _silent(_msg: str) -> None:
    pass


def _bootstrap(tmp_path: Path, today: date = date(2026, 4, 26)) -> Path:
    run_init(
        tmp_path, mode="new", language="ko", deepscan_tool="understand-anything",
        prompt_fn=lambda _: "y", display_fn=_silent,
        auto_confirm=True, today=today,
    )
    return tmp_path


def _add_src(tmp_path: Path, rel: str, content: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------
# inspect_template
# ---------------------------------------------------------------------


def test_inspect_experiment_returns_template_meta(tmp_path: Path):
    _bootstrap(tmp_path)
    result = inspect_template(
        tmp_path, type="experiment", title="lr-sweep-bs256",
        today=date(2026, 4, 23), session_id="2026-04-23-s3",
    )
    assert result.template.type == "experiment"
    titles = [s.title for s in result.template.sections]
    # KO templates ship by default; expect 가설/셋업/결과/관찰/관련 코드 etc.
    assert "가설" in titles
    assert "셋업" in titles
    assert "결과" in titles
    required = {s.title for s in result.template.sections if s.required}
    assert "가설" in required and "관련 코드" in required
    optional = {s.title for s in result.template.sections if not s.required}
    assert "다음 단계" in optional or "실패 양상" in optional

    assert result.entry_path.name == "exp-2026-04-23-lr-sweep-bs256.md"
    assert result.entry_path.parent.name == "experiments"
    assert result.placeholder_values["DATE"] == "2026-04-23"
    assert result.placeholder_values["SESSION_ID"] == "2026-04-23-s3"
    assert result.placeholder_values["TITLE"] == "lr-sweep-bs256"
    assert not result.signatures_available  # haven't run sync
    assert not result.collision

    # Template directives carry auto_link rules.
    auto = result.template.template_directives.get("auto_link", {})
    assert auto.get("code", {}).get("enabled") is True
    assert auto.get("experiments", {}).get("link_bidirectional") is True


def test_inspect_paper_decision_free_paths(tmp_path: Path):
    _bootstrap(tmp_path)
    today = date(2026, 5, 1)
    paper = inspect_template(tmp_path, type="paper", title="vaswani-2017", today=today)
    assert paper.entry_path.name == "vaswani-2017.md"
    assert paper.entry_path.parent.name == "papers"
    assert paper.placeholder_values["PAPER_ID"] == "vaswani-2017"

    decision = inspect_template(tmp_path, type="decision", title="adopt-postgres", today=today)
    assert decision.entry_path.name == "adopt-postgres.md"
    assert decision.entry_path.parent.name == "decisions"
    assert decision.placeholder_values["DECISION_ID"] == "adopt-postgres"

    free = inspect_template(tmp_path, type="free", title="quick-thought", today=today)
    assert free.entry_path.name == "2026-05-01-quick-thought.md"
    assert free.entry_path.parent.name == "notes"


def test_inspect_signature_available_after_sync(tmp_path: Path):
    _bootstrap(tmp_path)
    _add_src(tmp_path, "src/x.py", "class Foo:\n    pass\n")
    run_sync(tmp_path, today=date(2026, 4, 26))
    result = inspect_template(tmp_path, type="experiment", title="z",
                              today=date(2026, 4, 26))
    assert result.signatures_available is True


def test_inspect_collision_when_path_exists(tmp_path: Path):
    _bootstrap(tmp_path)
    target = tmp_path / "wiki" / "experiments" / "exp-2026-04-23-foo.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\n---\nbody\n", encoding="utf-8")
    result = inspect_template(tmp_path, type="experiment", title="foo",
                              today=date(2026, 4, 23))
    assert result.collision is True


def test_inspect_unknown_type_raises(tmp_path: Path):
    _bootstrap(tmp_path)
    with pytest.raises(ValueError):
        inspect_template(tmp_path, type="garbage", title="x")


# ---------------------------------------------------------------------
# lookup_code_symbols
# ---------------------------------------------------------------------


def test_lookup_returns_unmatched_when_no_index(tmp_path: Path):
    _bootstrap(tmp_path)
    matches = lookup_code_symbols(tmp_path, tokens=["Foo", "bar"])
    assert all(not m.matched for m in matches)


def test_lookup_matches_after_sync(tmp_path: Path):
    _bootstrap(tmp_path)
    _add_src(tmp_path, "src/trainer.py",
             "class Trainer:\n    def train_one_epoch(self, x):\n        return x\n")
    run_sync(tmp_path, today=date(2026, 4, 26))
    matches = lookup_code_symbols(
        tmp_path,
        tokens=["Trainer", "train_one_epoch", "Trainer.train_one_epoch",
                "src/trainer.py", "no_such_thing"],
    )
    by_token = {m.token: m for m in matches}
    assert by_token["Trainer"].matched and by_token["Trainer"].confidence == "verified"
    assert by_token["train_one_epoch"].matched
    assert by_token["Trainer.train_one_epoch"].matched
    assert by_token["Trainer.train_one_epoch"].parent == "Trainer"
    assert by_token["src/trainer.py"].matched
    assert by_token["src/trainer.py"].path == "src/trainer.py"
    assert not by_token["no_such_thing"].matched


def test_lookup_ambiguous_token_returns_unmatched(tmp_path: Path):
    """Two symbols with the same name in different files → ambiguous."""
    _bootstrap(tmp_path)
    _add_src(tmp_path, "src/a.py", "def helper():\n    return 1\n")
    _add_src(tmp_path, "src/b.py", "def helper():\n    return 2\n")
    run_sync(tmp_path, today=date(2026, 4, 26))
    matches = lookup_code_symbols(tmp_path, tokens=["helper"])
    assert not matches[0].matched


# ---------------------------------------------------------------------
# find_pages
# ---------------------------------------------------------------------


def test_find_pages_concepts_and_experiments(tmp_path: Path):
    _bootstrap(tmp_path)
    (tmp_path / "wiki" / "concepts" / "rotary-embedding.md").write_text(
        "---\nschema_version: 1\ntype: concept\n---\nbody\n", encoding="utf-8",
    )
    (tmp_path / "wiki" / "experiments" / "exp-2026-04-22-bs128.md").write_text(
        "---\nschema_version: 1\ntype: experiment\n---\nbody\n", encoding="utf-8",
    )
    matches = find_pages(tmp_path, kind="concepts",
                         ids=["rotary-embedding", "missing"])
    by_id = {m.id: m for m in matches}
    assert by_id["rotary-embedding"].matched
    assert by_id["rotary-embedding"].path == "wiki/concepts/rotary-embedding.md"
    assert not by_id["missing"].matched

    exp_matches = find_pages(tmp_path, kind="experiments",
                             ids=["exp-2026-04-22-bs128"])
    assert exp_matches[0].matched


# ---------------------------------------------------------------------
# find_amend_target
# ---------------------------------------------------------------------


def test_find_amend_target_within_window(tmp_path: Path):
    _bootstrap(tmp_path)
    p = tmp_path / "wiki" / "experiments" / "exp-2026-04-23-foo.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    when = datetime(2026, 4, 23, 14, 37)
    p.write_text(
        f"---\nschema_version: 1\ntype: experiment\ncreated: {when.isoformat()}\n"
        "updated: 2026-04-23\n---\n# foo\n\n## 가설\nthing\n",
        encoding="utf-8",
    )
    target = find_amend_target(
        tmp_path, type="experiment", window_hours=24,
        now=when + timedelta(minutes=37),
    )
    assert target is not None
    assert target.path == p
    assert target.age_hours < 1.0
    assert "foo" in target.body_preview


def test_find_amend_target_past_window(tmp_path: Path):
    _bootstrap(tmp_path)
    p = tmp_path / "wiki" / "experiments" / "exp-2026-04-21-old.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    when = datetime(2026, 4, 21, 9, 0)
    p.write_text(
        f"---\nschema_version: 1\ntype: experiment\ncreated: {when.isoformat()}\n"
        "updated: 2026-04-21\n---\n# old\n",
        encoding="utf-8",
    )
    target = find_amend_target(
        tmp_path, type="experiment", window_hours=24,
        now=datetime(2026, 4, 23, 9, 0),
    )
    assert target is None


def test_find_amend_target_no_entries(tmp_path: Path):
    _bootstrap(tmp_path)
    target = find_amend_target(tmp_path, type="experiment",
                                now=datetime(2026, 4, 23))
    assert target is None


# ---------------------------------------------------------------------
# run_log — happy path (experiment)
# ---------------------------------------------------------------------


def _experiment_payload(**overrides) -> LogPayload:
    base = dict(
        type="experiment",
        title="lr-sweep-bs256",
        today="2026-04-23",
        session_id="2026-04-23-s3",
        git_ref="5a3f9e2",
        section_answers={
            "가설": "batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것",
            "셋업": "exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일",
            "결과": "3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.",
            "관찰": "NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐",
            "관련 코드": "trainer.py 메인 루프, 특히 train_one_epoch",
        },
        approved_refs={
            "code": [{"path": "src/trainer.py", "symbol": "train_one_epoch",
                      "confidence": "verified"}],
            "experiments": ["exp-2026-04-22-bs128"],
            "concepts": [],
            "papers": [],
        },
        approved_stubs=[],
        questions=[],
        summary_line="batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것",
        authored_by="hybrid",
        extra_frontmatter={"run_duration": "2h 14m", "seed": [1, 2, 3]},
    )
    base.update(overrides)
    return LogPayload(**base)


def test_run_log_creates_entry_with_all_artifacts(tmp_path: Path):
    _bootstrap(tmp_path)
    # Pre-existing experiment for back-ref test.
    prior = tmp_path / "wiki" / "experiments" / "exp-2026-04-22-bs128.md"
    prior.write_text(
        "---\nschema_version: 1\ntype: experiment\ncreated: 2026-04-22\n"
        "updated: 2026-04-22\nrefs:\n  code: []\n  papers: []\n  concepts: []\n"
        "  experiments: []\n---\nbody\n",
        encoding="utf-8",
    )

    payload = _experiment_payload()
    result = run_log(tmp_path, payload=payload)

    # Entry written
    assert result.entry_path.exists()
    text = result.entry_path.read_text(encoding="utf-8")
    fm_block, _, body = text.partition("\n---\n")[2].partition("\n---\n") if False else (None, None, None)
    # Simpler: split on the second `---` boundary.
    parts = text.split("---", 2)
    assert len(parts) == 3
    fm_data = yaml.safe_load(parts[1])
    assert fm_data["type"] == "experiment"
    assert fm_data["created"] == "2026-04-23"
    assert fm_data["authored_by"] == "hybrid"
    assert fm_data["source_sessions"] == ["2026-04-23-s3"]
    assert fm_data["git_ref"] == "5a3f9e2"
    assert fm_data["run_duration"] == "2h 14m"
    assert fm_data["seed"] == [1, 2, 3]
    refs = fm_data["refs"]
    assert refs["code"][0]["symbol"] == "train_one_epoch"
    assert refs["experiments"] == ["exp-2026-04-22-bs128"]

    # Body has the answers under each required section.
    body = parts[2]
    assert "## 가설" in body
    assert "batch size 256" in body
    assert "## 관련 코드" in body
    # Optional sections that have no answer should be skipped.
    assert "## 다음 단계" not in body

    # log.md got a block.
    log_text = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "## [" in log_text
    assert "log | experiment | lr-sweep-bs256" in log_text
    assert "wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md" in log_text

    # index.md got a link under Experiments.
    idx_text = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "## Experiments" in idx_text
    assert "[lr-sweep-bs256](experiments/exp-2026-04-23-lr-sweep-bs256.md)" in idx_text

    # Bidirectional back-ref on the prior experiment.
    prior_text = prior.read_text(encoding="utf-8")
    prior_fm = yaml.safe_load(prior_text.split("---", 2)[1])
    assert "exp-2026-04-23-lr-sweep-bs256" in prior_fm["refs"]["experiments"]
    assert result.backrefs_added == 1


def test_run_log_idempotent_index_and_log(tmp_path: Path):
    """Re-inserting the same line into index.md should be a no-op."""
    _bootstrap(tmp_path)
    payload = _experiment_payload()
    run_log(tmp_path, payload=payload)
    # Re-call would collide on entry path — instead, simulate the
    # index/log path stays sane on a *different* run.
    payload2 = _experiment_payload(title="another-exp", section_answers={
        "가설": "x", "셋업": "y", "결과": "z", "관찰": "w", "관련 코드": "v",
    }, approved_refs={"code": [], "papers": [], "concepts": [], "experiments": []},
        extra_frontmatter={})
    run_log(tmp_path, payload=payload2)
    idx_text = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
    # Both links present, only one ## Experiments heading.
    assert idx_text.count("## Experiments") == 1
    assert "lr-sweep-bs256" in idx_text
    assert "another-exp" in idx_text


# ---------------------------------------------------------------------
# run_log — concept stub
# ---------------------------------------------------------------------


def test_run_log_creates_concept_stub(tmp_path: Path):
    _bootstrap(tmp_path)
    payload = _experiment_payload(approved_stubs=[
        {"slug": "rotary-embedding", "from_phrase": "rotary embedding"},
    ])
    result = run_log(tmp_path, payload=payload)
    assert len(result.stubs_created) == 1
    stub = tmp_path / "wiki" / "concepts" / "rotary-embedding.md"
    assert stub.exists()
    stub_fm = yaml.safe_load(stub.read_text(encoding="utf-8").split("---", 2)[1])
    assert stub_fm["seeded_by"] == "wiki-log"
    assert stub_fm["seed_context"]["from_phrase"] == "rotary embedding"
    assert stub_fm["seed_context"]["from_entry"] == \
        "wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md"
    body = stub.read_text(encoding="utf-8").split("---", 2)[2]
    assert "Stub created by wiki-log" in body


def test_run_log_skips_existing_stub(tmp_path: Path):
    _bootstrap(tmp_path)
    target = tmp_path / "wiki" / "concepts" / "rotary-embedding.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntype: concept\n---\noriginal body\n", encoding="utf-8")
    payload = _experiment_payload(approved_stubs=[
        {"slug": "rotary-embedding", "from_phrase": "rotary embedding"},
    ])
    result = run_log(tmp_path, payload=payload)
    assert result.stubs_created == []
    # Original body untouched (P3 — wiki-log never overwrites bodies).
    assert "original body" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------
# run_log — questions
# ---------------------------------------------------------------------


def test_run_log_appends_questions(tmp_path: Path):
    _bootstrap(tmp_path)
    payload = _experiment_payload(questions=[
        {"question": "왜 bs=256, lr=3e-4 조합에서 NaN이 발생했는가?",
         "context": "관찰 섹션에서 분리. grad norm 단조 증가 사실은 기록됨."},
    ])
    result = run_log(tmp_path, payload=payload)
    assert result.questions_appended == 1
    q_text = (tmp_path / "wiki" / "questions.md").read_text(encoding="utf-8")
    assert "**Question:**" in q_text
    assert "NaN이 발생했는가" in q_text
    assert "**Status:** open" in q_text
    assert "from wiki-log (wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md)" in q_text


# ---------------------------------------------------------------------
# run_log — validation
# ---------------------------------------------------------------------


def test_run_log_rejects_authored_by_llm(tmp_path: Path):
    _bootstrap(tmp_path)
    payload = _experiment_payload(authored_by="llm")
    with pytest.raises(ValueError, match="forbidden"):
        run_log(tmp_path, payload=payload)


def test_run_log_rejects_blank_required(tmp_path: Path):
    _bootstrap(tmp_path)
    payload = _experiment_payload(section_answers={
        "가설": "", "셋업": "x", "결과": "y", "관찰": "z", "관련 코드": "w",
    })
    with pytest.raises(ValueError, match="required section"):
        run_log(tmp_path, payload=payload)


def test_run_log_rejects_collision(tmp_path: Path):
    _bootstrap(tmp_path)
    payload = _experiment_payload()
    run_log(tmp_path, payload=payload)
    with pytest.raises(FileExistsError):
        run_log(tmp_path, payload=payload)


# ---------------------------------------------------------------------
# Index.md insertion under existing categories
# ---------------------------------------------------------------------


def test_run_log_inserts_under_existing_category(tmp_path: Path):
    _bootstrap(tmp_path)
    idx = tmp_path / "wiki" / "index.md"
    idx.write_text(
        "# wiki/index.md\n\n## Experiments\n- [old](experiments/old.md)\n",
        encoding="utf-8",
    )
    payload = _experiment_payload()
    run_log(tmp_path, payload=payload)
    text = idx.read_text(encoding="utf-8")
    lines = text.splitlines()
    h = lines.index("## Experiments")
    assert lines[h + 1].startswith("- [lr-sweep-bs256]")
    assert "- [old](experiments/old.md)" in lines


# ---------------------------------------------------------------------
# Paper / decision / free-form happy paths
# ---------------------------------------------------------------------


def test_run_log_paper_entry(tmp_path: Path):
    _bootstrap(tmp_path)
    # Inspect first to learn the section titles in KO templates.
    insp = inspect_template(tmp_path, type="paper", title="vaswani-2017",
                            today=date(2026, 5, 1))
    answers = {s.title: f"answer for {s.title}" for s in insp.template.sections
               if s.required}
    payload = LogPayload(
        type="paper", title="vaswani-2017", today="2026-05-01",
        session_id="2026-05-01-s1",
        section_answers=answers,
        summary_line="Attention is all you need.",
        authored_by="hybrid",
    )
    result = run_log(tmp_path, payload=payload)
    assert result.entry_path.name == "vaswani-2017.md"
    assert result.entry_path.parent.name == "papers"


def test_run_log_free_entry_uses_dated_slug(tmp_path: Path):
    _bootstrap(tmp_path)
    insp = inspect_template(tmp_path, type="free", title="quick-thought",
                            today=date(2026, 5, 1))
    answers = {s.title: "x" for s in insp.template.sections if s.required}
    payload = LogPayload(
        type="free", title="quick-thought", today="2026-05-01",
        session_id="s1", section_answers=answers,
        summary_line="quick thought", authored_by="hybrid",
    )
    result = run_log(tmp_path, payload=payload)
    assert result.entry_path.name == "2026-05-01-quick-thought.md"
    assert result.entry_path.parent.name == "notes"
