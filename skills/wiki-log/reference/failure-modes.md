# `wiki-log` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-log`. Not loaded at LLM runtime — the most common failure modes are inlined in `SKILL.md`. This file holds the full catalog including edge cases and conversation-flow failures.

---

## Workspace state failures

### Target repo not initialized (no `CLAUDE.md` or `research-wiki.config.yaml`)

- **Action:** abort with a clear message; do not produce partial output.
- **Recovery:** `wiki-init --mode new` (or `--mode adopt` if existing notes/code should be preserved).
- **Exit code:** 1.

### Template not found at configured path

The configured template (e.g., `templates/experiment.md`) does not exist or is unreadable.

- **Action:** fall back to `templates/free_form.md` and warn: "Template for `<type>` not found at `<path>`; falling back to free_form. Check `research-wiki.config.yaml` → `log_templates`."
- **If `free_form.md` is also missing:** abort. This is a `wiki-init` packaging failure, not a researcher-fixable error.

### `index/signatures.json` absent

- **Action:** warn once: "Index Layer not found — running `wiki-sync` first is recommended. Code auto-linking disabled for this entry." Continue with paper / concept / experiment auto-link kinds. Code refs can be added manually post-write.
- **Do not abort** — wiki-log is the most-used skill; refusing to run because of a missing fact-layer artifact would block the researcher unreasonably.

---

## Required-content failures

### Required section blank or placeholder-only

- **Action:** do not write the entry. Re-ask, citing the section name.
- **If researcher explicitly declines** ("skip it", "그냥 넘겨"): abort with no output. The researcher must either provide an answer or change the template's `[required]` flag to `[optional]`.

### Speculation dispute — researcher refuses both grounding and tagging

When a P8 enforcement intervention surfaces hedge / causal / intent claims, the skill offers three routes (rewrite as observation / `[speculation]` tag / move to `wiki/questions.md`). If the researcher rejects all three and insists on writing the speculative claim un-tagged:

- **Action:** abort with no output. Explain that wiki-log will not silently write ungrounded claims into the wiki.
- **Recovery:** the researcher edits the answer themselves or accepts one of the three routes.

---

## File system failures

### Target file already exists at the new entry path

The slug + date combination collides with an existing file.

- **Action:** refuse to overwrite. Offer three choices:
  - (a) change slug to `-v2` (or next available suffix)
  - (b) use `--amend` if within the amend window
  - (c) abort
- **Default:** wait for researcher choice; do not auto-pick.

### Permission error on write

- **Action:** abort the run. Report the offending path and OS-level error.
- **Recovery:** researcher fixes permissions (or chooses a different target directory) and re-invokes.

### Mid-run interrupt (Ctrl-C, network drop)

- **Action:** wiki-log writes are batched at the end of the conversation; mid-run interrupt leaves no files written.
- **Researcher resumes:** re-invoke from scratch. There is no "resume conversation" mode (the conversation state was in memory only).

---

## Auto-link failures

### Auto-link hits ambiguous match (one token → multiple index symbols)

- **Action:** list all candidates; ask the researcher to pick one or none.
- **Important:** do not guess. Ambiguous matches are not auto-resolved by heuristics like "pick the most recent" or "pick the most-referenced".

### Auto-link strategy disabled in template (`enabled: false`)

- **Action:** skip that scan kind silently (it's an explicit template directive). Do not warn.

### Concept stub suggestion: researcher provides a slug that is not a valid identifier

- **Action:** refuse with usage; re-prompt for a valid slug. (Slugs must match `[a-z0-9-]+` and not collide with an existing concept page.)

---

## P3 violations (refusals)

### Researcher asks wiki-log to edit an existing page body

The most common P3 violation request.

- **Action:** refuse politely. Explain P3.
- **Offer concrete alternatives:**
  - (a) edit the file manually
  - (b) log a new entry that supersedes the old one (decision template often fits)
  - (c) run `wiki-sync` if the issue is a stale code ref
- **If the researcher insists:** still refuse. The skill cannot violate P3 even on direct request — that is what makes the wiki trustworthy.

### Researcher asks wiki-log to bulk-import notes

- **Action:** refuse. Explain that wiki-log is one-entry-per-invocation by design.
- **Recovery:** researcher invokes wiki-log once per entry, or writes a script that does the same.

---

## `--amend` failures

### `--amend` with no entry in window

- **Action:** abort with a clear message: "No `<type>` entry within the last `<N>`h. Most recent: `<path>` (`<age>`)."
- **Offer:**
  - (a) edit the file manually
  - (b) write a new entry that supersedes (with a `supersedes:` field in frontmatter)
  - (c) extend the amend window in `config.log.amend_window`

### `--amend` finds the entry but proposed diff doesn't match (researcher described a change to text that doesn't exist)

- **Action:** show the current body; ask the researcher to revise the description. Do not invent a substitution.
