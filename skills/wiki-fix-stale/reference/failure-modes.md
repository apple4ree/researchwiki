# `wiki-fix-stale` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-fix-stale`. Not loaded at LLM runtime.

---

## Workspace state failures

### `wiki/` does not exist

- **Action:** abort. Suggest `wiki-init`.

### Target repo not initialized (no `CLAUDE.md` or `research-wiki.config.yaml`)

- **Action:** abort. Suggest `wiki-init`.

### No stale-flagged pages exist (nothing to fix)

- **Action:** print "no stale flags to fix"; exit 0. Do not nag — wiki-fix-stale is researcher-initiated; if there is nothing to do, the answer is "ok, done".

---

## Per-page resolution failures

### Stale flag exists but symbol not found in body (false positive)

The frontmatter says `stale: true on OldAttention` but body grep finds no occurrences of `OldAttention`. Likely the symbol was only ever in `refs.code`, never mentioned in body prose.

- **Action:** offer two narrow options:
  - (a) Clear the frontmatter flag (no body edits)
  - (b) Skip and leave the flag
- **Default:** wait for researcher choice.
- **Important:** do not attempt body edits. The whole point of this skill is per-occurrence approval; if there are no occurrences, there is nothing to approve.

### `body_stale_mentions` entries point to lines that no longer match

The page was edited (manually or via another skill) since the last `wiki-sync` body link rot scan. The recorded line numbers no longer match the symbol mentions they were created for.

- **Action:** skip those entries; record on stderr; continue with the rest of the page.
- **Recovery:** the next `wiki-sync --scan-body` will produce fresh `body_stale_mentions` if the symbols still exist in body prose at new locations.

### Page has been modified by the researcher since `stale: true` was set, and the symbol no longer appears anywhere in the body

- **Action:** treat as fixed-out-of-band; offer to clear the frontmatter flag without further edits.

---

## Edit-action failures

### Edit option 1 (replace) — researcher-supplied name is not a valid identifier

The new name fails identifier validation (e.g., contains spaces, starts with a digit, contains punctuation other than `_`).

- **Action:** refuse with usage; re-prompt for a valid identifier. Do not abort the page or session.

### Edit option 3 (delete sentence) — sentence boundary ambiguous

Examples: abbreviations (`e.g.`, `et al.`), code spans containing periods (`Trainer.train_one_epoch`), or text where punctuation is sparse.

- **Action:** show candidate boundaries (the skill's best guesses) and ask the researcher to pick one or write a custom span.
- **Important:** do not auto-pick. Sentence-boundary judgment is a researcher concern when ambiguous.

### Researcher tries to invent an option not in the menu (e.g., "rewrite the paragraph for me")

- **Action:** politely refuse. Explain the four-option constraint. Offer to **skip** this occurrence so the researcher can manually edit later.
- **Rationale:** wiki-fix-stale's P3 compliance rests on the four mechanical transformations being the only edits possible. Allowing free-form edits would require LLM-authored prose, which the skill does not do.

---

## Session-flow failures

### Researcher exits mid-page (Ctrl-C, abort, "stop")

- **Action:** that page's in-memory edits are discarded; the file remains untouched.
- **Already-written pages remain.** The session record (appended at end of session normally) is appended *with what completed*, listing the page where work stopped.

### Researcher exits mid-session (between pages)

- **Action:** completed pages stay written. The current page (in-memory only) is not touched. Append session record with partial summary.

### `--page <path>` references a page without stale flags

- **Action:** print "no stale flags on <path>"; exit 0.
- **Recovery:** invoke without `--page` to walk all stale-flagged pages.

---

## Config failures

### `research-wiki.config.yaml` missing

- **Action:** fall back to defaults (`fix_stale.auto_clear_flags = true`, `fix_stale.include_body_mentions = auto`, `fix_stale.oldest_first = true`). Warn once on stderr.
- **Exit code:** 0 (does not block).

### `research-wiki.config.yaml` has unknown `fix_stale.*` keys

- **Action:** ignore unknown keys; warn on stderr.
