# `wiki-init` — Worked Examples

> Supplementary material for `wiki-init`. Not loaded at LLM runtime — read for orientation, design discussion, or when debugging unexpected init behavior.

---

## Example 1 — Happy path: new project

Researcher clones a fresh research repo and wants the wiki.

```
> wiki-init --mode new --language ko --deepscan-tool understand-anything

[ResearchWiki] Proposed layout under /home/researcher/project/:

  CLAUDE.md
  research-wiki.config.yaml
  wiki/{concepts,papers,experiments,decisions}/
  wiki/{index,log,questions,discrepancies}.md
  index/snapshots/
  index/audits/
  deep/
  raw/{papers,experiments}/
  templates/{experiment,paper_reading,design_decision,free_form}.md
  .gitignore (append entry for deep/knowledge-graph.json)

Confirm? [y/N] y

✓ Created 14 files, 9 directories.
✓ First log entry appended to wiki/log.md.

Next steps:
  1. `wiki-sync` — generate the first Index Layer snapshot.
  2. (Optional) `wiki-deepscan` — refresh the Deep Analysis Layer.
     Understand-Anything must be installed separately; see its README.
  3. `wiki-log` — record experiments, paper readings, decisions, notes.
```

---

## Example 2 — Ambiguity: flag missing

Researcher invokes without specifying mode. The repo already has code and loose notes.

```
> wiki-init --language en --deepscan-tool understand-anything

[ResearchWiki] I need one piece of info before proceeding.

  The target directory already contains:
    - src/            (code, 47 files)
    - notes.md        (top-level unstructured notes)

  Treat this as a `new` project (preserve existing files, wrap the wiki
  directory structure around them) or `adopt` it (same, but also record
  `notes.md` under `--seed-from` in the first log entry)?

> adopt

[ResearchWiki] Proposed layout:
  (as above, minus anything that already exists)

Confirm? [y/N] y
```

---

## Example 3 — Refusal: already initialized

Researcher invokes against a repo that already has a wiki.

```
> wiki-init --mode new

[ResearchWiki] This repository is already a ResearchWiki workspace:
  - CLAUDE.md (present)
  - research-wiki.config.yaml (present)
  - wiki/ (present, 12 pages)

Running `wiki-init` on an initialized repo risks overwriting the
constitution. I will not proceed.

If you want to change a configuration value, edit
`research-wiki.config.yaml` directly.
If you want to reset the wiki, that is a manual, destructive decision.
Delete the files yourself first, then re-invoke.
```

---

## Example 4 — Recovery: interrupted mid-run

A previous run was interrupted after creating `wiki/` but before writing `templates/`.

```
> wiki-init --mode new --language ko --deepscan-tool understand-anything

[ResearchWiki] Partial ResearchWiki workspace detected:
  Existing:  CLAUDE.md, research-wiki.config.yaml, wiki/ (5 files)
  Missing:   templates/, index/, deep/, raw/, wiki/log.md

Proposed: create only the missing items. Existing files untouched.

Confirm? [y/N] y

✓ Created 8 files, 4 directories.
✓ Skipped 7 pre-existing files.
✓ A new entry was appended to wiki/log.md recording this partial init.
```

---

## Example 5 — Reference asset missing (skill-set packaging bug)

Hypothetical: a reference template file is missing from the skill set installation.

```
> wiki-init --mode new --language ko --deepscan-tool understand-anything

[ResearchWiki] Reference asset missing from the skill set:
  reference/bundle/templates/ko/experiment.md

This is a skill-set packaging bug, not a researcher-fixable error. wiki-init
will not fall back to generating templates from memory — that would silently
introduce drift in the very documents the rest of the skill set treats as
the source of truth.

Aborting. Please report this to the skill-set maintainer or reinstall the
skill bundle.
```

The skill refuses to invent. This is the protection that makes the whole "verbatim copy" contract meaningful — once the skill silently regenerates one template from training data, the byte-stability guarantee is broken everywhere downstream (wiki-log auto-link rules, wiki-lint frontmatter checks, etc., all assume the template structure is what the bundle ships).
