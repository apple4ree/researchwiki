# CLAUDE.md — ResearchWiki Constitution

> This file is the **Hot Memory** constitution for any LLM agent session operating on a ResearchWiki-enabled repository.
> It is read first, it is read fully, and its rules override session-level conveniences.
> Agents that do not follow this file produce output that violates the researcher's trust contract and must stop.

---

## 1. What this repository is

This repository is a **research workspace** maintained with the ResearchWiki skill set. It contains:

- Active research code (under frequent revision)
- A living research journal in `wiki/` (the Wiki Layer — interpretation)
- An automatically regenerated fact index in `index/` (the Index Layer)
- Optionally, a deeper code knowledge graph in `deep/` (the Deep Analysis Layer)
- Raw sources in `raw/` (papers, experiment logs; may live elsewhere per config)

See `ARCHITECTURE.md` for the full design rationale. This file codifies only the **operational rules** an agent must follow when acting on this repository.

## 2. The inviolable principles

These are restated from `ARCHITECTURE.md §1.4` because an agent is required to obey them without having to reason about them.

**P1 — Fact and interpretation are separate.**
`wiki/` is interpretation. `index/` and `deep/` are facts. Never merge them. Never move content from one to the other without an explicit instruction.

**P3 — Propose, do not mutate interpretation.**
You may freely regenerate anything in `index/` and `deep/`. You may **not** silently rewrite anything in `wiki/`. When you detect that a wiki page is stale, contradictory, or incomplete, you (a) update **only the frontmatter metadata** if it concerns fact-layer references, and (b) append a note to `wiki/questions.md`. You do not rewrite the page body. The researcher decides whether and how to update the body.

**P7 — Every claim has provenance.**
When you write anything, tag its origin. For frontmatter: `authored_by: llm | human | hybrid`, `confidence: verified | inferred | dynamic`. For inline content: quote sources, or mark as `[speculation]` if the statement cannot be grounded.

**P8 — Analysis yes, speculation no.** *(the hard one)*

You may write:
- Summaries of content that is explicitly in the sources
- Descriptions of observable relationships (X calls Y; paper A cites paper B)
- Juxtapositions revealing similarity, difference, or contradiction between sources
- Direct statements supported by grounded evidence

You may **not** write:
- Guesses about what a developer *intended* that the code does not state
- Extensions of what a paper *implies* beyond what it explicitly says
- Causal explanations for experiment outcomes not supported by the logs
- Design critique the researcher did not ask for and which is not grounded in concrete evidence

When in doubt:
- Prefer a **question** over an **assertion** ("intent here is unclear — confirm with the researcher")
- Use the `[speculation]` or `[unverified]` tag inline
- If the entire claim would be speculation, omit it

Violating P8 is the single most damaging thing you can do in this workspace. It slow-poisons the knowledge base with plausible-but-wrong claims that the researcher may not catch for weeks.

## 3. Directory contract

An agent must understand what it is allowed to touch in each location.

| Path | Owner | Agent may create | Agent may edit | Agent may delete |
|---|---|---|---|---|
| `CLAUDE.md` | human | no | no | no |
| `ARCHITECTURE.md` | human | no | on explicit request | no |
| `research-wiki.config.yaml` | human | on `wiki-init` only | on explicit request | no |
| `wiki/*.md` body content | human+LLM | yes (via `wiki-log`) | **only with explicit researcher approval or researcher-initiated request** | no |
| `wiki/*.md` frontmatter `refs:` block | fact layer | yes | yes (stale-link updates allowed) | yes (on explicit request) |
| `wiki/index.md` | LLM | yes | yes | no |
| `wiki/log.md` | LLM | yes | append-only | no |
| `wiki/questions.md` | LLM | yes | append-only | no |
| `wiki/discrepancies.md` | LLM | yes | yes | no |
| `index/*` | tool | yes (regenerate) | yes | yes |
| `deep/*` | tool | yes (regenerate) | yes | yes |
| `raw/*` | human | no | no | no |
| `templates/*` | human | on `wiki-init` only | on explicit request | no |

**Reading this table as an agent:** before writing anything, find the path in the table. If "may edit" is not unconditionally `yes`, stop and confirm with the researcher.

## 4. Skills you should prefer

If any of these skills are loaded in the current session, use them for the corresponding task rather than freelancing.

**MVP (life-cycle):**

- `wiki-init` — first-time setup only. Never run on an already-initialized repo without explicit instruction.
- `wiki-log` — all additions to `wiki/`. Use the template system, not ad-hoc page creation.
- `wiki-sync` — all regeneration of `index/` (signatures, snapshots, reverse-ref index) and all stale-link scanning.
- `wiki-deepscan` — all invocations of Understand-Anything. Do not run the underlying tool directly.
- `wiki-lint` — all audit passes. Never silently do linting work as a side effect of another task.

**Retrieval extensions (read-only):**

- `wiki-query` — natural-language search over wiki contents. Returns ranked page paths + extractive snippets only; never composes an answer.
- `wiki-recall` — surfaces stale-but-relevant pages by intersecting recent log activity with old-page frontmatter refs. Pointers + overlap evidence only; never summarizes.

**Remediation (the *one* skill that legitimately edits wiki page bodies after creation):**

- `wiki-fix-stale` — addresses unresolved stale refs that `wiki-sync` flagged. Strict P3 carve-out: researcher-initiated invocation + per-occurrence approval of every individual edit + only four pre-defined mechanical transformations (replace symbol, wrap-deprecated, delete sentence, skip). The skill never composes new prose. **No other skill edits a wiki page body.**

If none of these skills are loaded but the task clearly fits one, tell the researcher which skill is missing.

## 5. Frontmatter you must write correctly

Every new page under `wiki/` must have frontmatter matching this schema. See `ARCHITECTURE.md §2.3` for rationale.

```yaml
---
schema_version: 1
type: concept | paper | experiment | decision | other
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
refs:
  code: []     # list of {path, symbol, confidence}
  papers: []   # list of paper IDs from wiki/papers/
  concepts: [] # list of concept slugs
  experiments: [] # list of experiment IDs
authored_by: human | llm | hybrid
source_sessions: []
---
```

Missing frontmatter is grounds for the `wiki-lint` skill to flag the page as malformed. Always write frontmatter. Always use the schema.

Some skills add **optional fields** to specific pages (this is not a free-for-all — each field below is written by exactly one skill, in defined conditions):

- `refs.code[].stale: true` and `refs.code[].stale_detected: YYYY-MM-DD` — written by `wiki-sync` when the symbol is missing from `index/signatures.json`. Cleared by `wiki-fix-stale` after the researcher addresses the body.
- `body_stale_mentions: [{line, token, detected}]` — written by `wiki-sync` when invoked with `--scan-body`. Heuristic, implicitly `[unverified]`.
- `seeded_by: wiki-log | wiki-deepscan` and `seed_context: { from_entry, from_phrase | from_node_id, ... }` — written when the page is auto-created as a stub. Marks pages whose body is initially empty, for downstream skills (notably `wiki-lint`'s orphan check) to give grace-period treatment.
- `tags: [auto-seeded]` — added by `wiki-deepscan` to graph-seeded stubs.

Do not invent additional optional fields without extending this list.

## 6. Language policy

- Korean is the default documentation language.
- Each wiki entry is written in the **dominant language of the session that produced it**. A session in English produces English pages; a session in Korean produces Korean pages.
- You do not automatically translate between languages. Cross-language links between pages are fine.
- All content in this repository is assumed to be public-safe. You do not need to implement redaction, but do not introduce content that the researcher did not author or import.

## 7. What to do when you are uncertain

1. Prefer a short, truthful answer over a long, speculative one.
2. Prefer asking a clarifying question over guessing the researcher's intent.
3. Prefer writing less to `wiki/` and more to `wiki/questions.md`.
4. If a skill would require speculation to complete its output, stop the skill and explain what source is missing.

Uncertainty well-tagged is more valuable than confidence poorly grounded.

## 8. What to do at session start

On every new session operating on this repository:

1. Read `CLAUDE.md` fully (this file).
2. Glance at `ARCHITECTURE.md` table of contents if the task touches architecture.
3. Glance at `wiki/index.md` to know what already exists.
4. Glance at `wiki/log.md` tail to know recent context.
5. Check `research-wiki.config.yaml` for paths and template overrides.

Skipping step 1 is a protocol violation.

---

*This file is authored by the researcher. It changes rarely. When it changes, it is a deliberate governance event, not an automated edit.*
