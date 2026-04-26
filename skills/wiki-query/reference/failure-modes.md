# `wiki-query` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-query`. Not loaded at LLM runtime — the four most common failure modes are inlined in `SKILL.md`. This file holds the full catalog including edge cases.

---

## Repository state failures

### `wiki/` does not exist

The target repo has not been initialized as a ResearchWiki workspace.

- **Action:** abort with a clear message; do not produce partial output.
- **Recovery suggestion:** `wiki-init --mode new` (or `--mode adopt` if existing notes/code should be preserved).
- **Exit code:** 1.

### Wiki is empty (no `.md` files under `wiki/`)

The workspace is initialized but contains no entries yet.

- **Action:** print "wiki/ is empty — nothing to search". Do not crash.
- **Recovery suggestion:** use `wiki-log` to start journaling.
- **Exit code:** 1.

### Target repo not initialized (no `CLAUDE.md`, no `research-wiki.config.yaml`)

Distinguished from the "empty wiki" case — the workspace itself is missing infrastructure.

- **Action:** abort. Suggest `wiki-init`.
- **Exit code:** 1.

---

## Query failures

### Query is empty or whitespace-only

- **Action:** refuse with usage message.
- **Exit code:** 2 (usage error, distinct from "no results").

### `--scope` value is not a real wiki subdirectory

- **Action:** refuse with the list of valid scopes detected under `wiki/`.
- **Exit code:** 2.

### Zero results match the query

- **Action:** print "0 results"; suggest broadening (drop quotes, try shorter or alternate terms, `--include-meta`).
- **Important:** do **not** guess alternate queries. That would be speculation about what the researcher actually meant. (P8)
- **Exit code:** 1.

---

## Per-page failures (recoverable, do not block search)

### Page parse error (malformed frontmatter, encoding issue)

- **Action:** skip the page; record the failure on stderr; continue.
- **Rationale:** a single broken page should not block the entire search.

### Page is empty (frontmatter only, no body)

- **Action:** scoring proceeds against frontmatter alone. Page may still appear in results if frontmatter matches the query.
- **Note:** typically these are stubs from `wiki-log` or `wiki-deepscan`. The researcher will see them; the badge is not specifically applied (no stale flag), but the empty body will be visible in the snippet (or absent).

### Page is unreadable (permissions, broken symlink)

- **Action:** skip; record on stderr with the OS error.
- **Exit code:** 0 if other pages produced results, 1 if no readable pages remained.

---

## Config failures

### `research-wiki.config.yaml` missing

- **Action:** fall back to built-in defaults (`query.backend: lexical`, `query.stale_warnings: true`, etc.). Warn once on stderr.
- **Exit code:** 0 (does not block).

### Config has an unknown `query.backend` value

- **Action:** fall back to `lexical`; warn on stderr.

---

## Index layer failures (do not block, but degrade quality)

### `index/reverse_refs.json` missing

- **Impact:** none on basic search; only relevant if the researcher was about to use stale-badge information. wiki-query's stale-badge logic reads frontmatter `stale: true` directly, not from the reverse index.
- **Action:** continue normally.

### `index/audits/` does not exist

- **Impact:** none. wiki-query's `--scope all` excludes `index/audits/*` by default; if the directory is missing, the exclusion is trivially satisfied.
- **Action:** continue normally.
