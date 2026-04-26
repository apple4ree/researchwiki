# Skill Spec: `wiki-lint`

> **Frequency:** On-demand, on the researcher's initiative
> **Tier:** On-demand audit
> **Writes to:** `index/audits/`, append-only to `wiki/questions.md` and `wiki/discrepancies.md`. **Never modifies a wiki page (body or frontmatter).**

## Purpose

Audit the health of an existing wiki and produce a report. Surface mechanically detectable problems — broken links, frontmatter schema violations, pages above the speculation threshold, persistent stale refs, orphan pages, and a narrow class of cross-page contradictions — and route each finding to a place the researcher can act on it.

wiki-lint **reports** findings; it does **not** fix them. Per `ARCHITECTURE.md §3.2`, it is the only skill authorized to produce audit reports, and per `CLAUDE.md §4`, it owns all linting passes — no other skill should silently lint as a side effect.

## When to invoke

- Pre-milestone or pre-paper-submission health check.
- Periodic (weekly, monthly) hygiene pass on a long-running wiki.
- After a stretch of fast-moving research, when accumulated drift is suspected.
- After resolving a batch of `wiki/questions.md` entries, to confirm the open list is shrinking.
- As a CI gate before merging a documentation branch — combined with `--strict`.

## When NOT to invoke

- For regenerating the Index Layer → `wiki-sync`.
- For Deep Analysis Layer refresh → `wiki-deepscan`.
- For new wiki entries → `wiki-log`.
- As a pre-commit hook — too thorough; meant for deliberate audit moments.
- As a substitute for reading the wiki — semantic problems (well-formed but wrong) are out of scope.

## Inputs

| Flag | Default | Effect |
|---|---|---|
| `--scope` | `all` | Limit check categories: comma-combine `links,frontmatter,speculation,stale,orphans,contradictions` |
| `--strict` | off | Escalate every finding to `error` severity; non-zero exit if any survive |
| `--no-write` | off | Dry-run — print summary, no audit report or append |
| `--report-path` | `index/audits/lint_{ts}.md` | Override audit report destination |

Consumed config: `paths.{wiki,index,deep}`, `lint.{strict_mode, speculation_threshold, stale_age_days, stub_grace_period_days, severity_overrides}`. See `reference/consumed-config.md`.

## Outputs

- **`index/audits/lint_YYYYMMDD_HHMM.md`** — self-contained, immutable per-run audit report. Contains repository header, severity summary table, per-finding sections, and `## Scan errors`.
- **Append to `wiki/questions.md`** — findings requiring researcher decision.
- **Append to `wiki/discrepancies.md`** — Check 7 cross-page confidence conflicts only.

## Behavior contract

- **Read-only on wiki bodies AND frontmatter.** Stricter than `wiki-sync`. (P3)
- **Mechanical checks only.** Each check is a deterministic function of wiki + index state. No LLM judgment in deciding what is a problem. (P8)
- **No corrective suggestions in report body.** Finding states observable condition + source rule; companion `wiki/questions.md` entries describe the *kind* of decision needed.
- **Does not duplicate `wiki-sync`.** Symbol-level stale detection is wiki-sync's job; wiki-lint reports persistent unaddressed `stale: true` flags via `lint.stale_age_days`.
- **Does not invoke Understand-Anything.** If `deep/knowledge-graph.json` present, used to refine Check 8 (orphan); never re-runs the tool.
- **Append-only on `wiki/questions.md` and `wiki/discrepancies.md`.** (CLAUDE.md §3)
- **Audit reports immutable.** Re-run produces a new file in `index/audits/`.
- **Honors `lint.strict_mode` / `--strict`.** Escalates every finding to `error`; non-zero exit.

## The check catalog (8 mechanical checks)

| # | Category | Check | Default severity |
|---|----------|-------|------------------|
| 1 | frontmatter | All required fields per `CLAUDE.md §5` present + well-typed | error |
| 2 | frontmatter | `authored_by` ∈ {human, llm, hybrid} | error |
| 3 | links | Every intra-wiki link target exists | warn |
| 4 | links | Every `refs.code.path` exists in the repo (file-level) | warn |
| 5 | speculation | Page `[speculation]` density ≤ `lint.speculation_threshold` (0.30 default) | warn |
| 6 | stale | No `stale: true` for > `lint.stale_age_days` (7 default) | warn |
| 7 | contradictions | No two pages disagree on `confidence` for same `refs.code` symbol | warn |
| 8 | orphans | Every non-meta page has ≥1 inbound link | info |

Adding a new check requires extending this catalog explicitly — wiki-lint does not run ad-hoc checks. (P8 — keeps the skill mechanically grounded; if any check required LLM judgment, wiki-lint would itself violate P8.)

Source rules + meta-page exclusions: see `SKILL.md`'s detailed catalog.

## Reference

- Worked examples (5): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions (incl. severity boundaries, speculation tokenization unit, gap detection, stub orphan grace): `reference/open-questions.md`
- Consumed config keys + skill-output reads + writes: `reference/consumed-config.md`
