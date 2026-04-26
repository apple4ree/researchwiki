# `wiki-recall` — Consumed Config Keys

> Supplementary material for `wiki-recall`. Lists `research-wiki.config.yaml` keys this skill reads. Full schema in `docs/CONFIG.md` (TBD).

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to scan pages and `log.md` |

## Read by `recall:` section

| Key | Default | Used for |
|---|---|---|
| `recall.lookback_default` | `30` | Default for `--lookback <days>` |
| `recall.stale_since_default` | `60` | Default for `--stale-since <days>` |
| `recall.top_default` | `10` | Default for `--top N` |
| `recall.exclude_stubs` | `true` | Whether to exclude `seeded_by:`/`authored_by: llm` empty stubs by default |
| `recall.ref_weights.code` | `2.0` | Score weight for shared `refs.code` |
| `recall.ref_weights.concepts` | `1.5` | Score weight for shared `refs.concepts` |
| `recall.ref_weights.papers` | `1.0` | Score weight for shared `refs.papers` |
| `recall.ref_weights.experiments` | `1.0` | Score weight for shared `refs.experiments` |

## Reserved (declared, not yet used)

- `recall.recency_decay` — reserved for v1.x linear-decay weighting within the lookback window (see `open-questions.md` §3).

---

## Not consumed

wiki-recall does **not** read:
- `lint.*`, `query.*`, `sync.*`, `deepscan.*`, `log_templates.*`, `fix_stale.*`
- `paths.{index,deep,raw}` (frontmatter-only; doesn't touch index/deep/raw layers)

Adding new config keys for wiki-recall: extend the table above and document the rationale in `wiki-recall/SPEC.md`.
