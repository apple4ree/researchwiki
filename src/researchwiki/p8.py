"""First-pass P8 marker detection.

A regex-based scanner for hedge / causal-without-evidence / intent-attribution
markers in researcher prose. Used by `wiki log validate-candidate` to flag
sections for the LLM to review under the three-route P8 flow.

This is intentionally a *coarse first pass*. False positives are expected
and cheap (the LLM refines or dismisses); false negatives are the real
risk and the patterns below are biased toward over-reporting in the gray
zone (P8 violations slow-poison the wiki, so we err toward asking).

Pattern catalog source: `skills/wiki-log/reference/p8-detection.md` §2-3.
That document is the authoritative reference for what *should* be flagged
(section-by-section risk map, counter-examples, edge cases).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

MarkerKind = Literal[
    "hedge",          # 것 같다 / seems / probably
    "causal",         # X 때문에 / because of (without evidence cited)
    "intent",         # 위해 / was meant to (developer-intent attribution)
    "implication",    # implies / suggests that (in paper Implications sections)
]


@dataclass
class P8Match:
    section: str
    marker: str       # the literal substring matched
    kind: MarkerKind
    start: int        # character offset within the section text
    end: int

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------
# Pattern catalog
# ---------------------------------------------------------------------
#
# Each entry: (pattern, kind). Patterns are case-insensitive for English.
# Korean patterns are case-irrelevant. Word boundaries used where needed
# to reduce false positives on substring matches (e.g., "due to" matches
# "I'm due to leave" — accepted; the LLM dismisses).

_KO_PATTERNS: list[tuple[str, MarkerKind]] = [
    # Hedge endings — speculation / inference verbs
    (r"것\s*같(다|아|네|은데|음)", "hedge"),
    (r"듯\s*(하|보|싶)(다|아|음|네)", "hedge"),
    (r"보(여|이)는데", "hedge"),
    (r"보인다(\s|$|\.)", "hedge"),
    (r"인\s*것\s*같", "hedge"),
    # ~을 것이다 / ~ㄹ 것이다 / ~ 것이다 — speculation-future copula.
    # Common P8 trap in observation sections ("발생했을 것이다",
    # "수렴할 것이다", "줄어들 것이다"). The leading space variant
    # catches the case where the future-marker ㄹ is fused into the
    # preceding syllable (e.g., 발생할 것이다 — `할`).
    (r"(을|ㄹ)\s*것\s*이(다|었|네|에요|에다)", "hedge"),
    (r"\s것\s*이(다|었|네|에요|에다)", "hedge"),
    (r"(을|ㄹ)\s*것\s*같", "hedge"),
    # Speculation verbs (literal)
    (r"추정(된다|되|함)", "hedge"),
    (r"짐작(된다|되|함)", "hedge"),
    (r"추측(된다|되|함)", "hedge"),
    # Causal — gray-zone; flag and let LLM judge based on whether
    # evidence is cited adjacent.
    (r"때문(에|이|이다)", "causal"),
    (r"덕분(에|이다)", "causal"),
    (r"인해(\s|$|\.)", "causal"),
    (r"로\s*인\s*해", "causal"),
    # ~아서/어서/여서 + result verb (발생/생기/일어나/터지/터짐 등) —
    # often hidden causal claim. Narrow window to reduce false positives.
    (r"(아|어|여)서\s+\S{0,10}(발생|일어나|생기|터지|터짐|망가|죽|폭주|튀)", "causal"),
    # Intent attribution
    (r"의도(는|한|적인)", "intent"),
    (r"\w+려고\s+(한\s*것|했|만든|쓴|짠)", "intent"),
    (r"위(해|해서)\s+(만든|쓴|작성|짠)", "intent"),
    (r"위(해|해서)\s+\w+(된|한)\s*것", "intent"),
]

_EN_PATTERNS: list[tuple[str, MarkerKind]] = [
    # Hedges
    (r"\bseems?\s+(to\s+|like\s+)?", "hedge"),
    (r"\bappears?\s+to\b", "hedge"),
    (r"\blooks?\s+like\b", "hedge"),
    (r"\bprobably\b", "hedge"),
    (r"\blikely\b", "hedge"),
    (r"\bpresumably\b", "hedge"),
    (r"\bapparently\b", "hedge"),
    (r"\bsuggests?\s+that\b", "implication"),
    (r"\bimplies?\b", "implication"),
    (r"\bperhaps\b", "hedge"),
    (r"\bmight\s+be\b", "hedge"),
    # Causal without evidence — gray
    (r"\bbecause\s+of\b", "causal"),
    (r"\bdue\s+to\b", "causal"),
    (r"\bcaused\s+by\b", "causal"),
    (r"\bowing\s+to\b", "causal"),
    # Intent attribution
    (r"\bwas\s+(meant|designed|intended)\s+to\b", "intent"),
    (r"\bin\s+order\s+to\b", "intent"),
    (r"\bso\s+as\s+to\b", "intent"),
]


# ---------------------------------------------------------------------
# Pre-compile
# ---------------------------------------------------------------------


_COMPILED: list[tuple[re.Pattern, MarkerKind]] = [
    *((re.compile(p), k) for p, k in _KO_PATTERNS),
    *((re.compile(p, re.IGNORECASE), k) for p, k in _EN_PATTERNS),
]


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def scan_section(section_title: str, text: str) -> list[P8Match]:
    """Return all P8 marker matches inside `text`. Empty list if clean.

    Each match is a P8Match; the LLM consumer turns this into the 3-route
    flow per `reference/p8-detection.md` §1.
    """
    if not text:
        return []
    out: list[P8Match] = []
    for pattern, kind in _COMPILED:
        for m in pattern.finditer(text):
            out.append(P8Match(
                section=section_title,
                marker=m.group(0),
                kind=kind,
                start=m.start(),
                end=m.end(),
            ))
    # Deduplicate by (start, end) — overlapping patterns can both fire.
    seen: set[tuple[int, int]] = set()
    deduped: list[P8Match] = []
    for m in sorted(out, key=lambda x: (x.start, -x.end)):
        if (m.start, m.end) in seen:
            continue
        seen.add((m.start, m.end))
        deduped.append(m)
    return deduped


def scan_section_answers(section_answers: dict[str, str]) -> list[P8Match]:
    """Apply scan_section to every entry in a section_answers dict."""
    out: list[P8Match] = []
    for title, text in section_answers.items():
        out.extend(scan_section(title, text or ""))
    return out
