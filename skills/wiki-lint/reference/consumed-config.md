# `wiki-lint` — Consumed Config Keys

> Supplementary material for `wiki-lint`. Lists `research-wiki.config.yaml` keys this skill reads. Full schema in `docs/CONFIG.md` (TBD).

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to scan pages |
| `paths.index` | `index/` | Where to write `audits/lint_*.md` and read `signatures.json` for Check 4 / Check 6 |
| `paths.deep` | `deep/` | Read `knowledge-graph.json` if present (refines Check 8 — orphan detection) |

## Read by `lint:` section

| Key | Default | Used for |
|---|---|---|
| `lint.strict_mode` | `false` | Escalate every finding to `error` severity (overridable per-invocation by `--strict`) |
| `lint.speculation_threshold` | `0.30` | Density above which Check 5 fires |
| `lint.stale_age_days` | `7` | Age above which Check 6 reports an unaddressed stale ref |
| `lint.stub_grace_period_days` | `30` (reserved) | Orphan check grace period for `seeded_by:` stubs (see `open-questions.md` §6) |
| `lint.report_path_default` | `index/audits/lint_{timestamp}.md` | Default audit report destination (overridable by `--report-path`) |

## Reserved (declared, not yet used)

- `lint.severity_overrides:` — reserved per-check severity overrides (see `open-questions.md` §2).

---

## Writes to

- `index/audits/lint_YYYYMMDD_HHMM.md` — new immutable audit report each run.
- `wiki/questions.md` — append-only entries for findings requiring researcher decision.
- `wiki/discrepancies.md` — append-only entries for cross-page contradiction findings (Check 7).

---

## Reads from other skills' outputs

wiki-lint **consumes** (does not write):
- Frontmatter `stale: true`, `stale_detected:` (set by `wiki-sync`) — drives Check 6.
- Frontmatter `body_stale_mentions:` (set by `wiki-sync --scan-body`) — does not drive any current check; reserved for future "persistent body-mention" extension.
- Frontmatter `seeded_by:` (set by `wiki-log` and `wiki-deepscan`) — reserved for stub-grace refinement of Check 8.
- `index/signatures.json` (written by `wiki-sync`) — drives Check 4 (refs.code.path file existence; cross-references the snapshot).
- `index/snapshots/sync_*.md` (written by `wiki-sync`) — referenced in audit report header for traceability.
- `deep/knowledge-graph.json` (written by `wiki-deepscan`, optional) — refines Check 8 (a wiki page is `info · orphan` only if also unreferenced by the deep graph, when graph is available).

---

## Not consumed

- `query.*`, `recall.*`, `log_templates.*`, `log.*`, `fix_stale.*`, `deepscan.*`
- `paths.raw`

Adding new config keys for wiki-lint: extend the table above and document the rationale in `wiki-lint/SPEC.md`.
