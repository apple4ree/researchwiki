# Skill Spec: `wiki-sync`

> **Frequency:** Roughly once per day (researcher-initiated, often as morning ritual)
> **Tier:** Daily
> **Writes to:** `index/`, frontmatter-only updates in `wiki/`, append to `wiki/questions.md`

## Purpose

Regenerate the Index Layer: a lightweight, fast snapshot of what the repository currently contains (file tree, function and class signatures, recent diffs, active experiments). Detect stale references in the Wiki Layer and flag them without editing the wiki page bodies.

The Index Layer exists because the Deep Analysis Layer (Understand-Anything via `wiki-deepscan`) is too expensive to run on every code change. wiki-sync fills the daily-cadence gap.

## When to invoke

- At the start of a research session ("what changed since yesterday?").
- Before `wiki-log` if significant code work has happened, so auto-links use up-to-date signatures.
- Any time the researcher suspects the Index Layer is stale.

## When NOT to invoke

- For new wiki entries → `wiki-log`.
- For full knowledge graph refresh → `wiki-deepscan`.
- For audit/lint reports → `wiki-lint` (wiki-sync does the narrow stale-code-ref subset automatically).

## Inputs

| Flag | Default | Effect |
|---|---|---|
| `--scope` | `all` | `all \| code-only \| experiments-only` |
| `--since` | last sync | Limits diff window in snapshot |
| `--no-stale-check` | off | Regenerate `index/` only; skip stale-ref pass |
| `--scan-body` | off | Opt-in heuristic body link rot scan; records `body_stale_mentions:` |
| `--no-nag` | off | Suppress end-of-run reminder about old unresolved stale flags |

Consumed config: `paths.{wiki,index,deep,raw}`, `sync.{scope_default, since_default, scanner.*, wiki_sync_ignore, scan_timeout, snapshot_depth_limit, body_link_rot.*, nag_after_days, respect_gitignore}`. See `reference/consumed-config.md`.

## Outputs

1. **`index/snapshots/sync_YYYYMMDD_HHMM.md`** — self-contained, immutable per-run. Sections: Repository, File tree, Language breakdown, Modules, Active experiments, Changes since previous, Possible renames `[unverified]`, Scan errors.
2. **`index/signatures.json`** — overwritten each run. Consumed by `wiki-log` auto-link.
3. **`index/reverse_refs.json`** — overwritten each run. Pure inversion of declared `refs.code` frontmatter (no body parsing, no inference).
4. **Frontmatter `stale: true` + `stale_detected:` on affected wiki pages** — P3-permitted edit on existing pages; bodies untouched.
5. **`body_stale_mentions:`** — when `--scan-body` is on; heuristic, `[unverified]`-tagged.
6. **Append to `wiki/questions.md`** — one entry per stale ref.
7. **End-of-run nag** — informational reminder if old unresolved stale flags exist.

## Behavior contract

- **Fast** — daily-cadence skill; long runs break the habit. (P2)
- **Deterministic** — same repo state → same outputs. Templated snapshot summary; no LLM creativity.
- **Snapshots immutable** — append-only history.
- **Read-only on code** — never modifies source files.
- **Frontmatter-only edits on `wiki/`** — bodies never touched. (P3)
- **No speculation in "Changes since previous"** — observable diffs only; rename heuristic uncertain → `[unverified]` with both readings. (P8)
- **`wiki/questions.md` append-only.** (P3)
- **Scanner pluggable per language** — MVP: Python (tree-sitter / ctags), TypeScript/JavaScript (tree-sitter). Other languages reported and skipped.
- **Respects `.gitignore` + `wiki_sync_ignore:`.** (P4)
- **Does not invoke Understand-Anything** — that is `wiki-deepscan`.
- **Reverse index is pure inversion** — no inference, no body parsing.
- **Body link rot opt-in and `[unverified]`-tagged** — downstream consumers (notably `wiki-fix-stale`) must surface the heuristic nature.
- **Nag is surfacing, not enforcement** — wiki-sync does not invoke `wiki-fix-stale`.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys + skill-output reads + writes: `reference/consumed-config.md`
