# `research-wiki.config.yaml` — Full Specification

> Authoritative reference for the user-tunable config that governs every ResearchWiki skill. Aggregated from each skill's `skills/<skill-name>/reference/consumed-config.md`.
>
> **Source of truth:** `wiki-init` writes the initial config from `skills/wiki-init/reference/bundle/research-wiki.config.yaml` (verbatim copy except `language.default`, which is set per the `--language` flag). All later edits are by the researcher; ResearchWiki skills only *read* this file.

---

## Document conventions

- A key in `monospace.namespace.form` denotes the YAML path.
- "Consumed by" lists the skills that read the key. (`wiki-init` does not appear in this column — it *writes* the initial file but does not read it at runtime.)
- "Default" is the value baked into the bundled reference config. Researchers may omit a key from the file; the consuming skill falls back to its built-in default (which matches the bundled default unless noted otherwise).
- "Reserved" rows describe keys that are documented but not yet consumed. They appear here so customizers know not to invent conflicting names; the consuming skill will gain support in a later version.

---

## `schema_version` *(top-level)*

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `schema_version` | int | `1` | every skill (loose check) |

The version of the config schema. Always `1` for now. Reserved for breaking changes; future migrations will read this to decide which fields to expect.

---

## `paths.*` — Filesystem layout

The wiki / index / deep / raw layer locations relative to the target repo root. Defaults match `ARCHITECTURE.md §2.2`. Override only if the layout demands non-standard names (rare).

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `paths.wiki` | path | `wiki/` | every skill |
| `paths.index` | path | `index/` | wiki-sync, wiki-lint, wiki-fix-stale, wiki-deepscan |
| `paths.deep` | path | `deep/` | wiki-deepscan, wiki-lint (orphan refinement) |
| `paths.raw` | path | `raw/` | wiki-sync (active experiment listing) |

---

## `language.*` — Language policy

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `language.default` | `ko \| en \| other` | `ko` | wiki-log (template selection), wiki-init |
| `language.follow_session` | bool | `true` | wiki-log (paraphrase prompts in session-dominant language) |

Note: `language.default` is set verbatim from the `--language` flag at `wiki-init` time. It is the only field wiki-init substitutes during the bundle copy.

---

## `log_templates.*` — wiki-log template selection

Each entry maps a `--type` value to a template slug under `templates/`. Default `default` resolves to the four shipped templates: `templates/experiment.md`, `templates/paper_reading.md`, `templates/design_decision.md`, `templates/free_form.md`.

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `log_templates.experiment` | str (template slug) | `default` | wiki-log |
| `log_templates.paper_reading` | str | `default` | wiki-log |
| `log_templates.design_decision` | str | `default` | wiki-log |
| `log_templates.free_form` | str | `default` | wiki-log |

Customize by writing a new template under `templates/` (e.g., `templates/my_lab_experiment.md`) and pointing the entry at it: `experiment: my_lab_experiment`. See `docs/TEMPLATES.md` for the file format.

---

## `log.*` — wiki-log behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `log.amend_window` | duration (e.g. `24h`) | `24h` | wiki-log |
| `log.suggest_concept_stubs` | bool | `true` | wiki-log |

`log.amend_window` controls how far back `wiki-log --amend` looks for a recent entry to modify. `log.suggest_concept_stubs` toggles the "create new concept stub for unmatched noun phrase" extension to the auto-link pass; when `false`, failed-match phrases are silently dropped.

---

## `lint.*` — wiki-lint behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `lint.strict_mode` | bool | `false` | wiki-lint |
| `lint.speculation_threshold` | float `[0.0, 1.0]` | `0.30` | wiki-lint (Check 5) |
| `lint.stale_age_days` | int | `7` | wiki-lint (Check 6) |
| `lint.stub_grace_period_days` | int | `30` | wiki-lint (Check 8) |
| `lint.report_path_default` | path template | `index/audits/lint_{timestamp}.md` | wiki-lint |
| `lint.severity_overrides` | map | `{}` *(reserved)* | wiki-lint *(future)* |

`strict_mode: true` escalates every finding to `error` severity and causes wiki-lint to exit non-zero. `--strict` on the command line has the same effect even when the config disables it.

`speculation_threshold` is the maximum allowed ratio of `[speculation]`-tagged sentences per page before Check 5 fires. `0.30` matches the threshold described in `ARCHITECTURE.md §2.5`.

`stub_grace_period_days` excludes `seeded_by:`-marked stubs from the orphan check (Check 8) for this many days after `created:` — the stub is *expected* to be orphan at creation time.

---

## `query.*` — wiki-query behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `query.backend` | `lexical \| hybrid` | `lexical` | wiki-query |
| `query.stale_warnings` | bool | `true` | wiki-query (`⚠ stale: …` badge) |
| `query.top_default` | int | `10` | wiki-query |
| `query.snippet_lines` | int | `2` *(reserved)* | wiki-query |
| `query.ko_tokenizer` | str | (unset) *(reserved)* | wiki-query *(v1.x)* |

`query.backend: hybrid` enables embedding-based semantic re-ranking on top of BM25. Reserved for v1.x — currently only `lexical` is implemented (see `wiki-query/reference/open-questions.md` §1).

---

## `recall.*` — wiki-recall behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `recall.lookback_default` | int (days) | `30` | wiki-recall |
| `recall.stale_since_default` | int (days) | `60` | wiki-recall |
| `recall.top_default` | int | `10` | wiki-recall |
| `recall.exclude_stubs` | bool | `true` | wiki-recall |
| `recall.ref_weights.code` | float | `2.0` | wiki-recall |
| `recall.ref_weights.concepts` | float | `1.5` | wiki-recall |
| `recall.ref_weights.papers` | float | `1.0` | wiki-recall |
| `recall.ref_weights.experiments` | float | `1.0` | wiki-recall |
| `recall.recency_decay` | str | (unset) *(reserved)* | wiki-recall *(v1.x)* |

`exclude_stubs: true` means pages with `seeded_by:` or (`authored_by: llm` + empty body) are excluded from the stale candidate set — their dense `refs.code` would otherwise dominate scoring without representing real interpretation.

---

## `sync.*` — wiki-sync behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `sync.scope_default` | `all \| code-only \| experiments-only` | `all` | wiki-sync |
| `sync.since_default` | `last-sync \| <ref>` | `last-sync` | wiki-sync |
| `sync.scanner.python` | `tree-sitter \| ctags` | `tree-sitter` | wiki-sync |
| `sync.scanner.typescript` | `tree-sitter` | `tree-sitter` | wiki-sync *(v0.2+)* |
| `sync.wiki_sync_ignore` | list of glob | `[]` | wiki-sync |
| `sync.scan_timeout` | int (seconds, per file) | `10` | wiki-sync |
| `sync.snapshot_depth_limit` | int | `4` | wiki-sync (file-tree section) |
| `sync.respect_gitignore` | bool | `true` | wiki-sync |
| `sync.snapshot_retention_days` | int | (unset) *(reserved)* | wiki-sync *(v1.x rolling-window cleanup)* |
| `sync.body_link_rot.enabled` | bool | `false` | wiki-sync |
| `sync.body_link_rot.token_regex` | regex | (built-in) *(reserved)* | wiki-sync *(v1.x override)* |
| `sync.nag_after_days` | int | `7` | wiki-sync |
| `sync.rename_heuristic.enabled` | bool | `true` | wiki-sync |
| `sync.rename_heuristic.similarity_threshold` | float `[0.0, 1.0]` | `0.80` | wiki-sync |
| `sync.rename_heuristic.line_window` | int | `10` | wiki-sync |

`body_link_rot.enabled: true` makes the body link rot scan run on every sync. Without it, the scan only runs when `--scan-body` is on the command line. The pass produces `body_stale_mentions:` frontmatter entries; downstream consumers (notably `wiki-fix-stale`) treat them as `[unverified]`.

`nag_after_days` triggers an end-of-run reminder when there are pages with `stale: true` flags older than this. `--no-nag` suppresses. Set to `0` to disable nagging entirely.

`rename_heuristic.*` controls the "Possible renames" section of each snapshot. When enabled, wiki-sync scans removed × added symbol pairs in the same file and compares signatures with `difflib.SequenceMatcher`; pairs above the threshold and within the line window are listed as candidates with `[unverified]` tag. The researcher decides whether the rename is real.

---

## `deepscan.*` — wiki-deepscan behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `deepscan.tool` | `understand-anything \| none` | `understand-anything` | wiki-deepscan |
| `deepscan.tool_path` | path | (auto-detect via `$PATH`) | wiki-deepscan |
| `deepscan.tool_version_pin` | str (e.g. `0.4.2`) | (none) | wiki-deepscan |
| `deepscan.strict_version_pin` | bool | `false` | wiki-deepscan |
| `deepscan.timeout` | int (seconds) | `600` | wiki-deepscan |
| `deepscan.incremental_default` | bool | `true` | wiki-deepscan |
| `deepscan.seed_wiki_default` | bool | `true` | wiki-deepscan |
| `deepscan.stub_edge_threshold` | int | `3` | wiki-deepscan |
| `deepscan.ignore` | list of glob | `[]` | wiki-deepscan |
| `deepscan.cadence_hint` | str | `weekly` | wiki-deepscan (informational) |
| `deepscan.seed_with_seed_context` | bool | (unset) *(reserved)* | wiki-deepscan *(v1.x)* |
| `deepscan.tour_seeding` | bool | (unset) *(reserved)* | wiki-deepscan *(v1.x)* |

`tool: none` disables wiki-deepscan entirely (treats invocation as no-op). Useful when the researcher does not want to install Understand-Anything; daily code-fact needs are still served by `wiki-sync`.

`stub_edge_threshold` filters which graph nodes get seeded as wiki stubs — only nodes classified as architecturally significant *and* with at least this many inbound edges qualify.

---

## `fix_stale.*` — wiki-fix-stale behavior

| Key | Type | Default | Consumed by |
|---|---|---|---|
| `fix_stale.auto_clear_flags` | bool | `true` | wiki-fix-stale |
| `fix_stale.include_body_mentions` | `auto \| true \| false` | `auto` | wiki-fix-stale |
| `fix_stale.oldest_first` | bool | `true` | wiki-fix-stale |
| `fix_stale.deprecated_tag_format` | str | `[deprecated YYYY-MM-DD]` | wiki-fix-stale |
| `fix_stale.apply_to_all.threshold` | int | (unset) *(reserved)* | wiki-fix-stale *(v1.x bulk option)* |

`include_body_mentions: auto` walks `body_stale_mentions:` entries when present in frontmatter; skips them when absent (no error).

---

## Minimal valid config

```yaml
# research-wiki.config.yaml — minimal
schema_version: 1
language:
  default: ko
paths:
  wiki: wiki/
  index: index/
  deep: deep/
  raw: raw/
deepscan:
  tool: understand-anything
lint:
  strict_mode: false
```

Every other key falls back to its built-in default.

---

## Full config (every documented key, defaults shown)

```yaml
schema_version: 1

language:
  default: ko
  follow_session: true

paths:
  wiki: wiki/
  index: index/
  deep: deep/
  raw: raw/

log_templates:
  experiment: default
  paper_reading: default
  design_decision: default
  free_form: default

log:
  amend_window: 24h
  suggest_concept_stubs: true

lint:
  strict_mode: false
  speculation_threshold: 0.30
  stale_age_days: 7
  stub_grace_period_days: 30
  report_path_default: index/audits/lint_{timestamp}.md

query:
  backend: lexical
  stale_warnings: true
  top_default: 10

recall:
  lookback_default: 30
  stale_since_default: 60
  top_default: 10
  exclude_stubs: true
  ref_weights:
    code: 2.0
    concepts: 1.5
    papers: 1.0
    experiments: 1.0

sync:
  scope_default: all
  since_default: last-sync
  scanner:
    python: tree-sitter
    typescript: tree-sitter
  wiki_sync_ignore: []
  scan_timeout: 10
  snapshot_depth_limit: 4
  respect_gitignore: true
  body_link_rot:
    enabled: false
  nag_after_days: 7
  rename_heuristic:
    enabled: true
    similarity_threshold: 0.80
    line_window: 10

deepscan:
  tool: understand-anything
  tool_path: null
  tool_version_pin: null
  strict_version_pin: false
  timeout: 600
  incremental_default: true
  seed_wiki_default: true
  stub_edge_threshold: 3
  ignore: []
  cadence_hint: weekly

fix_stale:
  auto_clear_flags: true
  include_body_mentions: auto
  oldest_first: true
  deprecated_tag_format: "[deprecated YYYY-MM-DD]"
```

---

## Common patterns

### Tighter speculation budget (pre-paper-write hygiene)

```yaml
lint:
  strict_mode: true
  speculation_threshold: 0.10   # 10% — much tighter
  stale_age_days: 3             # nag earlier
```

Pair with a CI hook that runs `wiki-lint --strict` on the documentation branch before merging.

### Always scan body for stale mentions

```yaml
sync:
  body_link_rot:
    enabled: true               # opt-in heuristic, by default
```

Pair with regular `wiki-fix-stale` runs to clean up the surfaced mentions.

### Solo researcher, no Understand-Anything

```yaml
deepscan:
  tool: none                    # disable; deep/ stays empty
```

`wiki-deepscan` becomes a no-op; `wiki-lint`'s Check 8 (orphan refinement) falls back to the inbound-link heuristic without graph data.

### Multi-package monorepo with ignore patterns

```yaml
sync:
  wiki_sync_ignore:
    - "src/bindings/_generated.cpp"
    - "vendor/**"
deepscan:
  ignore:
    - "src/bindings/**"
    - "vendor/**"
  stub_edge_threshold: 5        # raise to limit noise in a large repo
```

---

## Where each skill reads from

To trace a specific config key back to its consumer, see each skill's per-skill reference:

- `skills/wiki-init/reference/consumed-config.md` — *initial-config writer*, not a reader
- `skills/wiki-log/reference/consumed-config.md`
- `skills/wiki-sync/reference/consumed-config.md`
- `skills/wiki-deepscan/reference/consumed-config.md`
- `skills/wiki-lint/reference/consumed-config.md`
- `skills/wiki-query/reference/consumed-config.md`
- `skills/wiki-recall/reference/consumed-config.md`
- `skills/wiki-fix-stale/reference/consumed-config.md`

When this file disagrees with one of those, the per-skill file wins for that skill — but report the inconsistency so this aggregate can be corrected.
