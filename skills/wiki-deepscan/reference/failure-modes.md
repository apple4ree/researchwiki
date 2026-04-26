# `wiki-deepscan` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-deepscan`. Not loaded at LLM runtime.

---

## External tool failures

### Understand-Anything not installed

- **Action:** abort. Report missing binary. Provide install instructions referencing the tool's upstream README.
- **Critical:** do **not** attempt to degrade to a different tool silently. wiki-deepscan is the *only* skill that wraps Understand-Anything; falling back to another tool would silently change the fact surface other skills depend on.
- **Recovery:** install Understand-Anything, then retry. Or use `wiki-sync` for daily code work (`deep/` stays empty until wiki-deepscan runs).

### Understand-Anything version mismatch against `deepscan.tool_version_pin`

- **Action:** warn. If strict pinning enabled, abort; otherwise proceed and note version drift in the report.

### Scan timeout on a large module

- **Action:** retain partial `deep/knowledge-graph.json` if the tool supports streaming. Report the timeout with the file or module that was being processed.
- **Critical:** do NOT overwrite previous `deep/` state with incomplete output. Previous successful scan is preserved.
- **Recovery suggestions:**
  - (a) Add the file to `deepscan.ignore` if it is auto-generated.
  - (b) Increase `deepscan.timeout`.
  - (c) Use `--scope` to narrow the next run.

### Graph output malformed / missing expected fields

- **Action:** abort. Keep previous `deep/` contents (do not partially overwrite). Report the parse failure.
- **Recovery:** typically a tool version mismatch or upstream tool bug. Reinstall or downgrade Understand-Anything.

---

## Workspace state failures

### Target repo not initialized (no `CLAUDE.md` or `research-wiki.config.yaml`)

- **Action:** abort. Suggest `wiki-init`.

### `deep/` does not exist

- **Action:** create it. Not an error.

---

## Stub-creation failures

### Stub target path exists with different purpose (naming conflict)

The skill would create `wiki/concepts/loader.md` for graph node `src/data/loader.py:DataLoader`, but `wiki/concepts/loader.md` already exists with `refs.code` pointing to `src/config.py:ConfigLoader`.

- **Action:** do NOT write. Record in the final report under "Naming conflicts". Append to `wiki/questions.md`:
  ```
  **Naming conflict:** wiki-deepscan would create wiki/concepts/loader.md for
  graph node `src/data/loader.py:DataLoader`, but wiki/concepts/loader.md
  already exists with refs.code pointing to `src/config.py:ConfigLoader`.
  Researcher to resolve: rename one, merge, or accept as distinct concepts.
  ```
- **Recovery:** researcher renames one of the files (e.g., `wiki/concepts/data-loader.md` vs `wiki/concepts/config-loader.md`) and re-runs.

### Graph and existing frontmatter disagree on a symbol location

- **Action:** do NOT auto-correct. Append to `wiki/discrepancies.md` with both readings and source evidence.
- **Recovery:** researcher decides which is correct, manually updates the wiki frontmatter or the code.

---

## Cross-skill coordination failures

### Stale flag from `wiki-sync` already exists for the symbol

When wiki-deepscan would append a note about a graph-vs-frontmatter discrepancy, but `wiki-sync` has already flagged that ref as `stale: true`:

- **Action:** dedup. Do NOT append a duplicate note to `wiki/questions.md`. The researcher already has one open question about that symbol.

### Stub overlaps with `wiki-log` concept stub

When wiki-deepscan would create a stub but `wiki-log` (or a previous wiki-deepscan run) already created one with `seeded_by:` for the same path:

- **Action:** treat as existing page (Naming conflict path) — do not overwrite. Optionally append refs to the existing stub's frontmatter (this is the create-only carve-out for refs).

---

## Per-run scope failures

### `--scope <glob>` matches no files

- **Action:** abort with message; suggest a broader scope or full-repo run.

### `--seed-wiki=true` but no candidates pass `deepscan.stub_edge_threshold`

- **Action:** proceed normally. Report "No new stubs to seed (no components above threshold)." Not an error.

---

## Output failures

### Cannot write to `deep/`

- **Action:** abort. Report OS-level error. Previous `deep/` state preserved.

### Cannot write to `wiki/concepts/<stub>.md`

- **Action:** abort the stub creation phase; record the failure. Existing pages with frontmatter ref additions still complete (those are different files).
