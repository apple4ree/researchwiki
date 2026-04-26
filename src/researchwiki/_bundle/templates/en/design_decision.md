<!--
  ResearchWiki template: design_decision
  --------------------------------------
  This file is consumed by `wiki-log` when the researcher creates a decision entry.
  wiki-log does three things with it:

    1. Parses the YAML frontmatter below. Keys prefixed with `_` (e.g., `_template`)
       are template-only directives and are NOT copied to the resulting entry.
    2. Copies the remaining frontmatter to the new entry, substituting placeholders
       in `{{DOUBLE_BRACES}}` with session-captured values.
    3. Walks the markdown body below, turning each `##` header into a conversational
       prompt. Sections marked `[required]` must be non-empty before wiki-log writes
       the entry.

  Placeholders wiki-log fills automatically:
    {{DATE}}         ISO date (YYYY-MM-DD) at the moment of creation.
    {{SESSION_ID}}   The current LLM session identifier.
    {{DECISION_ID}}  Short slug supplied by the researcher; also the filename stem.
    {{TITLE}}        Human-readable title provided by the researcher.

  Do not edit the blocks below unless you want to change the template globally.
  For per-entry deviations, edit the generated entry file, not this template.
-->

---
# ===== Entry frontmatter (copied to the new entry) =====

schema_version: 1
type: decision
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

# Decision lifecycle metadata (state, not interpretation)
decision_id: {{DECISION_ID}}
status: proposed               # proposed | accepted | superseded | rejected | deprecated
supersedes: []                 # list of decision_ids this decision replaces
superseded_by: []              # populated later if a newer decision replaces this one
scope: []                      # paths, domains, or components affected

# ===== Template-only config =====

_template:
  # Design decisions tend to touch code directly, reference concepts, and respond
  # to experiment results. All four link types enabled, with code scanning most
  # aggressive since decisions usually implicate specific files or symbols.
  auto_link:
    code:
      enabled: true
      strategy: identifier_token
      default_confidence: verified
    papers:
      enabled: true
      strategy: exact_slug
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    experiments:
      enabled: true
      strategy: exact_id
      link_bidirectional: true
---

# {{TITLE}}

## Problem  [required]

*What problem does this decision solve? State the problem, not the solution.
One or two sentences.*

## Options considered  [required]

*What alternatives did you evaluate? List at least two. For each: one-line
description. No ranking yet — ranking happens in "Rationale".*

## Chosen approach  [required]

*Which option did you pick, and in what form? Reference the chosen option by name
from "Options considered". Include only the observable decision — implementation
details belong in the linked code, not here.*

## Rationale  [required]

*Why did you choose this option over the alternatives? Ground each reason in
evidence — an experiment result, a paper, a known constraint. If a reason is
a judgment call rather than evidence-backed, say so explicitly (P8).*

## Tradeoffs  [optional]

*What does the chosen approach cost you? List what this decision makes harder,
not just what it makes easier.*

## Scope of impact  [required]

*Which code paths, modules, or research directions are affected? Reference by
path or concept slug — wiki-log auto-links these.*

## Revisit conditions  [optional]

*Under what conditions should this decision be reopened? Specific triggers help
future-you recognize when it is time to supersede this decision.*
