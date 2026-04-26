# Skill Spec: `wiki-recall`

> **Frequency:** On-demand, typically every few weeks or pre-milestone
> **Tier:** Read-only surfacing
> **Writes to:** Nothing.

## Purpose

Surface wiki pages that are (a) **stale** — not updated for a configurable number of days — yet (b) **relevant** to recent activity, defined by overlap of frontmatter refs with entries logged in `wiki/log.md` over the recent window.

The output is a ranked list of "you wrote this a while ago, and your last few weeks' work touches the same things — you might want to revisit it". This is a **surfacing** skill, not a synthesis or recommendation skill. wiki-recall does not read page bodies, does not summarize, and does not say what the researcher should do.

## When to invoke

- Periodic memory refresh (monthly).
- Pre-paper-write reminder of decision pages or experiment writeups.
- Pre-milestone catch of concepts implicitly built on but not re-linked.

## When NOT to invoke

- For finding a specific page by query → `wiki-query`.
- For all stale/orphan pages regardless of relevance → `wiki-lint`.
- For body keyword matching → `wiki-query`.
- For adding new entries → `wiki-log`.

## Inputs

| Flag | Default | Rationale |
|---|---|---|
| `--lookback` | 30 days | Recent-activity window in `wiki/log.md` |
| `--stale-since` | 60 days | Minimum age (frontmatter `updated:`) for stale candidacy |
| `--top` | 10 | Result count |
| `--scope` | `all` | Limit to one wiki subdirectory |
| `--include-stubs` | off | Include `seeded_by:` / empty-body stubs |

Consumed config: `paths.wiki`, `recall.{lookback_default, stale_since_default, top_default, exclude_stubs, ref_weights.*}`. See `reference/consumed-config.md`.

## Outputs

Stdout only: ranked list with score, page path, days-since-update, and the **specific overlap evidence** per result (which ref of which type shared with which dated log entry). Closed with a window summary (lookback / stale-since / scanned / considered / overlapping counts). Exit code `0` if ≥1 result, `1` if zero.

## Behavior contract

- **Read-only** — no file writes. (P1, P3)
- **Refs-overlap scoring, not body matching** — boundary kept clean from `wiki-query`. (P8)
- **Weighted overlap** — `refs.code = 2.0`, `refs.concepts = 1.5`, `refs.papers = 1.0`, `refs.experiments = 1.0`; configurable. Rationale: code refs are the most concrete signal.
- **`updated:` from frontmatter, not git** — reflects researcher intent, immune to bulk-edit pollution.
- **Recent activity from `wiki/log.md`** — parse `## [YYYY-MM-DD] …` entries, gather refs.
- **Skill-meta log entries filtered** — `from wiki-sync` / `from wiki-lint` headers excluded.
- **Stubs excluded by default** — `seeded_by:` and `authored_by: llm` + empty body skipped unless `--include-stubs`.
- **No synthesis** — pointers + overlap evidence only. (P8)
- **Deterministic** — closed-form score; no LLM judgment.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys: `reference/consumed-config.md`
