# `wiki-sync` — Worked Examples

> Supplementary material for `wiki-sync`. Not loaded at LLM runtime.

---

## Example 1 — Happy path: morning sync detects changes and flags two stale refs

**Setup.** Target repo: `/home/researcher/attention-study/`. Last sync was yesterday 08:55 against git `bf3ee41`. Current HEAD: `5a3f9e2`. Researcher committed yesterday evening: added a new RotaryEmbedding class, removed the legacy trainer.

**Invocation.**

```
> wiki-sync
```

**Execution trace.**

```
wiki-sync: Loading research-wiki.config.yaml.
  scope: all
  since: 2026-04-22T08:55:11+09:00 (last sync)
  scanner: python=tree-sitter, typescript=tree-sitter
  ignore: [build/, .venv/, **/__pycache__/]

Scanning...
  src/                  → 12 files, 312 symbols (tree-sitter-python)
  wiki/                 → not scanned (not code)
  raw/experiments/      → 2 active experiment directories

Computing diffs against last sync (bf3ee41 → 5a3f9e2)...
  Files:    +1 -1 *2
  Symbols:  +18 -3 (3 of the -3 may be renames; running heuristic)
    - forward_v1 → forward (same file, 87% body similarity) — TAGGED [unverified]
    - (no other rename candidates)

Stale-link pass:
  Scanning 23 wiki pages with refs.code entries...
  Match failures:
    wiki/concepts/auth-flow.md refs LegacyTrainer → not in index
    wiki/experiments/exp-2026-04-19.md refs Model.forward_v1 → not in index
       (forward_v1 was detected as possible rename to forward;
        still flagging as stale until researcher decides)

Writing...
  ✓ index/signatures.json                       (312 symbols, overwritten)
  ✓ index/reverse_refs.json                     (14 paths, 23 referencing pages, overwritten)
  ✓ index/snapshots/sync_20260423_0912.md       (new immutable snapshot)
  ✓ wiki/concepts/auth-flow.md                  (frontmatter: stale: true on 1 ref)
  ✓ wiki/experiments/exp-2026-04-19.md          (frontmatter: stale: true on 1 ref)
  ✓ wiki/questions.md                           (2 notes appended)

Index refreshed (1.8s).
  Files scanned: 12
  Symbols indexed: 312 (+18, -3 since last sync)
  Stale wiki refs flagged: 2
    → wiki/concepts/auth-flow.md references removed LegacyTrainer
    → wiki/experiments/exp-2026-04-19.md references renamed Model.forward_v1
      (rename to `forward` is [unverified] — see snapshot)

Appended 2 notes to wiki/questions.md.
Snapshot written: index/snapshots/sync_20260423_0912.md

⚠ stale 플래그 1개, 9일 이상 미해결. wiki-fix-stale로 처리하시겠어요?
```

The nag is informational — surfaces the accumulating gap and points at the remediation skill, but does not run anything itself. Suppress with `--no-nag`.

**What the researcher sees in `index/snapshots/sync_20260423_0912.md`** (Changes section, abridged):

```markdown
## Changes since previous snapshot
_Previous: index/snapshots/sync_20260422_0855.md_

### Files
- Added:    src/model/rotary.py
- Removed:  src/legacy/old_trainer.py
- Modified: src/trainer.py, src/losses.py

### Symbols
- Added: src/model/rotary.py:RotaryEmbedding (class)
- Added: src/trainer.py:Trainer.save_checkpoint (method)
- ... (16 more)
- Removed: src/legacy/old_trainer.py:LegacyTrainer (class)
- Removed: src/trainer.py:forward_v1 (method) — see rename candidates

### Possible renames (heuristic, [unverified])
- src/trainer.py:forward_v1 → src/trainer.py:forward
  Evidence: same file, adjacent line range, 87% body similarity.
  Alternative reading: forward_v1 deleted, forward added independently.
  Researcher decision needed in wiki/experiments/exp-2026-04-19.md stale ref.
```

The snapshot is immutable history — even if the researcher resolves the stale ref later, this snapshot keeps the record of "as of 2026-04-23 09:12, these refs were stale."

---

## Example 2 — Ambiguity: working tree is dirty mid-refactor

```
> wiki-sync --no-stale-check

wiki-sync: Working tree dirty.
  Uncommitted: 3 modified, 2 untracked.
  Proceeding against working-tree state (not HEAD).

Scanning...
  src/ → 13 files, 298 symbols
    (1 parse error: src/model/new_attention.py line 42 — continuing)

Writing...
  ✓ index/signatures.json                       (298 symbols, overwritten)
  ✓ index/reverse_refs.json                     (overwritten; reflects wiki's declared refs.code as of last frontmatter scan)
  ✓ index/snapshots/sync_20260423_1041.md       (new immutable snapshot, dirty-state flagged)
  - wiki/ frontmatter                           (skipped: --no-stale-check)
  - wiki/questions.md                           (skipped: --no-stale-check)

Index refreshed (1.4s).
  ⚠ Working tree dirty. Snapshot reflects uncommitted state.
  ⚠ 1 parse error — see `## Scan errors` section of the snapshot.
  Stale-link pass was skipped (--no-stale-check).
```

The snapshot's repository header carries `⚠ Scan taken against the **working tree**, not HEAD.` plus the uncommitted file list. Dirty-state snapshots are still valid history, just labeled.

---

## Example 3 — Refusal: target repo not initialized

```
> wiki-sync

wiki-sync: Target repo appears not to be a ResearchWiki workspace.
  Missing: CLAUDE.md
  Missing: research-wiki.config.yaml
  Missing: wiki/

wiki-sync requires an initialized workspace. Run:

  > wiki-init --mode new --language ko --deepscan-tool understand-anything

or --mode adopt if you want to preserve existing code/notes around the wiki
structure. Aborting.
```

No partial output. The researcher must initialize first.

---

## Example 4 — Recovery: scanner times out on one file; run continues

A single file (a generated 30k-line C++ binding stub) trips the scanner timeout. wiki-sync recovers by skipping just that file.

```
> wiki-sync

wiki-sync: Scanning...
  src/bindings/_generated.cpp → TIMEOUT after 10s (file size: 30,287 lines).
    Scanner: tree-sitter-cpp (if available) — not configured.
    Fallback: skip file; record in changes.md.
  src/                        → other 11 files scanned cleanly.

Writing...
  ✓ index/signatures.json                       (overwritten)
  ✓ index/reverse_refs.json                     (overwritten)
  ✓ index/snapshots/sync_20260423_0915.md       (new snapshot, with `## Scan errors` section)
  ✓ wiki/...                                    (stale-link pass ran on unaffected pages)

Index refreshed (2.1s; 10s timeout included).
  Files scanned: 11 (1 skipped due to timeout)
  Symbols indexed: 312 (+18, -3 since last sync)
  Stale wiki refs flagged: 2

Scan errors: 1 (see snapshot).
Suggestion: add `src/bindings/_generated.cpp` to `wiki_sync_ignore:` in
research-wiki.config.yaml if this file is auto-generated and not worth indexing.
```

In `index/snapshots/sync_20260423_0915.md`:

```markdown
## Scan errors
- src/bindings/_generated.cpp: TIMEOUT after 10s.
  Likely cause: very large auto-generated file (30,287 lines).
  Impact on this run: symbols from this file are absent from signatures.json.
  Impact on wiki-log: code auto-link will not find symbols from this file.
  Suggested fix: add to `wiki_sync_ignore:` in research-wiki.config.yaml.
```

The run is considered successful (produced outputs), just with a warning. No wiki-log auto-link will resolve to the skipped file until the researcher either (a) adds it to ignore, or (b) configures a C++ scanner.
