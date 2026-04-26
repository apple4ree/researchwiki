<!--
  ResearchWiki template: experiment
  ---------------------------------
  This file is consumed by `wiki-log` when the researcher creates an experiment
  entry. wiki-log does three things with it:

    1. Parses the YAML frontmatter below. Keys prefixed with `_` (e.g., `_template`)
       are template-only directives and are NOT copied to the resulting entry.
    2. Copies the remaining frontmatter to the new entry, substituting placeholders
       in `{{DOUBLE_BRACES}}` with session-captured values.
    3. Walks the markdown body below, turning each `##` header into a conversational
       prompt. Sections marked `[required]` must be non-empty before wiki-log writes
       the entry.

  Placeholders wiki-log fills automatically:
    {{DATE}}        ISO date (YYYY-MM-DD) at the moment of creation.
    {{SESSION_ID}}  The current LLM session identifier.
    {{GIT_REF}}     Current HEAD SHA or branch. Null if not a git repo.
    {{TITLE}}       Human-readable title provided by the researcher.

  Do not edit the blocks below unless you want to change the template globally.
  For per-entry deviations, edit the generated entry file, not this template.
-->

---
# ===== Entry frontmatter (copied to the new entry) =====

schema_version: 1
type: experiment
created: {{DATE}}
updated: {{DATE}}
tags: []

# Cross-references — populated by wiki-log's auto-link pass after your approval
# (P7: every entry has provenance; confidence marked per entry in refs.code)
refs:
  code: []
  papers: []
  concepts: []
  experiments: []

# Provenance
authored_by: hybrid            # P3/P8: wiki-log forbids `llm`. Researcher-only is `human`.
source_sessions: [{{SESSION_ID}}]

# Experiment-specific measurable metadata
# Objective, measurable facts only (P8). Interpretation goes in the body.
git_ref: {{GIT_REF}}           # SHA, branch, or tag the experiment was run against
run_duration: null             # e.g., "2h 14m"; null if not recorded
seed: null                     # int for single-seed runs, list for multi-seed

# ===== Template-only config (consumed by wiki-log; not copied to entries) =====

_template:
  # Auto-link scan rules. See ARCHITECTURE.md §3.4 and wiki-log/SPEC.md §Auto-link rules.
  # For experiments, code and prior-experiment links are the most valuable.
  # Papers rarely come up directly in experiment bodies; keep that scan off to
  # reduce noise. Researcher can always add `refs.papers` manually.
  auto_link:
    code:
      enabled: true
      strategy: identifier_token   # scan body for code-identifier-shaped tokens
      default_confidence: verified # only if matched in index/signatures.json
    experiments:
      enabled: true
      strategy: exact_id           # match `exp-YYYY-MM-DD-*` patterns literally
      link_bidirectional: true     # also write back-ref in target entry's frontmatter
    concepts:
      enabled: true
      strategy: exact_slug         # match exactly against `wiki/concepts/<slug>.md`
      link_bidirectional: true
    papers:
      enabled: false
---

# {{TITLE}}

<!--
  For the researcher filling this in via wiki-log:
  You do not type this template yourself. wiki-log will ask each prompt below
  conversationally. You answer in natural language. wiki-log structures the answer
  into the matching section.
-->

## Hypothesis  [required]

*What were you testing? A hypothesis is a claim that could have been wrong —
not a goal. One or two sentences.*

<!-- example: "batch size 256 lets us use lr=3e-4 without instability" -->

## Setup  [required]

*What was different from previous runs? Hyperparameters, dataset changes, seed
count, hardware. Reference prior experiments by ID (e.g., `exp-2026-04-22-bs128`)
— wiki-log will auto-link them. The git ref is already captured in frontmatter,
so do not repeat it here.*

## Result  [required]

*What did the numbers show? **Direct observation only.** Do not write causal
explanations in this section — those belong in "Observations" if grounded, or
in `wiki/questions.md` if they cannot be grounded (P8 — no-guessing principle).*

<!-- example: "2/3 seeds converged to val_loss 1.24. 1 seed NaN at step 340." -->

## Observations  [required]

*Patterns visible in the logs, plots, or metrics that you can point to directly.
If an observation would assign a cause that the data does not establish, either
omit it or tag it `[speculation]` (P8).*

## Failure modes  [optional]

*What went wrong during the run. Describe **what happened**, not **why**.
Cause attribution without log evidence is speculation — tag `[speculation]`
or move the guess to `wiki/questions.md`.*

## Related code  [required]

*Functions, files, or modules involved in the run. Names only — wiki-log scans
this section for symbols in `index/signatures.json` and proposes verified
`refs.code` candidates for your approval.*

## Next steps  [optional]

*Concrete follow-up experiments or code changes. Keep short — a follow-up that
grows into its own investigation should get its own log entry rather than
living in this one.*
