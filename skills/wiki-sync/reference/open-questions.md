# `wiki-sync` — Open Questions

> Supplementary material for `wiki-sync`. Not loaded at LLM runtime.

---

## 1. Trigger `wiki-log` auto-link re-evaluation for recent entries?

**Status:** rejected.

After a sync that introduces new symbols, the recent wiki-log entries' auto-linked refs might be improvable (wiki-log saw fewer symbols at the time it ran).

**Rejected:** keep skills separate. The researcher can manually re-run wiki-log auto-link by amending an entry if it matters. Coupling wiki-sync to wiki-log would obscure the boundary.

---

## 2. Scanner partial parse errors

**Status:** decided — log the error, include what it could parse.

**Rationale:** partial information beats none. wiki-log auto-link can use whatever symbols the scanner did extract; the `## Scan errors` section in the snapshot informs the researcher of what's missing.

---

## 3. `.gitignore` and `wiki_sync_ignore:` interaction

**Status:** decided.

Scanner respects both:
- `.gitignore` (always, for parity with researcher's existing version-control state)
- Explicit `wiki_sync_ignore:` list in `research-wiki.config.yaml` (for files the researcher wants to keep tracked but not indexed — e.g., generated bindings)

Both are union, not exclusive.

---

## 4. Body link rot regex strictness

**Status:** MVP defaults set, looser regex reserved for v1.1.

MVP token patterns:
- PascalCase: `[A-Z][A-Za-z0-9_]*\(?`
- snake_case: `[a-z_][a-z0-9_]+\(` (requires trailing `(` to capture function calls in prose)

Looser regex catches more stale mentions but more false positives. Configurable via `sync.body_link_rot.token_regex:` — reserved.

**Open:** what is the right "loose" alternative? Some researchers may want `_under_score_names` matched without the trailing `(`. Defer until first real-world feedback.

---

## 5. Body link rot for symbols with changed `kind`

E.g., a class becomes a function (`Trainer` was a class; now a factory function with the same name).

**Proposed:** no — body link rot only flags **missing** tokens, not **changed-kind** tokens. The latter is "soft drift" — the symbol still exists. `wiki-lint` Check #7 (confidence conflict) is the right place if multiple wiki pages disagree on the kind.

---

## 6. Snapshot retention policy

**Status:** undecided.

`index/snapshots/` accumulates indefinitely (one file per sync). Over years this is large. Markdown is small (~2-10KB per snapshot), so a year of daily snapshots is ~1-3MB — acceptable for most repos.

**Proposed:** no auto-cleanup. The snapshot history is a research provenance artifact and worth keeping. If a researcher wants to prune, they do so manually with `rm` or `git rm`.

**Reconsider:** if monorepo snapshots grow unwieldy, add `sync.snapshot_retention_days:` config (rolling window).

---

## 7. Cross-platform paths in `index/signatures.json`

**Status:** decided — POSIX paths.

All paths are recorded relative to the repo root using POSIX separators (`/`). Windows users see `src/trainer.py`, not `src\trainer.py`. The path is canonical for cross-platform comparison and for the reverse_refs lookup.
