# `wiki-log` — Consumed Config Keys

> Supplementary material for `wiki-log`. Lists the `research-wiki.config.yaml` keys this skill reads. Full schema definitions live in `docs/CONFIG.md` (TBD); this file is a per-skill index.

---

## Read at every invocation

| Key | Default | Meaning |
|---|---|---|
| `paths.wiki` | `wiki/` | Where new entries are written (subdivided by type) |
| `paths.index` | `index/` | Where `signatures.json` is read for code auto-link |
| `language.default` | `ko` | Selects which language's templates were installed at `wiki-init` time |

## Read by `log_templates:` section

| Key | Default | Used for |
|---|---|---|
| `log_templates.experiment` | `experiment` | Template slug for `--type experiment` |
| `log_templates.paper_reading` | `paper_reading` | Template slug for `--type paper` |
| `log_templates.design_decision` | `design_decision` | Template slug for `--type decision` |
| `log_templates.free_form` | `free_form` | Template slug for `--type free` (also fallback when a configured template is missing) |

A custom template slug (e.g., `experiment: my_custom`) points to `templates/my_custom.md`. The slug must resolve to an existing file under `templates/`.

## Read by `log:` section

| Key | Default | Used for |
|---|---|---|
| `log.amend_window` | `24h` | Time window for `--amend` to find a recent entry to modify |
| `log.suggest_concept_stubs` | `true` | Whether failed concept-slug matches are routed to the stub-suggestion batch |

## Read by per-template `_template:` block (not config but worth noting)

Each template file (`templates/<type>.md`) carries a `_template:` block consumed by wiki-log:

```yaml
_template:
  auto_link:
    code:
      enabled: true
      strategy: identifier_token
      default_confidence: verified
      link_bidirectional: false
    experiments:
      enabled: true
      strategy: exact_id
      link_bidirectional: true
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    papers:
      enabled: false
```

Each `_template.auto_link.<kind>` controls one auto-link scan. `link_bidirectional: true` means the target page's frontmatter gets a back-ref entry on approval.

---

## Not consumed

wiki-log does **not** read:
- `lint.*`, `query.*`, `recall.*`, `sync.*`, `deepscan.*`, `fix_stale.*`
- `paths.deep`, `paths.raw`

Adding new config keys for wiki-log: extend the table above and document the rationale in `wiki-log/SPEC.md`.
