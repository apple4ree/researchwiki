# `wiki-recall` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-recall`. Not loaded at LLM runtime.

---

## Workspace state failures

### `wiki/` does not exist

- **Action:** abort. Suggest `wiki-init`.
- **Exit code:** 1.

### Target repo not initialized (no `CLAUDE.md` or `research-wiki.config.yaml`)

- **Action:** abort with a clear message; suggest `wiki-init`.
- **Exit code:** 1.

---

## Empty-corpus failures (skill exits cleanly with helpful direction)

### `wiki/log.md` does not exist or is empty

- **Action:** print "wiki-recall: wiki/log.md is empty or missing. There is no recent-activity corpus to compare stale pages against." Suggest `wiki-log` to start journaling, or `wiki-query` for raw keyword search instead of activity-based recall.
- **Exit code:** 1.

### No log entries within `--lookback` window

- **Action:** print "no log entries in the last N days". Suggest a longer `--lookback`.
- **Exit code:** 1.

### No pages older than `--stale-since`

- **Action:** print "no pages older than N days". Suggest a shorter `--stale-since`.
- **Exit code:** 1.

### Zero results after scoring (overlaps exist but all score 0)

- **Action:** print "0 stale-but-relevant pages found" with the window summary. Suggest broadening (longer lookback, shorter stale-since, `--include-stubs`).
- **Exit code:** 1.

---

## Per-page / per-entry failures (recoverable)

### A specific page fails to parse (malformed frontmatter, encoding issue)

- **Action:** skip the page; record on stderr; continue.
- **Rationale:** a single broken page should not block the recall pass.

### A log entry has malformed frontmatter or refs

- **Action:** skip just that entry; record on stderr; continue with the rest of the lookback window.

### A page has frontmatter `updated:` in invalid date format

- **Action:** skip the page; record on stderr; continue. The skill cannot compute staleness without a parseable date.

---

## Config failures

### `research-wiki.config.yaml` missing

- **Action:** fall back to built-in defaults (`recall.ref_weights = {code: 2.0, concepts: 1.5, papers: 1.0, experiments: 1.0}`, `recall.lookback_default = 30`, `recall.stale_since_default = 60`, `recall.exclude_stubs = true`). Warn once on stderr.
- **Exit code:** 0 (does not block).

### `recall.ref_weights` has unknown keys

- **Action:** ignore unknown keys; warn on stderr. Use known keys; missing known keys default.

---

## Edge cases

### Page is `seeded_by: wiki-log` or `seeded_by: wiki-deepscan` (concept stub)

- **Default:** if `--include-stubs` off (default), exclude. Their `refs.code` is dense from auto-link/graph but body is empty — no real interpretation to revisit.
- **Override:** `--include-stubs` opts in.

### Page's `updated:` field is later than today (clock skew)

- **Action:** treat as freshly updated; skip from the stale candidate set.
