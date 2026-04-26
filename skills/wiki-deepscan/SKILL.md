---
name: wiki-deepscan
description: Use this skill when the researcher wants to run Understand-Anything against the repository and refresh the Deep Analysis Layer (`deep/knowledge-graph.json`, `deep/last-scan.yaml`) — the weekly or milestone-cadence refresh that provides the rich fact surface for cross-cutting structural questions. It optionally seeds new wiki stub pages for architecturally significant components that do not yet have a wiki entry. Trigger phrases include "wiki-deepscan", "deep scan", "knowledge graph 업데이트", "Understand-Anything 돌려줘", "주말 리프레시", "milestone 전 지식 그래프 갱신", "weekend refresh", "refresh the deep layer", "run Understand-Anything". Do not use for daily code refresh (use `wiki-sync` — wiki-deepscan is too expensive for daily), new wiki entries (use `wiki-log`), wiki health audits (use `wiki-lint`), or initialization (use `wiki-init`). Do not use during an active refactor — wait until code stabilizes. This skill requires Understand-Anything to be installed on the researcher's machine; it does not auto-install.
---

# wiki-deepscan

Run Understand-Anything and refresh the Deep Analysis Layer. Seed stub wiki pages for newly significant components. The weekend / milestone ritual — expensive, deliberate, worth doing at a cadence where its findings actually get acted on.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Writes fact artifacts (`deep/`) and creates scaffold-only stub pages in `wiki/`. Any interpretation the stubs eventually carry is filled in by the researcher via `wiki-log` or direct editing, not by this skill.
- **P3 — Propose, do not mutate interpretation.** Stub generation is **create-only**. If a wiki page already exists for a component, may append verified `refs.code` to its frontmatter but **never** touches body. Naming conflicts flagged, not overwritten.
- **P4 — Configuration over convention.** `deepscan.*` config (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Stubs carry `authored_by: llm`. Refs added to existing pages carry `confidence: verified` only when the graph node has a direct, unambiguous file/symbol binding; ambiguous bindings get `confidence: dynamic`.
- **P8 — Analysis yes, speculation no.** Stub bodies contain **structural facts only** — file path, exposed symbols, inbound callers from the graph. They do **not** contain LLM-generated prose about purpose, design quality, or what the component "is for." Those are the researcher's job.

## When to use

- Weekend refresh before a new sprint of research.
- Before a major decision requiring cross-cutting structural understanding (large refactor, paper-ready experiment, publication cut).
- At research milestones — paper submission, refactor completion, checkpoint release.
- When `wiki-sync` alone cannot answer a structural question (e.g., "who uses this helper across all layers?").

## When NOT to use

- **Daily.** Cost is minutes, not seconds. `wiki-sync` exists for daily.
- **Mid-active-refactor.** Graph reflects a moving target; output goes stale faster than the researcher can act.
- **As substitute for reading code.** Deep layer is an index of structural relationships, not understanding.
- **Understand-Anything not installed.** Skill aborts; does not degrade to another tool.
- For new wiki entries → `wiki-log`. For audit → `wiki-lint`. For init → `wiki-init`.

## Inputs

- `--incremental` (default `true`) — re-use unchanged graph regions when `deep/last-scan.yaml` matches a recent commit. `--incremental=false` for full rescan.
- `--seed-wiki` (default `true`) — generate stub pages for newly prominent components lacking a wiki page. `--seed-wiki=false` for graph refresh without new stubs.
- `--scope <glob>` — restrict scan to a subpath. Default: full repo.
- `--dry-run` — report graph deltas, stubs to create, refs to add — without writing.

## Outputs

### `deep/knowledge-graph.json`

Overwritten each run. Full Understand-Anything output: `nodes`, `edges`, `layer_classification`, `symbols`, `call_graph`, `guided_tours`, plus metadata (`tool_version`, `git_ref`, `incremental`).

### `deep/last-scan.yaml`

Overwritten each run. Metadata used by subsequent `--incremental` runs: `scanned_at`, `git_ref`, `scope`, `tool_version`, `nodes`, `edges`, `scan_duration`.

### Wiki stub pages (when `--seed-wiki=true`)

For each graph node classified as a significant architectural component (per Understand-Anything's layer detection) with ≥`deepscan.stub_edge_threshold` (default 3) inbound edges, lacking a wiki page → create at `wiki/concepts/<slug>.md`:

- Frontmatter: `schema_version: 1`, `type: concept`, `tags: [auto-seeded]`, `refs.code` populated with verified bindings, `authored_by: llm`, `source_sessions: [<this-run-id>]`.
- Body: `## Structural facts (auto-generated)` (file path, public symbols, inbound callers, dependencies — observable graph data only) + `## Notes from researcher` (italicized "Add your interpretation here") + `## Open questions for researcher` (fixed template inviting researcher to fill in).

**No LLM-authored prose** about purpose, quality, or design. Only graph-extractable facts.

### Frontmatter ref updates on existing wiki pages

For existing pages whose concept maps to a graph node with newly verified links, append refs to frontmatter `refs.code` (frontmatter-only, body untouched — P3-permitted).

### Final report

Stdout summary + persistent `deep/deepscan-report-<date>.md`:
- Scan stats (nodes, edges, deltas vs last scan)
- Stubs created + existing pages with new refs + naming conflicts + graph-vs-frontmatter discrepancies
- Potential gaps (components below seed threshold)
- Suggested next step (highest-centrality stub by graph score, not LLM judgment)

## Behavior contract

- **External tool invocation.** *Only* skill that shells out to Understand-Anything. (`ARCHITECTURE.md §3.2` skill boundary.) Other skills read from `deep/` if needed but never invoke the tool.
- **Overwrites `deep/`.** By design — deep layer is regeneratable fact. (P1)
- **Never overwrites existing wiki page body (P3).** Stub creation is create-only. Existing pages may receive frontmatter ref additions; bodies untouched.
- **Stubs are structural scaffolding only (P8).** Bodies = file path + symbols + inbound callers + open-questions template. No prose about purpose / quality / design / "is for".
- **`authored_by: llm` on every stub.** Stricter than other skills. wiki-lint's later speculation check applies tighter thresholds to llm-authored pages.
- **Never invents purpose prose.** "This component is responsible for…" / "the intent appears to be…" are forbidden. Graph ambiguity → `confidence: dynamic` on the ref, not a prose guess.
- **Incremental mode reuses unchanged portions.** When `--incremental=true` + `deep/last-scan.yaml` metadata matches, reuse prior graph regions for files unchanged since last scan.
- **Naming conflicts flagged, not resolved.** Path collision with different `refs.code` → don't write; log to report + `wiki/questions.md`.
- **Graph-vs-frontmatter discrepancies → `wiki/discrepancies.md`.** Never auto-correct; flag and let researcher decide.

## Researcher interaction flow

1. Confirm scope and cost:
   ```
   wiki-deepscan: About to run Understand-Anything against the full repo.
     Scope: .
     Last scan: <date> (<N> days ago, incremental possible).
     Estimated duration: ~3–5 minutes.
     Will generate stubs for components with ≥<threshold> inbound edges.
   Proceed? [y/N]
   ```
2. On `y`: run external tool. Stream progress if supported.
3. Present final report.
4. Suggest single highest-centrality stub to fill in (ranked by graph centrality, **not** LLM judgment of importance).
5. Never open follow-up conversation ("shall I fill in the stub?"). Researcher invokes `wiki-log` separately when ready.

## Failure handling (essentials)

- Understand-Anything not installed → abort, install instructions; do **not** fall back to another tool.
- Scan timeout → retain partial output if available; preserve previous `deep/`; suggest `--scope` or `deepscan.ignore` config.
- Graph output malformed → abort, preserve previous `deep/`.
- Stub naming conflict → don't write; log to report + questions.md.
- Graph-vs-frontmatter discrepancy → `wiki/discrepancies.md`, not auto-corrected.
- Target repo not initialized → suggest `wiki-init`.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples (4): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions (incl. monorepo merge, version pinning, stub `seed_context` extension): `reference/open-questions.md`
- Consumed config keys + skill-output reads + writes: `reference/consumed-config.md`
