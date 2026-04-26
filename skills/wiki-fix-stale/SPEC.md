# Skill Spec: `wiki-fix-stale`

> **Frequency:** On-demand, on the researcher's initiative — typically prompted by `wiki-sync`'s nag at the end of a daily sync, or by the researcher noticing accumulated stale flags
> **Tier:** Maintenance / remediation
> **Writes to:** `wiki/` page bodies (each edit per-occurrence-approved by the researcher), `wiki/` frontmatter (auto-clears `stale: true` flags after all stale refs in a page are handled), `wiki/log.md` (session record)

## Purpose

Walk the researcher through unresolved stale references — frontmatter `stale: true` flags written by `wiki-sync` and (when available) body-prose `body_stale_mentions` from wiki-sync's body link rot scan — and apply researcher-approved body edits one occurrence at a time.

This skill closes the design's most damaging operational hazard: the **body / frontmatter decoupling**. wiki-sync flags the frontmatter when a code symbol disappears, but it cannot edit the body that still claims things about that symbol. The body therefore lies — silently — until a researcher reads the frontmatter flag and acts. wiki-fix-stale makes that action a discrete, repeatable, P3-compliant operation.

## When to invoke

- After `wiki-sync` reports stale flags older than the nag threshold.
- Periodic maintenance — weekly or pre-paper-submission.
- After a refactor that renamed/removed many symbols.
- When a `wiki-query` result page carries a `⚠ stale` badge.

## When NOT to invoke

- For *detecting* stale refs → `wiki-sync`.
- For broader audit → `wiki-lint`.
- For new entries → `wiki-log`.
- Mid-refactor while symbols are in flux — fixes will themselves go stale.

## Inputs

| Flag | Default | Effect |
|---|---|---|
| `--scope` | `all` | Limit walk to one wiki subdirectory |
| `--auto-clear-flags` | `true` | After all stale refs in a page handled, auto-remove frontmatter flags |
| `--include-body-mentions` | `auto` | Walk `body_stale_mentions` if present; skip if absent |
| `--oldest-first` | `true` | Process by oldest `stale_detected:` first |
| `--page <path>` | (none) | Restrict to a single page |

Consumed config: `paths.{wiki,index}`, `fix_stale.*`. See `reference/consumed-config.md`.

## Outputs

- **Body edits** (per researcher-approval): four mechanical options per occurrence (replace symbol / wrap-deprecated / delete sentence / skip). Verbatim transformations only — no LLM-authored prose.
- **Frontmatter clearance** (when `--auto-clear-flags=true` and no skips): remove `stale: true`, `stale_detected:`, `body_stale_mentions:` entries on resolved refs.
- **`wiki/log.md` session record:** mechanical counts (pages walked, edits applied per choice type, flags cleared).

## Behavior contract

- **Researcher-initiated, per-occurrence-approved.** The precise scenario CLAUDE.md §3 carve-out permits. (P3)
- **Verbatim edits, no LLM-authored prose.** Four mechanical transformations only. Replace takes literal token. Wrap prepends literal tag. Delete removes literal span. (P8)
- **Atomic per page.** Edits buffered; written on researcher confirmation. Mid-page abort leaves file untouched.
- **Conditional flag clearance.** Cleared only when every occurrence handled (no skips).
- **Heuristic body mentions tagged `[unverified]`.** Distinguishes wiki-sync's heuristic findings from deterministic frontmatter findings. (P7)
- **In-skill body grep fallback** when `body_stale_mentions` absent.
- **No bulk auto-apply by default.** `--apply-to-all <choice-type>` available *per page* with explicit confirmation; does not span sessions.
- **Idempotent.** Re-invocation after complete session = no-op; after partial = resume from skipped.

## P3 compliance — three load-bearing protections

This skill is the *one* skill that legitimately edits wiki page bodies after creation. Its legitimacy rests on:

1. **Researcher-initiated.** Skill never auto-runs. wiki-sync's nag is a *suggestion*.
2. **Per-occurrence approval.** Every individual body edit shown and approved (or skipped) before being written.
3. **Mechanical only.** Four pre-defined transformations; never composes new prose. Researcher cannot, by approving, accidentally authorize an LLM-authored rewrite — that capability does not exist in the skill.

Weakening any of these three breaks P3 compliance.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions (incl. `--apply-to-all` design, rename-hint surfacing, broken intra-wiki links scope): `reference/open-questions.md`
- Consumed config keys + what this skill reads from other skills' outputs + what it writes: `reference/consumed-config.md`
