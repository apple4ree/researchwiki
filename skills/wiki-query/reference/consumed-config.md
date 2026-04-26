# `wiki-query` — Consumed Config Keys

> Supplementary material for `wiki-query`. Lists the `research-wiki.config.yaml` keys this skill reads. Full schema definitions live in `docs/CONFIG.md` (TBD); this file is a per-skill index.

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to look for pages |
| `paths.index` | `index/` | Used to know what to exclude under `index/audits/*` |

## Read by `query:` section

| Key | Default | Used for |
|---|---|---|
| `query.backend` | `lexical` | Scoring backend (`lexical` MVP; `hybrid` reserved for v2) |
| `query.stale_warnings` | `true` | Whether to prefix stale-flagged results with `⚠ stale: …` badge |
| `query.ko_tokenizer` | (unset) | Reserved — Korean morphological adapter for v2 |
| `query.top_default` | `10` | Default for `--top` when not specified |

## Reserved (declared, not yet used)

- `query.snippet_lines` — reserved for tuning the ±N lines around a match (default 2). Not yet exposed as a flag.

---

## Not consumed

wiki-query does **not** read:
- `lint.*` (only `wiki-lint` consumes)
- `recall.*` (only `wiki-recall`)
- `sync.*` or `deepscan.*`
- `log_templates.*`

Adding new config keys for wiki-query: extend the table above and document the rationale in `wiki-query/SPEC.md`.
