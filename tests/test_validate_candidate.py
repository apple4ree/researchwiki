"""Tests for `validate_candidate` (conversation-as-source v2 flow)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from researchwiki.init import run_init
from researchwiki.log import (
    CandidateDraft,
    _slugify_concept,
    validate_candidate,
)
from researchwiki.sync import run_sync


def _silent(_msg: str) -> None:
    pass


def _bootstrap(tmp_path: Path) -> Path:
    run_init(
        tmp_path, mode="new", language="ko", deepscan_tool="understand-anything",
        prompt_fn=lambda _: "y", display_fn=_silent,
        auto_confirm=True, today=date(2026, 4, 22),
    )
    return tmp_path


def _add_src(tmp_path: Path, rel: str, content: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _draft(**overrides) -> CandidateDraft:
    base = dict(
        type="experiment",
        title="lr-sweep-bs256",
        today="2026-04-23",
        session_id="2026-04-23-s3",
        section_answers={
            "가설": "batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것",
            "셋업": "exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds",
            "결과": "3시드 중 2개는 val_loss 1.24 로 수렴",
            "관찰": "grad norm 이 step 300 부터 단조 증가",
            "관련 코드": "trainer.py train_one_epoch",
        },
        extracted_refs={
            "code_tokens": [],
            "concepts_phrases": [],
            "experiments_ids": [],
            "papers_slugs": [],
        },
    )
    base.update(overrides)
    return CandidateDraft(**base)


# ---- Status: ok ----


def test_validate_clean_draft_returns_ok(tmp_path: Path):
    _bootstrap(tmp_path)
    result = validate_candidate(tmp_path, draft=_draft())
    assert result.status == "ok"
    assert result.issues == []


# ---- Status: needs-review (P8 marker) ----


def test_validate_p8_marker_yields_review(tmp_path: Path):
    _bootstrap(tmp_path)
    draft = _draft(section_answers={
        "가설": "test",
        "셋업": "test",
        "결과": "3 seeds out of 3 reached val_loss 1.24",
        "관찰": "NaN 은 lr 이 너무 높아서 발생했을 것이다",
        "관련 코드": "trainer.py",
    })
    result = validate_candidate(tmp_path, draft=draft)
    assert result.status == "needs-review"
    p8 = [i for i in result.issues if i["kind"] == "p8-marker"]
    assert len(p8) >= 1
    assert all(i["section"] == "관찰" for i in p8)


# ---- Status: fatal (missing required) ----


def test_validate_missing_required_section_is_fatal(tmp_path: Path):
    _bootstrap(tmp_path)
    draft = _draft(section_answers={
        "가설": "test",
        "셋업": "",            # missing required
        "결과": "test",
        "관찰": "test",
        "관련 코드": "test",
    })
    result = validate_candidate(tmp_path, draft=draft)
    assert result.status == "fatal"
    missing = [i for i in result.issues if i["kind"] == "missing-required"]
    assert any(i["section"] == "셋업" for i in missing)


# ---- Status: fatal (collision) ----


def test_validate_path_collision_is_fatal(tmp_path: Path):
    _bootstrap(tmp_path)
    target = tmp_path / "wiki" / "experiments" / "exp-2026-04-23-lr-sweep-bs256.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\nschema_version: 1\ntype: experiment\n---\n", encoding="utf-8")
    result = validate_candidate(tmp_path, draft=_draft())
    assert result.status == "fatal"
    assert result.collision is True
    assert any(i["kind"] == "collision" for i in result.issues)


# ---- Ref resolution ----


def test_validate_resolves_code_tokens(tmp_path: Path):
    _bootstrap(tmp_path)
    _add_src(tmp_path, "src/trainer.py",
             "class Trainer:\n    def train_one_epoch(self, x):\n        return x\n")
    run_sync(tmp_path, today=date(2026, 4, 22))
    draft = _draft(extracted_refs={
        "code_tokens": ["Trainer", "train_one_epoch", "no_such_thing"],
        "concepts_phrases": [], "experiments_ids": [], "papers_slugs": [],
    })
    result = validate_candidate(tmp_path, draft=draft)
    code = result.ref_resolution["code"]
    by_token = {c["token"]: c for c in code}
    assert by_token["Trainer"]["matched"]
    assert by_token["train_one_epoch"]["matched"]
    assert not by_token["no_such_thing"]["matched"]
    # Unresolved → review-level issue, but not fatal alone
    assert any(
        i["kind"] == "ref-unresolved" and i["token"] == "no_such_thing"
        for i in result.issues
    )
    assert result.status == "needs-review"


def test_validate_concept_stub_candidates(tmp_path: Path):
    _bootstrap(tmp_path)
    draft = _draft(extracted_refs={
        "code_tokens": [],
        "concepts_phrases": ["rotary embedding", "Flash Attention"],
        "experiments_ids": [], "papers_slugs": [],
    })
    result = validate_candidate(tmp_path, draft=draft)
    concepts = result.ref_resolution["concepts"]
    by_phrase = {c["phrase"]: c for c in concepts}
    assert by_phrase["rotary embedding"]["slug"] == "rotary-embedding"
    assert by_phrase["rotary embedding"]["stub_candidate"]
    assert by_phrase["Flash Attention"]["slug"] == "flash-attention"
    stub_issues = [i for i in result.issues if i["kind"] == "stub-candidate"]
    assert len(stub_issues) == 2


def test_validate_resolves_experiment_ids(tmp_path: Path):
    _bootstrap(tmp_path)
    prior = tmp_path / "wiki" / "experiments" / "exp-2026-04-22-bs128.md"
    prior.write_text("---\nschema_version: 1\ntype: experiment\n---\nbody\n",
                     encoding="utf-8")
    draft = _draft(extracted_refs={
        "code_tokens": [],
        "concepts_phrases": [],
        "experiments_ids": ["exp-2026-04-22-bs128", "exp-2099-12-31-future"],
        "papers_slugs": [],
    })
    result = validate_candidate(tmp_path, draft=draft)
    exps = result.ref_resolution["experiments"]
    by_id = {e["id"]: e for e in exps}
    assert by_id["exp-2026-04-22-bs128"]["matched"]
    assert not by_id["exp-2099-12-31-future"]["matched"]


# ---- Slug computation ----


def test_slugify_concept_basic():
    assert _slugify_concept("rotary embedding") == "rotary-embedding"
    assert _slugify_concept("Flash Attention") == "flash-attention"
    assert _slugify_concept("KV cache") == "kv-cache"


def test_slugify_strips_articles():
    assert _slugify_concept("the rotary embedding") == "rotary-embedding"
    assert _slugify_concept("a transformer block") == "transformer-block"


def test_slugify_drops_trailing_s_for_ascii():
    assert _slugify_concept("rotary embeddings") == "rotary-embedding"
    assert _slugify_concept("attention layers") == "attention-layer"
    # "ss" should not be reduced to "s"
    assert _slugify_concept("loss") == "loss"


def test_slugify_preserves_korean():
    # We don't slugify Korean phrases aggressively; preserve characters.
    out = _slugify_concept("어텐션 레이어")
    assert "어텐션" in out
    assert "-" in out


# ---- Mixed scenario ----


def test_validate_mixed_issues_yields_review(tmp_path: Path):
    """A draft with P8 marker AND ref-unresolved AND stub candidate but
    no fatal issues should be needs-review."""
    _bootstrap(tmp_path)
    _add_src(tmp_path, "src/x.py", "class Foo:\n    pass\n")
    run_sync(tmp_path, today=date(2026, 4, 22))
    draft = _draft(
        section_answers={
            "가설": "test",
            "셋업": "test",
            "결과": "test",
            "관찰": "lr 이 높아서 발생했을 것",
            "관련 코드": "Foo",
        },
        extracted_refs={
            "code_tokens": ["Foo", "DoesNotExist"],
            "concepts_phrases": ["new concept"],
            "experiments_ids": [],
            "papers_slugs": [],
        },
    )
    result = validate_candidate(tmp_path, draft=draft)
    assert result.status == "needs-review"
    kinds = {i["kind"] for i in result.issues}
    assert "p8-marker" in kinds
    assert "ref-unresolved" in kinds
    assert "stub-candidate" in kinds
