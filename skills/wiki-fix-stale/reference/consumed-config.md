# `wiki-fix-stale` — Consumed Config Keys

> Supplementary material for `wiki-fix-stale`. Lists `research-wiki.config.yaml` keys this skill reads. Full schema in `docs/CONFIG.md` (TBD).

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where to scan for stale-flagged pages |
| `paths.index` | `index/` | Read for `signatures.json` lookup when verifying false-positive cases |

## Read by `fix_stale:` section

| Key | Default | Used for |
|---|---|---|
| `fix_stale.auto_clear_flags` | `true` | After all stale refs in a page are addressed (no skips), auto-remove `stale: true` and `stale_detected:` from frontmatter |
| `fix_stale.include_body_mentions` | `auto` | Walk through `body_stale_mentions` entries from wiki-sync's body link rot scan. `auto` = include if field present, skip if absent |
| `fix_stale.oldest_first` | `true` | Process pages in order of oldest `stale_detected:` date |
| `fix_stale.deprecated_tag_format` | `[deprecated YYYY-MM-DD]` | Format string for the wrap-deprecated edit option |

## Reserved (declared, not yet used)

- `fix_stale.apply_to_all.threshold` — for the not-yet-shipped `--apply-to-all` per-page bulk option (see `open-questions.md` §1). Reserved.

---

## Reads from other skills' outputs (not config, but worth noting)

wiki-fix-stale **consumes**:
- Frontmatter `stale: true`, `stale_detected:` written by `wiki-sync`
- Frontmatter `body_stale_mentions:` written by `wiki-sync` (when `--scan-body` was on)
- Optional: snapshot rename hints from the most recent `index/snapshots/sync_*.md` (for the "possible rename" note alongside the replace-symbol option)

---

## Writes to

- Wiki page bodies (per-edit researcher-approved)
- Wiki page frontmatter (clearance of `stale: true` / `stale_detected:` / `body_stale_mentions:` when fully resolved)
- `wiki/log.md` (append-only session record)

---

## Not consumed

- `lint.*`, `query.*`, `recall.*`, `deepscan.*`, `log_templates.*`, `log.*`
- `paths.{deep,raw}`

Adding new config keys for wiki-fix-stale: extend the table above and document the rationale in `wiki-fix-stale/SPEC.md`.
