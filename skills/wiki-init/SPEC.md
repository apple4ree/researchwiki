# Skill Spec: `wiki-init`

> **Frequency:** Once per project (idempotent — re-running must not destroy existing content)
> **Tier:** Initialization
> **Writes to:** Everything (seeds the repo)

## Purpose

Bootstrap a repository into a ResearchWiki-enabled workspace. Create the directory structure, the config file, the constitution, default templates, and seed pages so the rest of the skill set can run.

## When to invoke

- First-time setup of a new research repository.
- Adopting ResearchWiki for an existing repository with code/notes but no wiki structure.

## When NOT to invoke

- Repository already has both `CLAUDE.md` and `research-wiki.config.yaml` → researcher should edit, not re-init.
- Repository is not a research workspace (e.g., a library being developed for external users).

## Inputs

| Flag | Default | Effect |
|---|---|---|
| `--mode` | prompt | `new` (clean repo) \| `adopt` (preserve existing content) |
| `--language` | `ko` | Selects language of bundled templates; sets `language.default` in initial config |
| `--deepscan-tool` | `understand-anything` | Sets `deepscan.tool` in initial config (`none` to disable) |
| `--seed-from` | (none) | Optional path to existing notes; recorded in first log entry only (not imported) |

If invoked without flags, prompt the researcher interactively. wiki-init does not consume `research-wiki.config.yaml` (it does not exist yet at init time); it produces it. See `reference/consumed-config.md` for the flag → initial-config mapping.

## Outputs

- **Directories:** `wiki/{concepts,papers,experiments,decisions}/`, `index/{snapshots,audits}/`, `deep/`, `raw/{papers,experiments}/`, `templates/`
- **Files (verbatim copies from `reference/bundle/`):** `CLAUDE.md`, `research-wiki.config.yaml`, four templates flattened into `templates/`
- **Files (generated minimal):** `wiki/{index,log,questions,discrepancies}.md`
- **`.gitignore`** appended with `deep/knowledge-graph.json`

The first `wiki/log.md` entry records the init event itself (fact-only). No code scan, no deep analysis — those are `wiki-sync` and `wiki-deepscan`'s responsibilities.

## Behavior contract

- **Idempotency.** Existing target files are never overwritten. Conflict → skip + report. `adopt` mode merges by creating only missing items.
- **Verbatim copy + one exception.** Bundle assets are copied byte-for-byte. The single exception is `language.default` in the config, substituted per `--language`. Every other field, every other file is byte-stable. (Bundle integrity)
- **No analysis (P8).** wiki-init does not read existing code, papers, or notes to seed interpretation. Seed pages contain only structural scaffolding.
- **No interpretive content in seed pages (P3, P8).** No summaries, no inferences, no project guesses.
- **Authored_by tagging (P7).** Every generated page gets `authored_by: llm` and `schema_version: 1`.
- **Confirmation required.** Show proposed layout; wait for `y` before writing.
- **Reference asset missing → abort.** Do not fall back to generating from memory. (See `reference/failure-modes.md`.)

## Researcher interaction

1. Show proposed directory layout and file list (including any skipped due to conflicts).
2. Ask for confirmation.
3. After creation, show a "next steps" summary: `wiki-sync` (first index), optional `wiki-deepscan`, then `wiki-log` for entries.

## Reference

- Worked examples (5): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Config handling + reference bundle layout: `reference/consumed-config.md`
- **Bundle assets (the runtime files copied to target repo):** `reference/bundle/`
