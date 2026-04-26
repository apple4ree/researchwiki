# Skill Spec: `wiki-deepscan`

> **Frequency:** Weekly, or at research milestones, on researcher's initiative
> **Tier:** Weekly / milestone
> **Writes to:** `deep/`, and wiki stubs in `wiki/` (new only; never overwrites existing). Frontmatter ref additions on existing pages allowed (P3-permitted; bodies untouched).

## Purpose

Run the Understand-Anything pipeline against the repository and produce the Deep Analysis Layer: a full knowledge graph, layer classification, guided tours. Use the output to (a) refresh what the wiki knows about the code, and (b) generate stub pages for newly significant components that do not yet have a wiki entry.

The Deep Analysis Layer is a fact surface. Wiki stubs generated here are **minimal scaffolding** — empty interpretation slots for the researcher to fill later.

## When to invoke

- Weekend refresh before a new sprint of research.
- Before a major decision requiring cross-cutting structure (large refactor, paper-ready experiment, milestone).
- At research milestones (paper submission, refactor completion).
- When the researcher notices the Index Layer is not enough to answer a structural question.

## When NOT to invoke

- Daily — too expensive; that is `wiki-sync`'s job.
- Mid-active-refactor — the graph reflects a moving target.
- As a substitute for reading code — the deep layer is an index, not understanding.

## Inputs

| Flag | Default | Effect |
|---|---|---|
| `--incremental` | `true` | Reuse unchanged graph regions when `deep/last-scan.yaml` matches |
| `--seed-wiki` | `true` | Generate stub wiki pages for newly prominent components |
| `--scope` | full repo | Glob to limit the scan (e.g., `src/model/`) |
| `--dry-run` | off | Report graph deltas, stubs to create, refs to add — without writing |

Consumed config: `paths.{wiki,deep,index}`, `deepscan.{tool, tool_path, tool_version_pin, strict_version_pin, timeout, incremental_default, seed_wiki_default, stub_edge_threshold, ignore}`. See `reference/consumed-config.md`.

## Outputs

1. **`deep/knowledge-graph.json`** — overwritten each run. Full Understand-Anything output (nodes, edges, layer classification, symbols, call graph, guided tours).
2. **`deep/last-scan.yaml`** — overwritten each run. Metadata for next `--incremental`.
3. **Wiki stub pages** (when `--seed-wiki=true`) — one per newly significant graph node lacking a wiki page (≥`deepscan.stub_edge_threshold` inbound edges). Frontmatter + structural-facts body + open-questions template + italicized "add interpretation here". `authored_by: llm`, `tags: [auto-seeded]`.
4. **Frontmatter ref additions on existing wiki pages** — append verified `refs.code` entries that the new graph reveals. Frontmatter-only; bodies untouched (P3-permitted).
5. **Run report** at `deep/deepscan-report-<date>.md` + stdout summary.

## Behavior contract

- **External tool invocation.** *Only* skill that wraps Understand-Anything. Other skills read `deep/` but never invoke the tool. (`ARCHITECTURE.md §3.2`)
- **Overwrites `deep/`.** Deep layer is regeneratable fact. (P1)
- **Never overwrites existing wiki page body (P3).** Stub creation is create-only.
- **Stubs are structural scaffolding only (P8).** Bodies = file path + symbols + inbound callers + open-questions template. No prose about purpose, quality, design, or "is for".
- **`authored_by: llm` on every stub.**
- **Never invents purpose prose.** Graph ambiguity → `confidence: dynamic` on the ref; never a prose guess about intent.
- **Incremental mode reuses unchanged regions.**
- **Naming conflicts flagged, not resolved** — log to `wiki/questions.md` + report.
- **Graph-vs-frontmatter discrepancies → `wiki/discrepancies.md`** — never auto-correct.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys + skill-output reads + writes: `reference/consumed-config.md`
