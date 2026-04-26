<!--
  ResearchWiki template: paper_reading
  ------------------------------------
  This file is consumed by `wiki-log` when the researcher creates a paper entry.
  wiki-log does three things with it:

    1. Parses the YAML frontmatter below. Keys prefixed with `_` (e.g., `_template`)
       are template-only directives and are NOT copied to the resulting entry.
    2. Copies the remaining frontmatter to the new entry, substituting placeholders
       in `{{DOUBLE_BRACES}}` with session-captured values.
    3. Walks the markdown body below, turning each `##` header into a conversational
       prompt. Sections marked `[required]` must be non-empty before wiki-log writes
       the entry.

  Placeholders wiki-log fills automatically:
    {{DATE}}        ISO date (YYYY-MM-DD) at the moment of creation.
    {{SESSION_ID}}  The current LLM session identifier.
    {{PAPER_ID}}    Short slug supplied by the researcher; also the filename stem.
    {{TITLE}}       Human-readable title provided by the researcher.

  Do not edit the blocks below unless you want to change the template globally.
  For per-entry deviations, edit the generated entry file, not this template.
-->

---
# ===== Entry frontmatter (copied to the new entry) =====

schema_version: 1
type: paper
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

# Paper-specific metadata (objective citation facts)
paper_id: {{PAPER_ID}}         # Short slug; also the filename stem
authors: []                    # e.g., ["Vaswani", "Shazeer", ...]
year: null
venue: null                    # e.g., "NeurIPS 2017"
source_url: null               # DOI, arXiv URL, or local PDF path

# ===== Template-only config =====

_template:
  auto_link:
    code:
      enabled: false           # Paper entries rarely reference your codebase directly
    papers:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    experiments:
      enabled: false
---

# {{TITLE}}

## Key claim  [required]

*What does the paper assert, in one or two sentences? Use the paper's own framing
where possible. If the paper makes multiple claims, put the one most relevant to
your work here and capture the rest in "Other claims" below.*

## Method summary  [required]

*How does the paper produce its claim? In your own words — a paraphrase of the
method, not a reproduction of the paper's prose. Keep to what the paper explicitly
states; do not fill in implied steps (P8).*

## Relevance to my work  [required]

*Why is this paper in your wiki? Connect to a specific concept, experiment, or
design decision in your research. Reference by slug if it already exists — wiki-log
will auto-link.*

## Other claims  [optional]

*Secondary claims the paper makes, listed briefly. One line each.*

## Open questions  [optional]

*Questions the paper leaves unanswered that matter for your work. Also: questions
about the paper itself — unclear definitions, missing details. The contents of
this section are appended to `wiki/questions.md`.*

## Related concepts  [optional]

*Concepts discussed in the paper that overlap with your wiki. Use slugs where
possible; wiki-log scans this section for exact concept matches.*

## Citations of interest  [optional]

*Papers cited by this paper that you want to follow up on. One line each, in the
form `- paper-slug — why this citation matters`.*
