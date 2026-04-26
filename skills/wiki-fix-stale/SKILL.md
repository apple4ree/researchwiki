---
name: wiki-fix-stale
description: Use this skill when the researcher wants to address unresolved stale refs that `wiki-sync` has flagged in wiki page frontmatter (`refs.code` entries marked `stale: true`) and, optionally, body-prose mentions of removed code symbols (`body_stale_mentions` entries surfaced by wiki-sync's body link rot scan). wiki-fix-stale is the **only** skill that edits wiki page bodies after creation, and it does so strictly **researcher-initiated and per-occurrence-approved** — the researcher invokes it explicitly, and each individual body edit is reviewed before it is written. The skill offers four mechanical edit options per occurrence (replace symbol name with a researcher-supplied name, wrap with `[deprecated YYYY-MM-DD]` tag, delete the affected sentence, or skip); it never composes new prose, never paraphrases the surrounding text, and never proposes wording. After all stale refs in a page are addressed, frontmatter `stale: true` flags are auto-cleared. Trigger phrases include "wiki-fix-stale", "stale 정리", "오래된 ref 정리", "본문 거짓말 고치자", "stale 플래그 정리", "fix the stale refs", "address stale flags", "clean up the deprecated symbol mentions". Do not use to *detect* stale refs (that is `wiki-sync`'s job; this skill consumes its output). Do not use to add new entries (use `wiki-log`). Do not use mid-refactor when the symbol set is still in flux — fixes will themselves go stale. Do not invoke without clear intent: this is the one skill that touches wiki page bodies, so each invocation is a deliberate maintenance moment.
---

# wiki-fix-stale

> **Invocation:** `wiki fix-stale [--repo <path>] [--page <relpath>] [--no-auto-clear-flags] [--no-body-mentions]` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Walk the researcher through unresolved stale refs and apply researcher-approved body edits. Closes the body / frontmatter decoupling gap with strict P3 compliance — the *one* skill that legitimately edits wiki page bodies.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Reads index layer (`signatures.json`, `reverse_refs.json`) for context but writes only to interpretation layer (`wiki/`). Body edits are interpretation-layer changes the researcher authorizes.
- **P3 — Propose, do not mutate interpretation.** *Carve-out:* CLAUDE.md §3 directory contract permits body edits "only with explicit researcher approval or researcher-initiated request." This skill is the precise scenario the carve-out was reserved for. Researcher invokes (initiation) + approves each individual edit (per-occurrence approval). No bulk auto-apply without explicit `--apply-to-all` confirmation per choice type per page.
- **P4 — Configuration over convention.** `fix_stale.*` config (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** `body_stale_mentions` from wiki-sync's heuristic scan carry a visible `[unverified]` tag during the walk, distinguishing them from deterministic frontmatter stale refs.
- **P8 — Analysis yes, speculation no.** Four mechanical edit options operate on literal text only. Replace takes researcher's literal token. Wrap prepends a literal tag. Delete removes a literal span. Never composes prose, never paraphrases, never proposes wording.

## When to use

- After `wiki-sync` reports stale flags older than the nag threshold (default 7 days) and surfaces a "wiki-fix-stale로 처리하시겠어요?" prompt.
- Periodic maintenance pass — weekly or pre-paper-submission.
- After a refactor that renamed or removed many symbols — catch up affected wiki bodies in one focused session.
- When a `wiki-query` result page carries the `⚠ stale` badge and the researcher needs to trust that page's content.

## When NOT to use

- For *detecting* stale refs → `wiki-sync`.
- For broader audit → `wiki-lint`.
- For new entries → `wiki-log`.
- For finding pages by query → `wiki-query`.
- Mid-refactor while symbol set is in flux — fixes will themselves go stale on the next sync.
- Repo not initialized → `wiki-init` first.

## Inputs

- `--scope <all | concepts | papers | experiments | decisions>` (default `all`).
- `--auto-clear-flags` (default `true`) — after all stale refs in a page handled (no skips), auto-remove `stale: true` and `stale_detected:` from frontmatter.
- `--include-body-mentions` (default `auto`: include if `body_stale_mentions` present, skip otherwise) — walk body link rot mentions.
- `--oldest-first` (default `true`) — process pages by oldest `stale_detected:` first.
- `--page <path>` — restrict to a single page (e.g., one surfaced by `wiki-query` or `wiki-lint`).

## Outputs

### Wiki page body edits (per researcher-approval)

Per occurrence, the researcher chooses one of four actions; the skill applies the literal transformation:

1. **Replace symbol name** — substitute the literal token with researcher-supplied identifier (validated). Surrounding prose untouched.
2. **Wrap with `[deprecated YYYY-MM-DD]`** — prepend tag to the affected sentence. Original text preserved verbatim.
3. **Delete the sentence** — remove sentence containing the symbol (boundaries computed by punctuation; ambiguous cases confirmed).
4. **Skip** — leave as-is. The stale flag remains; page resurfaces next run.

The skill *never*: composes new prose, paraphrases researcher's text, adjusts surrounding sentences for grammar after deletion, proposes the replacement name.

### Frontmatter flag clearance

When `--auto-clear-flags=true` and every occurrence on a page was handled (no skips), remove `stale: true` / `stale_detected:` on each handled `refs.code` entry plus corresponding `body_stale_mentions` entries.

### `wiki/log.md` — session record

```
## [YYYY-MM-DD HH:MM] from wiki-fix-stale

Stale-fix session resolved.
- Pages walked:        N
- Pages fully cleared: N
- Pages partially handled (skips remain): N
- Body edits applied:  N (replace/wrap-deprecated/delete counts)
- Stale flags cleared: N
- Body mentions resolved: N
```

Mechanical counts only — no commentary about *why* the researcher made each choice.

## Behavior contract

- **Researcher-initiated, per-occurrence-approved.** Invoked explicitly; each body edit reviewed and approved before written. (P3)
- **Verbatim edits, no LLM-authored prose.** Four mechanical transformations only. (P8)
- **Atomic per page.** Edits buffered; written only on researcher confirmation of "apply". Mid-page abort leaves file untouched.
- **Conditional flag clearance.** Frontmatter cleared only if every occurrence was handled (no skips). Partial handling preserves the flag.
- **Body mentions tagged `[unverified]` during walk.** Distinguishes wiki-sync's heuristic findings from deterministic frontmatter findings. (P7)
- **In-skill body grep fallback.** If `body_stale_mentions` absent, the skill grep's the body itself during the walk.
- **No bulk auto-apply by default.** Each occurrence presented individually. `--apply-to-all <choice-type>` available *per page per choice type* with explicit per-page confirmation; does not span sessions.
- **Idempotent.** Re-invocation after complete session is no-op. After partial session, resumes from skipped occurrences.

### P3 compliance — three protections

1. **Researcher-initiated.** wiki-sync's nag is a *suggestion*; the researcher must invoke wiki-fix-stale to act.
2. **Per-occurrence approval.** Every edit shown and approved (or skipped) before written.
3. **Mechanical only.** Four pre-defined transformations; never composes new prose. The researcher cannot, by approving, accidentally authorize an LLM-authored rewrite — that capability is not in the skill.

If any of these three is weakened in a future revision, this skill ceases to be P3-compliant.

## Researcher interaction flow

1. Load `wiki/`; identify pages with `stale: true` plus `body_stale_mentions` (if `--include-body-mentions`). Sort oldest-first. Show summary; ask `Continue? [y/N]`.
2. Per page (researcher confirmed):
   a. Show page path + oldest stale entry + occurrence count summary.
   b. Per occurrence: show the symbol, line context, and the four-option menu. Apply researcher's choice to in-memory copy.
   c. After all occurrences: show cumulative diff + frontmatter clearance preview. Ask `Apply? [y/N/edit]`.
   d. On `y`: write edits + frontmatter clearance. On `N`: discard. On `edit`: revise individual choices, re-show diff.
3. After all pages: append session record to `wiki/log.md`; report counts.

## Failure handling (essentials)

- No stale-flagged pages → "no stale flags to fix"; exit 0.
- `wiki/` missing → abort, suggest `wiki-init`.
- Stale flag but symbol not in body (false positive) → offer (a) clear flag without body changes, (b) skip.
- Researcher exits mid-page → that page's edits discarded; already-written pages remain.
- Replace-symbol name not a valid identifier → refuse, re-prompt.
- Delete-sentence boundary ambiguous → show candidates, ask researcher to pick.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys (and what wiki-fix-stale reads from other skills' outputs): `reference/consumed-config.md`
