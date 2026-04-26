<!--
  ResearchWiki template: free_form
  --------------------------------
  This file is consumed by `wiki-log` when the researcher creates a free-form entry.
  wiki-log does three things with it:

    1. Parses the YAML frontmatter below. Keys prefixed with `_` (e.g., `_template`)
       are template-only directives and are NOT copied to the resulting entry.
    2. Copies the remaining frontmatter to the new entry, substituting placeholders
       in `{{DOUBLE_BRACES}}` with session-captured values.
    3. Walks the markdown body below, turning each `##` header into a conversational
       prompt. Sections marked `[required]` must be non-empty before wiki-log writes
       the entry.

  free_form is intentionally the lightest template — it is the escape hatch for
  content that does not fit the other three types. If you find yourself writing
  many free_form entries with the same shape, propose a new template type.

  Placeholders wiki-log fills automatically:
    {{DATE}}        ISO date (YYYY-MM-DD) at the moment of creation.
    {{SESSION_ID}}  The current LLM session identifier.
    {{TITLE}}       Human-readable title provided by the researcher.
-->

---
# ===== Entry frontmatter (copied to the new entry) =====

schema_version: 1
type: other
created: {{DATE}}
updated: {{DATE}}
tags: []

refs:
  code: []
  papers: []
  concepts: []
  experiments: []

authored_by: hybrid            # P3/P8: wiki-log forbids `llm`. Researcher-only is `human`.
source_sessions: [{{SESSION_ID}}]

# ===== Template-only config =====

_template:
  # free_form entries are intentionally low-structure. Auto-link is disabled by
  # default to prevent false positives on unstructured prose. The researcher adds
  # `refs:` manually (see "Links" section below) when a link is actually wanted.
  auto_link:
    code:
      enabled: false
    papers:
      enabled: false
    concepts:
      enabled: false
    experiments:
      enabled: false
---

# {{TITLE}}

## Notes  [required]

*Whatever you want to record. No structure imposed. One paragraph or ten.
If you find yourself repeatedly writing the same shape of content in free_form
entries, consider proposing a new template type — repeated structure is a
signal, not clutter.*

## Links  [optional]

*Manual refs. One line each, in the form `- <kind>: <slug> — context`, where
`<kind>` is one of `code`, `paper`, `concept`, `experiment`. wiki-log reads
this section at write time and promotes confirmed entries into `refs:` in
frontmatter.*

<!--
  Example (delete in the actual entry):
  - paper: transformer-2017 — referenced while thinking about attention cost
  - concept: temperature — related to the temperature-gap issue
-->
