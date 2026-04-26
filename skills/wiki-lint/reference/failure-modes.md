# `wiki-lint` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-lint`. Not loaded at LLM runtime.

---

## Workspace state failures

### `wiki/` does not exist

- **Action:** abort. Suggest `wiki-init`. No partial output.

### Target repo not initialized (no `CLAUDE.md` or `research-wiki.config.yaml`)

- **Action:** abort with a clear message. Suggest `wiki-init`.

### `index/` does not exist

- **Action:** warn; skip the checks that depend on it (Check 4 — `refs.code.path` file existence — and Check 6 — persistent-stale-ref age — both need fresh index data). Run remaining checks. Audit report header notes the partial-run state explicitly.

### `index/audits/` does not exist

- **Action:** `wiki-init` creates this directory at workspace bootstrap; if absent, the workspace was initialized before that change. Create as defensive fallback. Note the creation in the summary.

---

## Config failures

### `research-wiki.config.yaml` missing

- **Action:** fall back to built-in defaults (`speculation_threshold: 0.30`, `stale_age_days: 7`, `strict_mode: false`). Warn in the summary and the report header. Mirrors `wiki-sync`'s behavior.

### Unknown `lint.*` keys

- **Action:** ignore unknown keys; warn on stderr.

### `lint.speculation_threshold` out of [0.0, 1.0]

- **Action:** abort with usage. Density is a ratio; values outside [0.0, 1.0] are nonsensical.

---

## Per-page failures (recoverable, do not block audit)

### Frontmatter parse error on a specific page

- **Action:** record in the audit report's `## Scan errors` section. Continue with remaining pages.
- **Rationale:** a single broken page should not block the audit.

### Speculation tokenizer cannot parse a page

- **Action:** record in `## Scan errors`. The page contributes 0 to the speculation count for that run. Note the omission.

### Page has malformed `refs:` block

- **Action:** treat as if the broken kind is empty for that page. Other checks (frontmatter required-field, links, orphans) still run normally.

### Page is missing entirely (referenced from `wiki/index.md` but file not present)

- **Action:** record in `## Scan errors`. Other pages' link-existence checks (Check 3) will also flag this as a broken link from any page that refers to it.

---

## Check-specific edge cases

### Check 5 (speculation density) — page has 0 sentences (frontmatter only)

- **Action:** density is undefined (0/0). Skip the page from this check. Note in `## Scan errors`.

### Check 6 (persistent stale-ref age) — `stale_detected:` field missing or in invalid date format

- **Action:** the stale ref cannot be aged. Skip from this check; record in `## Scan errors`. The frontmatter integrity check (Check 1) will already flag the malformed field if applicable.

### Check 7 (confidence conflict) — same symbol, three or more pages, two distinct values

- **Action:** report all pages involved as one finding. The discrepancies.md entry lists every page and its claimed confidence.

### Check 8 (orphan) — page is `seeded_by:` (stub from wiki-log or wiki-deepscan)

- **Action (default):** *no special handling in MVP* — stubs may appear as `info · orphans` and that is documented in `wiki-log/SKILL.md`. **Known follow-up** (per `ARCHITECTURE.md` Appendix B 2026-04-25): refine Check #8 to honor `seeded_by:` markers with a grace period (a stub is *expected* to be orphan at creation time).

---

## Output failures

### Cannot write to `index/audits/`

- **Action:** abort *after* completing the scan. Print the audit report to stdout instead so the researcher does not lose the work. Report the OS-level error.

### Cannot append to `wiki/questions.md` or `wiki/discrepancies.md`

- **Action:** report the failure. The audit report itself was already written (it is the canonical record). The researcher can manually copy the to-be-appended entries from the audit report.

---

## `--strict` mode interactions

### `--strict` and zero findings

- **Action:** exit 0. Strict mode does not require *any* findings; it only escalates *existing* findings to error severity.

### `--strict` and `--no-write` (dry-run)

- **Action:** allowed. Print the would-be findings (escalated to error). Exit 1 if any finding survives. Useful for CI dry-runs to predict whether the next non-dry-run would gate a release.
