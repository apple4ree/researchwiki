# `wiki-lint` — Worked Examples

> Supplementary material for `wiki-lint`. Not loaded at LLM runtime.

---

## Example 1 — Happy path: weekly hygiene pass surfaces real findings

**Setup.** Researcher runs wiki-lint on a Friday afternoon as a weekly hygiene pass. Last audit was a week ago.

**Invocation.**

```
> wiki-lint
```

**Execution trace.**

```
wiki-lint: Loading research-wiki.config.yaml.
  scope: all
  strict: false (config.lint.strict_mode = false)
  speculation_threshold: 0.30
  stale_age_days: 7

Scanning 47 wiki pages...
  Frontmatter checks      → 2 error,  3 warn
  Link checks             → 4 warn
  Speculation checks      → 1 warn   (1 page above threshold)
  Stale-ref checks        → 2 warn   (referenced index/snapshots/sync_20260425_0903.md)
  Contradiction checks    → 1 warn
  Orphan checks           → 6 info   (deep/knowledge-graph.json present, used to refine)

Writing...
  ✓ index/audits/lint_20260425_1403.md     (new immutable report)
  ✓ wiki/questions.md                      (8 entries appended)
  ✓ wiki/discrepancies.md                  (1 entry appended)

Lint audit complete (3.2s).
  Pages scanned: 47
  Findings: 2 error · 11 warn · 6 info

  Top issues:
    error  wiki/concepts/auth-flow.md          missing authored_by
    error  wiki/experiments/exp-2026-04-19.md  missing schema_version
    warn   wiki/papers/sparse-attention.md     speculation density 0.42 (>0.30)
    warn   wiki/concepts/auth-flow.md          stale ref unaddressed for 2 days

  Full report: index/audits/lint_20260425_1403.md
  Appended 8 entries to wiki/questions.md
  Appended 1 entry  to wiki/discrepancies.md
```

The researcher opens `index/audits/lint_20260425_1403.md`, fixes the two `error`-severity frontmatter issues by hand, decides to leave the speculation-dense paper page alone (it is a draft summary that will be revisited), and resolves the two `warn`-severity stale refs by editing the relevant pages. They do **not** re-run wiki-lint after each fix; the next audit is the next deliberate hygiene moment.

---

## Example 2 — Strict mode: pre-submission gate

The researcher is one day from a paper submission and wants to confirm the wiki has zero structural problems before they freeze it.

```
> wiki-lint --strict

wiki-lint: Loading research-wiki.config.yaml.
  scope: all
  strict: true (overrides config.lint.strict_mode = false)
  All findings will be escalated to severity = error.

Scanning 47 wiki pages...
  ...

Writing...
  ✓ index/audits/lint_20260428_0945.md
  ✓ wiki/questions.md                      (3 entries appended)

Lint audit complete (3.0s).
  Pages scanned: 47
  Findings: 3 error (all severities escalated by --strict)

  Top issues:
    error  wiki/concepts/auth-flow.md       broken intra-wiki link → wiki/concepts/missing-page.md
    error  wiki/experiments/exp-2026-04-19.md  missing schema_version
    error  wiki/papers/sparse-attention.md  speculation density 0.42 (>0.30)

  Full report: index/audits/lint_20260428_0945.md

Exit code: 1 (strict mode + findings present).
```

The non-zero exit code lets the researcher (or a pre-submission script) abort the freeze. After fixing each issue, they re-run with `--strict` until the audit passes.

---

## Example 3 — Refusal: workspace not initialized

```
> wiki-lint

wiki-lint: Target repo appears not to be a ResearchWiki workspace.
  Missing: CLAUDE.md
  Missing: research-wiki.config.yaml
  Missing: wiki/

wiki-lint requires an initialized workspace. Run:

  > wiki-init --mode new --language ko --deepscan-tool understand-anything

or --mode adopt if you want to preserve existing code/notes around the wiki
structure. Aborting.
```

No partial output is written. The researcher must initialize first.

---

## Example 4 — Partial run: index/ missing, lint runs reduced check set

The researcher has a fresh wiki but has not run `wiki-sync` yet. They want a frontmatter audit anyway.

```
> wiki-lint --scope frontmatter,links,speculation,orphans

wiki-lint: Loading research-wiki.config.yaml.
  scope: frontmatter, links, speculation, orphans
  strict: false

⚠ index/ does not exist.
  Skipping checks that depend on the index:
    - Check 4 (refs.code.path file existence)  → SKIPPED
    - Check 6 (persistent stale-ref age)        → SKIPPED
  Note: --scope did not request these anyway.

Scanning 12 wiki pages...
  Frontmatter checks      → 1 error
  Link checks (intra-wiki only; cross-layer skipped) → 0 findings
  Speculation checks      → 0 findings
  Orphan checks (no deep graph available; pure inbound-link heuristic) → 4 info

Writing...
  ✓ index/audits/lint_20260425_1100.md     (new immutable report; partial-run flag set)
  ✓ wiki/questions.md                      (1 entry appended)

Lint audit complete (0.9s, partial — index/ missing).
  Pages scanned: 12
  Findings: 1 error · 0 warn · 4 info

  Top issues:
    error  wiki/concepts/auth-flow.md       missing authored_by

  Full report: index/audits/lint_20260425_1100.md
  Note: run wiki-sync to enable Check 4 and Check 6 in the next audit.
```

The audit report's header explicitly says "partial run — index/ missing, Check 4 and Check 6 skipped". The next audit, after the researcher runs `wiki-sync`, gets the full check set.

---

## Example 5 — Detailed audit report (excerpt)

The full content of `index/audits/lint_20260425_1403.md` (Example 1's report):

```markdown
# Lint audit — 2026-04-25 14:03 (Asia/Seoul)
_Generated by wiki-lint. Immutable once written._

## Repository
- Wiki root: wiki/
- Pages scanned: 47
- Index reference: index/snapshots/sync_20260425_0903.md
- Strict mode: false
- Config: lint.speculation_threshold = 0.30, lint.stale_age_days = 7

## Summary
| Severity | Count |
|----------|-------|
| error    | 2     |
| warn     | 11    |
| info     | 6     |

## Findings

### error · frontmatter · wiki/concepts/auth-flow.md
Missing required field: `authored_by`.
Source rule: CLAUDE.md §5 (P7 — every claim has provenance).

### error · frontmatter · wiki/experiments/exp-2026-04-19.md
Missing required field: `schema_version`.
Source rule: CLAUDE.md §5.

### warn · speculation · wiki/papers/sparse-attention.md
Speculation density 0.42 exceeds threshold 0.30.
  37 of 88 sentences tagged [speculation].
Source rule: ARCHITECTURE.md §2.5 / §1.4 P8.

### warn · stale · wiki/concepts/auth-flow.md
Stale ref `src/legacy/old_trainer.py:LegacyTrainer` flagged by wiki-sync on 2026-04-23, unaddressed for 2 days (threshold: 7 days).
Source rule: wiki-sync's stale-flag contract; lint.stale_age_days configures the report-after age.

### warn · contradictions · src/trainer.py:Trainer
Two pages reference this symbol with conflicting `confidence` values:
  - wiki/concepts/training-loop.md          confidence: verified
  - wiki/experiments/exp-2026-04-19.md      confidence: inferred
Source rule: P7 — confidence is per-symbol, not per-page; reconcile.

### info · orphans · wiki/concepts/legacy-cache.md
No inbound link from any other wiki page.
Source rule: README §How it works ("gaps") — orphan-page heuristic.

…

## Scan errors
(none)
```

The corresponding `wiki/questions.md` append:

```
## [2026-04-25 14:03] from wiki-lint

**Frontmatter violation:** `wiki/concepts/auth-flow.md` is missing `authored_by`.
**Action needed:** add the field with one of `human`, `llm`, or `hybrid` (see CLAUDE.md §5).

**Persistent stale ref:** `wiki/concepts/auth-flow.md` still references
`src/legacy/old_trainer.py:LegacyTrainer`, which wiki-sync flagged stale on 2026-04-23.
**Action needed:** decide — update body, remove the ref, or accept that this page documents deprecated code.
```

The corresponding `wiki/discrepancies.md` append (Check 7 only):

```
## [2026-04-25 14:03] from wiki-lint

**Confidence conflict on `src/trainer.py:Trainer`:**
  - wiki/concepts/training-loop.md         confidence: verified
  - wiki/experiments/exp-2026-04-19.md     confidence: inferred

Both pages reference the same code symbol but disagree on how reliable the binding is.
Per P7, confidence is a property of the symbol-binding evidence, not the page that records it. Reconcile.
```
