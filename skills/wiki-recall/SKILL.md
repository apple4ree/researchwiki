---
name: wiki-recall
description: Use this skill when the researcher wants to surface wiki pages that they wrote a while ago but that overlap with their recent activity — concept pages, design decisions, or experiment writeups whose frontmatter `refs.{code,concepts,papers,experiments}` overlap with the refs in `wiki/log.md` entries from the recent window. wiki-recall is **read-only** and **does not parse page bodies**; staleness is measured against the page's frontmatter `updated:` field, and "recent activity" is parsed from `wiki/log.md`. Output is a ranked list of pointers with explicit overlap evidence — never a summary of what the surfaced page says (P8). Trigger phrases include "wiki-recall", "오래된 페이지 surfacing", "예전 작업 다시 보자", "최근에 비슷한 거 한 적 있어?", "remind me of related older work", "what did I drop along the way?", "memory refresh". Do not use for query-by-keyword (use `wiki-query`). Do not use for finding all stale pages regardless of relevance (use `wiki-lint`'s orphan check). Do not use to add new entries (use `wiki-log`). Do not use as a substitute for actually reading the surfaced pages — wiki-recall points; the researcher reads.
---

# wiki-recall

> **Invocation:** `wiki recall [--repo <path>] [--lookback N] [--stale-since N] [--top N] [--scope <subdir>] [--include-stubs]` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Surface wiki pages not touched in a while but sharing refs with recent log entries. Read-only, frontmatter-only, no body parsing, no synthesis.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 / P3 — Read-only on `wiki/`.** Reads `wiki/log.md` and page frontmatter. Writes nothing.
- **P4 — Configuration over convention.** Lookback window, staleness threshold, ref-type weights, top-N default, stub exclusion read from `recall:` config (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Each result carries a numeric score plus the *specific overlap evidence* (which ref shared with which dated log entry).
- **P8 — Analysis yes, speculation no.** No summary, no paraphrase, no characterization of the surfaced page or what the researcher should do with it. State the observable fact and stop.

## When to use

- Periodic memory-refresh ("지난 달 작업하던 그 컨셉 다시 봐야겠다").
- Pre-paper-write reminder of decision pages or experiment writeups whose conclusions feed the current draft.
- Pre-milestone catch of concepts the researcher implicitly built on but did not re-link.

## When NOT to use

- For finding a specific page by query string → use `wiki-query`.
- For all stale or orphan pages regardless of relevance → use `wiki-lint`.
- For body keyword matching → use `wiki-query`.
- For adding new entries → use `wiki-log`.
- The repo is not initialized → `wiki-init` first.
- `wiki/log.md` is empty or has no recent entries → wiki-recall has nothing to compare against; exits cleanly with a clear message.

## Inputs

- `--lookback <days>` (default 30) — how far back to scan `wiki/log.md` for recent activity.
- `--stale-since <days>` (default 60) — minimum age (since frontmatter `updated:`) for a page to qualify as stale.
- `--top N` (default 10) — number of results.
- `--scope <all | concepts | papers | experiments | decisions>` (default `all`) — limit to one wiki subdirectory.
- `--include-stubs` (default off) — include `authored_by: llm` / `seeded_by: …` empty-body stubs (typically `wiki-deepscan`-seeded). Off by default because their dense `refs.code` would dominate scoring without representing real interpretation.

## Outputs

Stdout only. No files created or modified.

```
> wiki-recall

1. wiki/concepts/auth-flow.md                            score 6.5  (updated 2026-01-12, 103 days ago)
   Overlaps with recent activity:
     - shared refs.code      src/trainer.py:Trainer        (logged 3 days ago in exp-2026-04-22)
     - shared refs.concepts  rotary-attention              (logged 8 days ago in design decision)

2. wiki/decisions/why-bs128.md                           score 4.0  (updated 2026-02-03, 81 days ago)
   Overlaps with recent activity:
     - shared refs.experiments  exp-2026-04-19              (logged 6 days ago)

(N more results suppressed; --top default 10)

Window: --lookback 30 days, --stale-since 60 days
Recent log entries scanned: 14   |   Stale pages considered: 38   |   Pages with overlaps: 11
```

Exit code: `0` if at least one result, `1` if zero.

## Behavior contract

- **Read-only.** No file writes. (P1, P3)
- **Refs-overlap scoring, not body matching.** Compares (i) refs in `wiki/log.md` entries within `--lookback` against (ii) refs in candidate stale pages' frontmatter. Body prose **not** parsed (that is `wiki-query`'s job — clean boundary).
- **Weighted overlap.** Default weights: `refs.code = 2.0`, `refs.concepts = 1.5`, `refs.papers = 1.0`, `refs.experiments = 1.0`. Configurable. Rationale: code refs are the most concrete signal; experiment/paper refs are looser.
- **`updated:` from frontmatter, not git mtime.** Researcher intent ("I touched this on purpose"), not bulk-rename pollution.
- **Recent activity from `wiki/log.md`.** Parse entries `## [YYYY-MM-DD] …`, gather their `refs:` blocks. Entries without refs contribute nothing.
- **Skill-meta entries filtered.** Headers `## […] from wiki-sync` or `from wiki-lint` describe wiki-meta events, not researcher activity — excluded by header pattern.
- **Stubs excluded by default.** Pages with `seeded_by: …` or (`authored_by: llm` + empty body) skipped unless `--include-stubs`.
- **No synthesis.** Output is pointers + overlap evidence. Never characterizes either the stale page or the recent log entry. (P8)
- **Deterministic.** Same wiki state + same flags → same output. Score is closed-form sum over weighted overlaps; no LLM judgment.

## Researcher interaction flow

One-shot. No conversational follow-up. Re-invoke with adjusted flags to refine. Stateless: each invocation re-scans the wiki corpus.

## Failure handling (essentials)

- `wiki/` missing → abort, suggest `wiki-init`.
- `wiki/log.md` empty/missing → exit 1 with message + suggest `wiki-log` or `wiki-query`.
- No log entries within window / no stale pages / 0 overlaps → exit 1 with structural broadening suggestions.
- Per-page or per-entry parse error → skip, log to stderr, continue.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys: `reference/consumed-config.md`
