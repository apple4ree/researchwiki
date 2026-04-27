"""Tests for the P8 first-pass marker detector (`researchwiki.p8`)."""

from __future__ import annotations

from researchwiki.p8 import scan_section, scan_section_answers


# ---- Korean ----

def test_ko_hedge_endings():
    matches = scan_section("관찰", "수렴이 되는 것 같다")
    kinds = {m.kind for m in matches}
    assert "hedge" in kinds


def test_ko_speculation_future_copula():
    matches = scan_section("관찰", "NaN 은 lr 이 너무 높아서 발생했을 것이다")
    markers = [m.marker for m in matches]
    kinds = {m.kind for m in matches}
    assert "hedge" in kinds, f"'을 것이다' should flag hedge: {markers}"
    assert "causal" in kinds, f"'아서' + 발생 should flag causal: {markers}"


def test_ko_explicit_speculation_verb():
    matches = scan_section("결과", "병목은 dataloader 로 추정된다")
    assert any(m.kind == "hedge" for m in matches)


def test_ko_intent_attribution():
    matches = scan_section("관련 코드", "이 함수는 메모리를 줄이려고 만든 것이다")
    assert any(m.kind == "intent" for m in matches)


def test_ko_intent_위해():
    matches = scan_section("Method", "레이턴시 줄이기 위해 작성된 코드")
    assert any(m.kind == "intent" for m in matches)


def test_ko_clean_assertion_no_flags():
    """A grounded assertion should not flag (false-positive sanity check)."""
    matches = scan_section("결과", "AdamW 가 SGD 보다 빠르게 수렴한다")
    assert matches == []


def test_ko_hypothesis_section_hedge_acceptable_but_still_detected():
    """Hedge in 가설 is fine BY POLICY (P8 §3 risk-map says low risk),
    but the detector still flags — the LLM is responsible for dismissing
    based on section context."""
    matches = scan_section("가설", "lr 을 낮추면 NaN 이 줄어들 것이다")
    # We do flag (the regex doesn't know the section is 가설)
    assert any(m.kind == "hedge" for m in matches)


# ---- English ----

def test_en_seems():
    matches = scan_section("Observations", "The loss seems to plateau")
    assert any(m.kind == "hedge" for m in matches)


def test_en_causal_due_to():
    matches = scan_section("Observations", "Divergence due to higher lr")
    assert any(m.kind == "causal" for m in matches)


def test_en_implication():
    matches = scan_section("Implications", "This suggests that scaling laws hold")
    assert any(m.kind == "implication" for m in matches)


def test_en_intent_was_meant_to():
    matches = scan_section("Method", "this method was designed to short-circuit caching")
    assert any(m.kind == "intent" for m in matches)


def test_en_clean_grounded_observation():
    matches = scan_section("Results", "val_loss reached 1.24 across 3 seeds")
    assert matches == []


# ---- Multi-section dispatch ----

def test_scan_section_answers_aggregates_across_sections():
    answers = {
        "가설": "AdamW 가 SGD 보다 빠르게 수렴한다",          # clean
        "관찰": "NaN 은 lr 때문에 발생했을 것이다",              # 2 markers
        "다음 단계": "lr=1e-4 로 다시 시도",                    # clean
    }
    matches = scan_section_answers(answers)
    sections = {m.section for m in matches}
    assert sections == {"관찰"}
    assert len(matches) >= 2


def test_overlapping_patterns_dedup():
    """Two patterns matching the same span should produce a single hit."""
    matches = scan_section("관찰", "발생했을 것이다")
    spans = [(m.start, m.end) for m in matches]
    assert len(spans) == len(set(spans)), f"duplicate spans: {spans}"
