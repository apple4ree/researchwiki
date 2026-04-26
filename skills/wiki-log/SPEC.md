# Skill Spec: `wiki-log`

> **Frequency:** Multiple times per day, on researcher's initiative
> **Tier:** Daily
> **Writes to:** `wiki/` (new pages + `log.md` + `index.md` + frontmatter back-refs on linked pages + optional concept stubs)

## Purpose

Add a new entry to the research journal — an experiment record, paper-reading note, design decision, or free-form observation. Uses the template system, auto-links to existing wiki + index content, and appends to `log.md`.

This is the skill the researcher uses most. **Ease of use is the primary design driver** — the conversation should feel fluid, not form-filling.

## When to invoke

- After running an experiment (regardless of outcome).
- After reading a paper or article.
- When making a non-trivial design or implementation decision.
- When observing something worth recording (a bug, an idea, a question).
- Any time the researcher wants to record something in the wiki.

## When NOT to invoke

- For regenerating the Index Layer → use `wiki-sync`.
- For deep code analysis → use `wiki-deepscan`.
- For auditing existing content → use `wiki-lint`.
- For editing an existing page body → refuse (P3); offer manual edit, new superseding entry, or `wiki-fix-stale` for stale-ref cases.
- For bulk import → out of scope.

## Inputs

| Flag | Default | Rationale |
|---|---|---|
| `--type` | prompt | `experiment \| paper \| decision \| free` — selects template |
| `--title` | required | Slug for filename; doubles as `paper_id` / `decision_id` for those types |
| `--amend` | off | Update most recent entry of `--type` within `log.amend_window` (default 24h) |
| `--quick` | off | Skip auto-link + stub suggestion. Validation, P8 still enforced. |
| inline template fields | none | E.g., `--year 2017` for paper. Skips the corresponding prompt. |

Consumed config: `paths.{wiki,index}`, `language.default`, `log_templates.*`, `log.{amend_window, suggest_concept_stubs}`. See `reference/consumed-config.md`.

## Outputs

1. New page under `wiki/<subdir>/` (subdir per `--type`).
2. Append to `wiki/log.md` (single line + summary + path).
3. Update `wiki/index.md` (single line under category).
4. **Auto-link updates** — frontmatter ref on the new entry; if `link_bidirectional: true` in the template, also a back-ref on the target page's frontmatter (the only edit wiki-log makes to existing pages, P3-permitted).
5. **Concept stubs (optional)** — frontmatter-only stubs for noun phrases that failed exact-slug match in concept auto-link. Body is a single italicized line; `seeded_by: wiki-log` + `seed_context:` recorded.

## Behavior contract

- **Template-driven.** Templates carry entry frontmatter + `_template:` directives (auto-link rules). Section `[required]` / `[optional]` flags + italic guides drive the conversation. (P4)
- **One entry per invocation.** No bulk mode.
- **`authored_by`:** default `hybrid`; `human` when researcher dictates verbatim; **`llm` forbidden** — every entry has human intent.
- **No body edits on existing pages.** New entry → ref + tension note in `wiki/questions.md`; existing body untouched. (P3)
- **No speculation.** Hedge / causal / intent claims → three-route intervention (rewrite as observation / `[speculation]` tag / move to questions.md). Never silently rewrites or silently tags. (P8)
- **Auto-link requires explicit researcher approval.** Never stamps `verified` on data not in `index/signatures.json` or as an existing wiki page. (P7)
- **Concept stubs are create-only and body-empty.** Frontmatter + one italicized line. wiki-log never writes prose about what the concept "is for". (P3, P8)

## Auto-link strategy (concrete)

When scanning a draft for link candidates:

1. **Code symbols** — identifier-like tokens looked up in `index/signatures.json`. Unique match → `confidence: verified`. Not in index → ask researcher; on confirm → `confidence: inferred`.
2. **Paper IDs** — paper slug or `[[slug]]` pattern → exact match in `wiki/papers/`.
3. **Concepts** — concept-sounding noun phrase → exact slug match in `wiki/concepts/`. Failed matches routed to **stub suggestion batch** (if `log.suggest_concept_stubs: true`).
4. **Experiments** — `exp-YYYY-MM-DD-*` ID pattern → match in `wiki/experiments/`.

**Does not fuzzy-match aggressively. When in doubt, ask.** Detailed walk-through with example tokens and rejected candidates: `reference/examples.md` (Example 1).

## Reference

- Worked examples (5): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys + `_template:` block schema: `reference/consumed-config.md`
