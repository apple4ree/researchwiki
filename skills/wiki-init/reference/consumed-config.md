# `wiki-init` — Config Handling

> Supplementary material for `wiki-init`. Not loaded at LLM runtime. Unlike other skills, wiki-init **writes the initial config** rather than reading from one — so this file lists what wiki-init *seeds* into `research-wiki.config.yaml` and how `--language`, `--mode`, `--deepscan-tool`, `--seed-from` flags shape that initial seed.

---

## What wiki-init reads

**Nothing from `research-wiki.config.yaml`.** The config does not exist at the start of an init run — wiki-init creates it. There is therefore nothing to read.

If `research-wiki.config.yaml` already exists, wiki-init treats the workspace as already-initialized and refuses to proceed (see `SPEC.md` "When NOT to invoke" and Example 3 in `reference/examples.md`).

## What wiki-init writes

The initial `research-wiki.config.yaml` is a verbatim byte-for-byte copy of `reference/bundle/research-wiki.config.yaml` (the reference shipped with the skill set), with **one narrow substitution**: `language.default` is set per the `--language` flag.

The reference config follows the minimum schema in `ARCHITECTURE.md §2.4` and carries an inline comment on each field. Researchers customize after init by editing the file directly.

## How flags map to initial config

| Flag | Default | Initial-config effect |
|---|---|---|
| `--language` | `ko` | Sets `language.default`. The only post-copy substitution wiki-init performs. |
| `--mode` | prompt | Recorded in the first log entry; **not** written to config. |
| `--deepscan-tool` | `understand-anything` | Sets `deepscan.tool` — but the bundled reference config already carries this default; wiki-init only edits if the flag value differs. |
| `--seed-from` | (none) | Recorded in the first log entry as `seed-from: <path>`; **not** written to config. |

## What goes into `wiki/log.md` (first entry)

Per `SKILL.md` "First log entry":

```
## [YYYY-MM-DD] init | ResearchWiki initialized

- mode: new | adopt
- language: ko | en
- deepscan-tool: understand-anything | none
- seed-from: <path or "(none)">
```

This is fact-only — no interpretation, no summary of the repo contents. It records the init event itself for provenance (which P7 mandates).

## Reference bundle layout (what gets copied to target)

```
skills/wiki-init/reference/bundle/
├── CLAUDE.md                       → target/CLAUDE.md (verbatim)
├── research-wiki.config.yaml       → target/research-wiki.config.yaml (verbatim except language.default)
└── templates/
    ├── en/
    │   ├── experiment.md
    │   ├── paper_reading.md
    │   ├── design_decision.md
    │   └── free_form.md
    └── ko/
        ├── experiment.md
        ├── paper_reading.md
        ├── design_decision.md
        └── free_form.md
```

At init time, the four templates from the language matching `--language` are flattened into `target/templates/*.md` (without the language subdirectory).

## Design rationale: why "verbatim copy + one exception" instead of "generate from spec"

This approach was chosen over inline generation in the 2026-04-25 design batch (see `ARCHITECTURE.md` Appendix B). Rejected alternatives:

- **(B) Inline generation of `CLAUDE.md` and config from `ARCHITECTURE.md §2.4`:** regenerated prose drifts subtly each invocation, breaking the byte-stability `wiki-sync` and `wiki-log` rely on when reading `CLAUDE.md`.
- **(C) Hybrid (copy CLAUDE.md, generate config):** extra cognitive load with no compensating benefit.

The verbatim-copy contract is what makes the rest of the skill set able to assume specific file structure without re-validating on every run.
