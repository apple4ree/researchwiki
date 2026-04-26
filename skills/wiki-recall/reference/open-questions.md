# `wiki-recall` — Open Questions

> Supplementary material for `wiki-recall`. Not loaded at LLM runtime.

---

## 1. Stub exclusion default

**Status:** decided — `wiki-deepscan` and `wiki-log` stubs (`authored_by: llm` or `seeded_by: ...`, with empty body) excluded by default; `--include-stubs` opts in.

Rationale: stub frontmatter is densely populated (especially `wiki-deepscan` graph-seeded ones) but represents no real interpretation to revisit. Including them by default would dominate scoring and bury actually-revisitable pages.

---

## 2. Skill-meta log entry filtering

**Status:** decided — log entries with headers `## [...] from wiki-sync` or `from wiki-lint` are filtered out of the recent-activity corpus.

Rationale: those entries describe wiki-meta events (stale flags surfaced, audit findings appended), not researcher activity. Including them would let the wiki's own automation drive recall scoring.

---

## 3. Recency weighting within the lookback window

**Status:** flat (no decay) in MVP.

A log entry from yesterday and one from 29 days ago contribute equally if both are within `--lookback 30`. Reasonable for short windows; questionable for long ones.

**Proposed:** linear decay — freshest entry weight 1.0, oldest in window 0.3. Defer until use shows real loss.

---

## 4. Cross-skill `--feed-to-wiki-log` mode

**Status:** rejected.

Idea: surface the top result and immediately open `wiki-log` to file a new linked entry.

**Rejected:** keep skills composable but separately invoked. wiki-recall produces pointers; the researcher decides whether to invoke wiki-log next. Coupling the two would obscure the skill boundary.

---

## 5. Ranking ties

**Status:** undefined.

When two pages produce the same score, current behavior is "whichever wins lexicographically". Could be improved (e.g., older `updated:` first — surface most-forgotten pages preferentially).

**Proposed:** ties → older `updated:` first as secondary key. Trivial to implement; defer until first researcher feedback.
