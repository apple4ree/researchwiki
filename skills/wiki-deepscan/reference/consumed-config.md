# `wiki-deepscan` — Consumed Config Keys

> Supplementary material for `wiki-deepscan`. Lists `research-wiki.config.yaml` keys this skill reads. Full schema in `docs/CONFIG.md` (TBD).

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to scan for existing pages and create stubs |
| `paths.deep` | `deep/` | Where to write `knowledge-graph.json`, `last-scan.yaml`, and the run report |
| `paths.index` | `index/` | (Optional) read for cross-checking with `wiki-sync`'s stale-flag state to dedup notes |

## Read by `deepscan:` section

| Key | Default | Used for |
|---|---|---|
| `deepscan.tool` | `understand-anything` | Which external tool to invoke (`none` = skip; equivalent to refusing to run) |
| `deepscan.tool_path` | (auto-detect on $PATH) | Override path to the tool binary |
| `deepscan.tool_version_pin` | (none) | Pin a specific Understand-Anything version (warn or abort on mismatch) |
| `deepscan.strict_version_pin` | `false` | If true, version mismatch → abort; if false, warn and proceed |
| `deepscan.timeout` | `600` (seconds) | Tool subprocess timeout |
| `deepscan.incremental_default` | `true` | Default for `--incremental` flag |
| `deepscan.seed_wiki_default` | `true` | Default for `--seed-wiki` flag |
| `deepscan.stub_edge_threshold` | `3` | Minimum inbound edge count to qualify a graph node for stub seeding |
| `deepscan.ignore` | `[]` | Glob patterns of files/directories to exclude from scanning (e.g., `["src/bindings/_generated.cpp"]`) |

## Reserved (declared, not yet used)

- `deepscan.seed_with_seed_context` — for the v1.x extension that adds `seeded_by: wiki-deepscan` + `seed_context:` to stubs (see `open-questions.md` §5).
- `deepscan.tour_seeding` — reserved if guided tour seeding is ever added (see `open-questions.md` §6).

---

## Writes to

- `deep/knowledge-graph.json` — overwritten each run.
- `deep/last-scan.yaml` — overwritten each run; consumed by next run's `--incremental` mode.
- `deep/deepscan-report-<date>.md` — per-run report (immutable history).
- New stub pages in `wiki/concepts/` (create-only, with `authored_by: llm` + `tags: [auto-seeded]`).
- Frontmatter `refs.code` additions on existing wiki pages (the only edit wiki-deepscan makes to existing pages — never touches body).
- `wiki/discrepancies.md` (append) — graph vs frontmatter conflicts.
- `wiki/questions.md` (append) — naming conflicts (deduplicated against existing wiki-sync notes).

---

## Reads from / interacts with other skills' outputs

- `index/snapshots/sync_*.md` — read for cross-checking the rename-vs-delete heuristic against wiki-sync's snapshot.
- Frontmatter `stale: true` (set by `wiki-sync`) — used to dedup conflict notes.
- Existing wiki pages' `refs.code` — used to detect "graph vs frontmatter" discrepancies.

---

## Not consumed

- `lint.*`, `query.*`, `recall.*`, `log_templates.*`, `log.*`, `fix_stale.*`, `sync.*`
- `paths.raw`

Adding new config keys for wiki-deepscan: extend the table above and document the rationale in `wiki-deepscan/SPEC.md`.
