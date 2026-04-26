---
name: wiki-lint
description: Use this skill when the researcher wants to audit the health of an existing ResearchWiki — check for broken intra-wiki and cross-layer links, frontmatter schema violations (per `CLAUDE.md §5`), pages exceeding the speculation threshold (default >30% `[speculation]` tags per `ARCHITECTURE.md §2.5`), persistent `stale: true` refs that `wiki-sync` flagged but the researcher has not addressed, orphan pages, and a narrow class of cross-page contradictions — and produce an audit report. wiki-lint reports findings; it does **not** fix them, and it **never modifies a wiki page (body or frontmatter)**. Trigger phrases include "wiki-lint", "wiki 감사", "감사 리포트", "speculation 검사", "broken link 검사", "스펙 위반 찾아줘", "위키 헬스 체크", "audit the wiki", "lint the wiki", "wiki health check", "are my wiki pages well-formed?", "check for stale refs that I haven't addressed". Do not use to regenerate the index (use `wiki-sync`), to refresh the deep graph (use `wiki-deepscan`), to add new entries (use `wiki-log`), or to initialize the workspace (use `wiki-init`). Do not invoke as a pre-commit hook — it is too thorough for that. Do not use as a substitute for reading the wiki — the report points to mechanically detectable issues; semantic problems (a page that is well-formed but says the wrong thing) are out of scope.
---

# wiki-lint

> **Invocation:** `wiki lint [--repo <path>] [--scope <list>] [--strict] [--no-write]` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Audit an existing wiki and produce a report. Surface mechanically detectable problems; route findings to a place the researcher can act on. Never modify the wiki itself.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Reads `wiki/` (interpretation) and `index/` (fact); writes audit reports into `index/audits/` (fact). Appends researcher-facing notes to `wiki/questions.md` and `wiki/discrepancies.md`. Writes nothing else into `wiki/`.
- **P3 — Propose, do not mutate interpretation.** *Stricter than wiki-sync* — wiki-lint does not even update frontmatter flags. Findings flow only into the audit report and the two append-only meta files. The researcher is the sole entity authorized to amend wiki frontmatter or body in response to a lint finding.
- **P4 — Configuration over convention.** `lint.*` (severity escalation, thresholds) read from config (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Every finding carries provenance: page path, line number where applicable, check name, default severity, source rule reference.
- **P8 — Analysis yes, speculation no.** Every check is a deterministic function of wiki + index state. No LLM judgment. No "feels off about" findings. If a check is not in the catalog, wiki-lint does not run it.

## When to use

- Pre-milestone or pre-paper-submission health check.
- Periodic (weekly, monthly) hygiene pass.
- After resolving a batch of `wiki/questions.md` entries, to confirm the open list is shrinking.
- When a specific symptom (stale link, malformed page) suggests broader drift.
- As a CI gate before merging a documentation branch — combined with `--strict`.

## When NOT to use

- For regenerating the Index Layer → `wiki-sync`.
- For deep knowledge graph refresh → `wiki-deepscan`.
- For new wiki entries → `wiki-log`.
- Repo not initialized → `wiki-init` first.
- **As a pre-commit hook** — too thorough; meant for deliberate audit moments.
- **As a substitute for reading the wiki** — semantic problems (well-formed but wrong) are out of scope.

## Inputs

- `--scope <all | links | frontmatter | speculation | stale | orphans | contradictions>` (default `all`). Comma-combine, e.g. `--scope links,frontmatter`.
- `--strict` — escalate every finding to `error` severity. Overrides `config.lint.strict_mode`. Causes non-zero exit if any finding survives (release-gate friendly).
- `--no-write` — dry-run. Print summary; do not write audit report or append to questions/discrepancies.
- `--report-path <path>` — override default `index/audits/lint_YYYYMMDD_HHMM.md`.

## Outputs

### `index/audits/lint_YYYYMMDD_HHMM.md`

Self-contained, **immutable once written** (mirrors `index/snapshots/sync_*.md` convention). Contains:
- Repository header (wiki root, pages scanned, index reference, strict mode, config snapshot)
- Severity summary table (error / warn / info counts)
- Per-finding sections: `### <severity> · <category> · <page-path>` with the observed condition + source rule reference
- `## Scan errors` for per-page parse failures

### Append to `wiki/questions.md`

Findings requiring a researcher decision (frontmatter violations, stale refs, etc.) are appended in the same style `wiki-sync` uses — one append-block per audit run, multiple action items.

### Append to `wiki/discrepancies.md`

Cross-page contradiction findings (**Check 7 only** — confidence conflicts on the same `refs.code` symbol) go here, not to questions.md, because they describe a discrepancy between two wiki pages rather than a question for the researcher about a single page.

## Behavior contract

- **Read-only on wiki bodies AND frontmatter.** Findings flow only into audit report + questions.md + discrepancies.md. Stricter than `wiki-sync`. (P3)
- **Mechanical checks only.** No LLM judgment. (P8)
- **No corrective suggestions in the report body.** Finding states observable condition + source rule. The companion `wiki/questions.md` entries describe the *kind* of decision needed, not what to write.
- **Does not duplicate `wiki-sync`.** Symbol-level stale detection is wiki-sync's job. wiki-lint reads existing `stale: true` flags and reports those past `lint.stale_age_days`.
- **Does not invoke Understand-Anything.** Cross-module structural analysis is wiki-deepscan's job. Optional refinement: if `deep/knowledge-graph.json` is present, Check 8 (orphans) consults it.
- **Append-only on `wiki/questions.md` and `wiki/discrepancies.md`.** (CLAUDE.md §3)
- **Audit reports immutable.** Re-run produces a new file in `index/audits/`.
- **Honors `lint.strict_mode`.** When true, every finding escalated to `error`; non-zero exit. `--strict` flag has same effect.
- **Creates `index/audits/` if missing** (defensive fallback for pre-bootstrap-fix workspaces).

### The check catalog

The MVP defines eight checks. Each is mechanically grounded and bound to a specific document rule. **Adding a new check requires extending this catalog explicitly** — wiki-lint does not run ad-hoc checks.

| # | Category | Check | Default severity | Source rule |
|---|----------|-------|------------------|-------------|
| 1 | frontmatter | All required fields per `CLAUDE.md §5` present and well-typed | error | CLAUDE.md §5, §110 |
| 2 | frontmatter | `authored_by` ∈ {human, llm, hybrid} | error | CLAUDE.md §5, P7 |
| 3 | links | Every intra-wiki link target exists | warn | README skills table ("broken links") |
| 4 | links | Every `refs.code.path` exists in the repo (file-level only; symbol-level is wiki-sync's job) | warn | P1 |
| 5 | speculation | Page-level `[speculation]` density does not exceed `lint.speculation_threshold` (default 0.30) | warn | ARCHITECTURE.md §2.5 / §1.4 P8 |
| 6 | stale | No `refs.code` entry has `stale: true` for longer than `lint.stale_age_days` (default 7) | warn | wiki-sync's stale-flag contract |
| 7 | contradictions | No two pages reference the same `refs.code` (path + symbol) with conflicting `confidence` values | warn | P7 |
| 8 | orphans | Every non-meta wiki page has at least one inbound link from another wiki page | info | README skills table ("gaps") |

Meta pages (`wiki/index.md`, `wiki/log.md`, `wiki/questions.md`, `wiki/discrepancies.md`) and any file under `index/audits/` are excluded from Check 8 by definition.

## Researcher interaction flow

One-shot. Invocation produces a short summary:

```
Lint audit complete (3.2s).
  Pages scanned: 47
  Findings: 2 error · 11 warn · 6 info
  Top issues: <up to ~5 most severe one-liners>
  Full report: index/audits/lint_YYYYMMDD_HHMM.md
  Appended N entries to wiki/questions.md
  Appended N entry  to wiki/discrepancies.md
```

If `--strict` is set and any finding is at `error` severity (after escalation), the skill exits non-zero. No interactive Q&A — wiki-lint is a batch audit, not a conversation.

## Failure handling (essentials)

- `wiki/` missing → abort, suggest `wiki-init`.
- `index/` missing → warn, skip Check 4 + Check 6, run rest. Note partial-run state in report header.
- Config missing → fall back to defaults, warn.
- Per-page parse error → record in `## Scan errors`, continue.
- `index/audits/` missing → defensive create, note in summary.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples (5, including strict-mode and partial-run): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys + what wiki-lint reads from other skills' outputs + what it writes: `reference/consumed-config.md`
