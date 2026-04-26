# `wiki-deepscan` — Open Questions

> Supplementary material for `wiki-deepscan`. Not loaded at LLM runtime.

---

## 1. Very large monorepo scans

**Status:** designed but not stress-tested.

For repos large enough that a full Understand-Anything scan exceeds reasonable timeouts (~10–30 min), `--scope <glob>` allows narrowing.

**Proposed:** scope flag + per-package scans merged into a single `deep/knowledge-graph.json`. Merging logic is non-trivial — node IDs must be globally unique across scope partitions; cross-package edges must reconcile.

**Decision needed before** any large monorepo deployment: implement merge or accept that very large repos require partial deep layers.

---

## 2. Stubs as drafts vs immediate write

**Status:** decided — immediate write.

Idea: write new stubs to `wiki/draft_concepts/` until the researcher "promotes" them, instead of directly to `wiki/concepts/`.

**Rejected:** the `authored_by: llm` marker + empty body + open-questions section already make stubs visually distinct. Adding a draft directory adds workflow friction without clear benefit.

**Compromise (accepted):** stubs carry `tags: [auto-seeded]` so the researcher can filter wiki-query results to find unfilled stubs.

---

## 3. Understand-Anything version pinning

**Status:** designed.

Different versions of Understand-Anything may produce slightly different graphs (improved heuristics, new node classifications). For reproducibility, the researcher may want to pin a specific version.

**Proposed:** `deepscan.tool_version_pin: "0.4.2"` in config. wiki-deepscan checks the installed version against the pin and warns or aborts on mismatch (depending on `deepscan.strict_version_pin: bool`).

**Decision needed before:** first multi-machine deployment where reproducibility matters. For solo use, version drift is rarely an issue.

---

## 4. Stub edge threshold

**Status:** decided default, configurable.

`deepscan.stub_edge_threshold: 3` — components with ≥3 inbound edges that lack a wiki page get seeded as stubs. Below threshold, listed in "Potential gaps" but not auto-seeded.

**Open:** is 3 the right default? For very small repos, might be too high (no components qualify). For very large ones, might be too low (too many stubs). Researcher feedback will calibrate.

---

## 5. Stubs created from `seed_context` like `wiki-log`'s

**Status:** consider for v1.x.

Currently wiki-deepscan stubs carry `tags: [auto-seeded]` and `authored_by: llm` but not the `seeded_by:` + `seed_context:` schema that `wiki-log` introduced for its concept stubs.

**Proposed:** add `seeded_by: wiki-deepscan` and `seed_context: { from_node_id, centrality_score, scan_timestamp }` for symmetry with `wiki-log` stubs. Lets `wiki-lint`'s Check #8 (orphan grace) handle both stub types uniformly.

**Decision needed before:** wiki-lint Check #8 refinement (currently a known follow-up).

---

## 6. Guided tour authoring

**Status:** out of scope for MVP.

Understand-Anything's output includes "guided tours" — narrative paths through the codebase. wiki-deepscan currently dumps these into `deep/knowledge-graph.json` but does not surface them as wiki pages.

**Open:** should there be a `--seed-tours` flag that creates wiki pages from guided tours?

**Rejected for MVP:** tours are by their nature interpretive (the tool decides "this is the path you should walk"), and writing them as wiki pages would inject LLM-generated prose into the wiki — a P8 concern. If the researcher wants a tour, they read it from the JSON.
