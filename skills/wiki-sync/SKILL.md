---
name: wiki-sync
description: Use this skill when the researcher wants to regenerate the Index Layer — a lightweight, fast snapshot of what the repository currently contains: file tree, function and class signatures, recent diffs, active experiments. This is the morning-ritual skill that fills the daily-cadence gap between manual code reading and the expensive Deep Analysis Layer (`wiki-deepscan`). It also detects stale references in wiki pages (code symbols that no longer exist, renamed, or moved) and flags them — **without editing the wiki bodies themselves** (P3). Trigger phrases include "wiki-sync", "index 업데이트", "코드 스캔 해줘", "stale 링크 체크", "오늘 뭐가 바뀌었어?", "refresh the index", "check for stale links", "sync the wiki", "what changed since yesterday". Do not use for creating new wiki entries (use `wiki-log`), running deep code analysis (use `wiki-deepscan`), auditing overall wiki health (use `wiki-lint`), or initializing the workspace (use `wiki-init`).
---

# wiki-sync

> **Invocation:** `wiki sync [--repo <path>] [--scan-body] [--no-nag] [--no-rename-heuristic]` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Regenerate the Index Layer and flag stale references in the Wiki Layer. The morning ritual — fast enough to run daily, comprehensive enough to catch what the researcher's code changed overnight.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Regenerates `index/` (pure fact). Edits in `wiki/` limited to frontmatter stale flags and append to `wiki/questions.md`. Never touches a wiki page body.
- **P3 — Propose, do not mutate interpretation.** When a `refs.code` entry points to a missing symbol, mark `stale: true` in frontmatter + add a question to `wiki/questions.md`. Researcher decides how to rewrite the body.
- **P4 — Configuration over convention.** `sync.*` config (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Each signature carries `confidence` (`verified` / `inferred` / `dynamic`). Ambiguous rename-vs-delete cases get `[unverified]` in the snapshot. Body-mentions from `--scan-body` carry implicit `[unverified]` semantic.
- **P8 — Analysis yes, speculation no.** "Changes since previous snapshot" lists observable diffs only. Never speculates *why* a symbol was removed or *what the researcher likely intended*.

## When to use

- Start of a research session ("오늘 뭐가 바뀌었어?").
- Before `wiki-log` when significant code work has happened, so auto-link uses up-to-date `signatures.json`.
- When the Index Layer feels stale (e.g., wiki-log auto-link missed an obvious symbol).
- Pre-milestone verification that stale refs have been addressed.

## When NOT to use

- For new wiki entries → `wiki-log`.
- For full knowledge graph refresh → `wiki-deepscan`.
- For health audit (speculation ratios, orphan pages, contradictions) → `wiki-lint`. wiki-sync does the narrow stale-code-ref subset automatically.
- Repo not initialized → `wiki-init` first.
- **After every commit** — daily-cadence skill; every-commit wastes the summary value. Batch.

## Inputs

- `--scope <all | code-only | experiments-only>` (default `all`).
- `--since <git-ref | ISO-date>` (default "since last sync" — read from most recent snapshot or `deep/last-scan.yaml`). Limits diff window in snapshot's "Changes since previous" section.
- `--no-stale-check` — regenerate `index/` only; skip stale-ref pass that touches `wiki/` frontmatter and `wiki/questions.md`.
- `--scan-body` — enable opt-in body link rot scan (heuristic; records `body_stale_mentions:` in frontmatter, tagged `[unverified]` for downstream consumers like `wiki-fix-stale`). Overrides `config.sync.body_link_rot.enabled` (default false).
- `--no-nag` — suppress end-of-run reminder about unresolved stale flags older than `config.sync.nag_after_days` (default 7).

## Outputs

### `index/snapshots/sync_YYYYMMDD_HHMM.md`

Self-contained, **immutable once written**. New file per run; previous never overwritten. Sections: Repository (root, git HEAD, scope, previous snapshot pointer), File tree (depth-limited), Language breakdown, Modules, Active experiments, Changes since previous snapshot (files +/-/*; symbols +/-; possible renames `[unverified]`), Scan errors.

The "latest snapshot" = lexicographically last file in `index/snapshots/`. Consumers (wiki-log `--since`, wiki-lint freshness check) read the directory and pick the last entry. No separate `current.md` pointer.

### `index/signatures.json`

Machine-readable, **overwritten each run**. Consumed by `wiki-log` auto-link.

```json
{
  "schema_version": 1,
  "generated_at": "2026-04-23T09:12:04+09:00",
  "git_ref": "5a3f9e2",
  "symbols": [
    {"path": "src/trainer.py", "symbol": "Trainer", "kind": "class",
     "signature": "class Trainer(base.BaseTrainer):", "line": 42, "confidence": "verified"}
  ]
}
```

### `index/reverse_refs.json`

Machine-readable, **overwritten each run**. Pure inversion of declared `refs.code` frontmatter — no body parsing.

```json
{
  "schema_version": 1,
  "generated_at": "...",
  "by_path": {
    "src/trainer.py": [
      {"page": "wiki/concepts/training-loop.md", "symbols": ["Trainer"]}
    ]
  },
  "stats": {"pages_with_refs": 23, "distinct_paths_referenced": 14}
}
```

Use cases: `jq '.by_path["src/trainer.py"]' index/reverse_refs.json` for impact analysis; future `wiki-where` thin wrapper. wiki-sync does **not** infer additional bindings or scan body prose when building this.

### Body link rot scan (optional, opt-in via `--scan-body`)

Tokenizes body prose by identifier-shape regex (PascalCase + snake_case patterns), looks each token up in `index/signatures.json`. Misses recorded as frontmatter `body_stale_mentions: [{line, token, detected}]`. Implicit `[unverified]` semantic — downstream consumers (notably `wiki-fix-stale`) must surface heuristic nature.

Opt-in because: (a) slowest part of sync, (b) false-positive surface deserves explicit researcher decision.

### Stale-link report (frontmatter + append)

For each wiki page with `refs.code` entries pointing to missing symbols:

1. Frontmatter edit: `stale: true` + `stale_detected: <date>` on the affected ref. (CLAUDE.md §3 permits frontmatter ref edits.)
2. Append to `wiki/questions.md`:
   ```
   ## [<date>] from wiki-sync
   **Stale ref:** <page> references <path>:<symbol>, removed in git <commit>.
   **Action needed:** researcher to decide — update body to new symbol, remove the ref, or accept that the page documents deprecated code.
   ```
3. **Body never touched.**

### End-of-run nag

If unresolved stale flags older than `sync.nag_after_days` exist (and `--no-nag` not set), append one-line reminder to summary: `⚠ stale 플래그 N개, X일 이상 미해결. wiki-fix-stale로 처리하시겠어요?`. Pure surfacing — does not invoke `wiki-fix-stale`.

## Behavior contract

- **Fast.** Whole run completes in seconds on a normal-sized repo. (P2 — low daily friction.)
- **Deterministic.** Same repo state → same outputs. Templated snapshot summary; no LLM creativity.
- **Snapshots immutable.** Once written, never modified. Subsequent runs append new files.
- **Read-only on code.** Never modifies a source file. Scans only.
- **Frontmatter-only edits on `wiki/`.** Stale-link sets `stale: true` + `stale_detected:`. Body never touched. (P3)
- **No speculation in changes section (P8).** Every entry is an observable diff. Rename detection heuristic; uncertain → `[unverified]` with both readings.
- **`wiki/questions.md` append-only.** (P3)
- **Scanner pluggable per language.** MVP: Python (tree-sitter or ctags), TypeScript/JavaScript (tree-sitter). Languages without an adapter reported and skipped, not silently ignored.
- **Respects `.gitignore` and `wiki_sync_ignore:`.** (P4)
- **Does not invoke Understand-Anything.** Cross-module structural analysis is `wiki-deepscan`'s job.
- **Reverse index is pure inversion.** Reflects only declared `refs.code` frontmatter; no inference, no body parsing. (P8 / P1)
- **Body link rot opt-in and `[unverified]`-tagged.** Heuristic; downstream consumers must distinguish from deterministic frontmatter findings. (P7)
- **Nag is surfacing, not enforcement.** wiki-sync does not invoke `wiki-fix-stale`, retry, or block.

## Researcher interaction flow

Usually none — one-shot command. Invocation produces a short summary (see Outputs above) and (optionally) the nag.

If a scanner fails on a specific file, the summary surfaces the failure; the researcher may fix the file or add it to `wiki_sync_ignore:`. No interactive Q&A during a normal run.

## Failure handling (essentials)

- Target repo not initialized → abort, suggest `wiki-init`.
- `wiki/` doesn't exist → generate `index/` only; skip stale-link phase. Not an error.
- Working tree dirty → proceed; snapshot prefixed with `⚠ Working tree dirty`.
- Scanner times out on a file → skip that file; record in `## Scan errors`. Other files scan normally.
- No scanner for a language → warn + skip + continue.
- Config missing → fall back to defaults; warn.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions (incl. snapshot retention, body link rot regex, cross-platform paths): `reference/open-questions.md`
- Consumed config keys + skill-output reads + writes: `reference/consumed-config.md`
