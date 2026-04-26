# `wiki-sync` — Consumed Config Keys

> Supplementary material for `wiki-sync`. Lists `research-wiki.config.yaml` keys this skill reads. Full schema in `docs/CONFIG.md` (TBD).

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to scan frontmatter for stale-link pass and reverse-refs build |
| `paths.index` | `index/` | Where to write snapshots, `signatures.json`, `reverse_refs.json` |
| `paths.deep` | `deep/` | (Read-only) check `last-scan.yaml` for `--since` resolution if no snapshot exists |
| `paths.raw` | `raw/` | Where to look for active experiment directories (listed in snapshot) |

## Read by `sync:` section

| Key | Default | Used for |
|---|---|---|
| `sync.scope_default` | `all` | Default for `--scope` |
| `sync.since_default` | `last-sync` | Default for `--since` resolution strategy |
| `sync.scanner.python` | `tree-sitter` | Python scanner backend (`tree-sitter` \| `ctags`) |
| `sync.scanner.typescript` | `tree-sitter` | TypeScript/JavaScript scanner backend |
| `sync.wiki_sync_ignore` | `[]` | Glob patterns to skip during scan (union with `.gitignore`) |
| `sync.scan_timeout` | `10` (seconds) | Per-file scanner timeout |
| `sync.snapshot_depth_limit` | `4` | File-tree depth in snapshot's `## File tree` section |
| `sync.body_link_rot.enabled` | `false` | Default for `--scan-body` (opt-in heuristic body scan) |
| `sync.body_link_rot.token_regex` | (built-in MVP regex) | Override identifier-shape regex (reserved for v1.1) |
| `sync.nag_after_days` | `7` | Surface end-of-run nag for stale flags older than this |
| `sync.respect_gitignore` | `true` | Whether to honor `.gitignore` (almost always yes) |

## Reserved (declared, not yet used)

- `sync.snapshot_retention_days` — reserved for rolling-window snapshot cleanup (see `open-questions.md` §6).

---

## Writes to

- `index/signatures.json` — overwritten each run.
- `index/reverse_refs.json` — overwritten each run.
- `index/snapshots/sync_YYYYMMDD_HHMM.md` — new immutable snapshot per run.
- Frontmatter `stale: true` / `stale_detected:` on wiki pages with stale `refs.code` (P3-permitted edit on existing pages).
- Frontmatter `body_stale_mentions:` on wiki pages with body prose mentioning removed symbols (only when `--scan-body` is on).
- `wiki/questions.md` (append) — one entry per stale ref detected.

---

## Reads from / interacts with other skills' outputs

- `index/snapshots/sync_*.md` (own previous output) — last snapshot's filename used for `--since` default.
- `deep/last-scan.yaml` (from `wiki-deepscan`) — read as `--since` fallback if no `index/snapshots/` exist yet.
- Frontmatter `refs.code` (set by `wiki-log`, `wiki-deepscan`) — input to stale-link pass and reverse-refs build.

---

## Not consumed

- `lint.*`, `query.*`, `recall.*`, `log_templates.*`, `log.*`, `fix_stale.*`, `deepscan.*`

Adding new config keys for wiki-sync: extend the table above and document the rationale in `wiki-sync/SPEC.md`.
