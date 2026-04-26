---
name: wiki-init
description: Use this skill when the researcher wants to bootstrap a repository into a ResearchWiki workspace for the first time — creates the directory layout, the `research-wiki.config.yaml` config, the `CLAUDE.md` constitution, the four default templates under `templates/`, and the seed wiki pages so that the rest of the skill set — the five MVP skills (`wiki-log`, `wiki-sync`, `wiki-deepscan`, `wiki-lint`), the read-only retrieval extensions (`wiki-query`, `wiki-recall`), and the remediation skill `wiki-fix-stale` — can run. Trigger phrases include "ResearchWiki 셋업해", "리서치 위키 초기화", "wiki-init 실행", "research wiki 시작하자", "bootstrap the research wiki", "initialize researchwiki", "set up the wiki". Do not use when `CLAUDE.md` and `research-wiki.config.yaml` already exist in the target repo (tell the researcher to edit those files directly instead). Do not use for regenerating the code index (use `wiki-sync`), running deep code analysis (use `wiki-deepscan`), adding a new journal entry (use `wiki-log`), or auditing an existing wiki (use `wiki-lint`).
---

# wiki-init

> **Invocation:** `wiki init [target] [--language ko|en] [--mode new|adopt] [-y]` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Bootstrap a repository into a ResearchWiki workspace. Runs once per project. Idempotent — re-running on an initialized repo does not destroy existing content.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Creates the directory structure that enforces the separation (`wiki/` interpretation, `index/` and `deep/` fact).
- **P3 — Propose, do not mutate interpretation.** Never overwrites existing wiki content. On any conflict, reports and asks.
- **P4 — Configuration over convention.** Writes `research-wiki.config.yaml` with sensible defaults, customizable post-init.
- **P7 — Explicit uncertainty.** Stamps every generated page with `authored_by: llm` frontmatter so the origin is always visible.
- **P8 — Analysis yes, speculation no.** Does not analyze existing code, papers, or notes. Seed pages contain only structural scaffolding.

## When to use

- First-time setup of a new research repository.
- Adopting ResearchWiki for an existing research repo with code/notes but no wiki structure.
- Researcher explicitly says "initialize the wiki", "set up ResearchWiki", "bootstrap this repo", or Korean equivalent.

## When NOT to use

- Target repo already has both `CLAUDE.md` and `research-wiki.config.yaml` → tell researcher to edit directly, not re-init.
- For regenerating the code index → use `wiki-sync`.
- For deep code analysis → use `wiki-deepscan`.
- For new journal entries → use `wiki-log`.
- For audit reports → use `wiki-lint`.
- Repo is not a research workspace (e.g., a library for external consumers).
- Researcher says "reset the wiki" or "start over" — that is destructive; refer to manual deletion first, then re-init.

## Inputs

Accept flags. If any flag is missing, ask one focused question per missing flag.

- `--mode <new | adopt>` — `new` for clean repo; `adopt` to wrap around existing content.
- `--language <ko | en | other>` — sets `language.default` in the config. Default fallback `ko`.
- `--deepscan-tool <understand-anything | none>` — wires `wiki-deepscan`. Default `understand-anything`.
- `--seed-from <path>` — optional reference to existing notes directory (recorded in first log entry only; not imported).

## Outputs

Defaults from `ARCHITECTURE.md §2.2`; overridable in `research-wiki.config.yaml`.

**Directories created:** `wiki/{concepts,papers,experiments,decisions}/`, `index/{snapshots,audits}/`, `deep/`, `raw/{papers,experiments}/`, `templates/`.

**Files created:**
- `CLAUDE.md` — copied verbatim from `reference/bundle/CLAUDE.md`.
- `research-wiki.config.yaml` — copied verbatim from `reference/bundle/research-wiki.config.yaml`. Reference config follows minimum schema in `ARCHITECTURE.md §2.4`. Single substitution: `language.default` set per `--language` flag.
- `wiki/index.md` — empty catalog with maintenance instructions.
- `wiki/log.md` — contains first log entry (init event itself, fact-only, no interpretation).
- `wiki/questions.md`, `wiki/discrepancies.md` — empty.
- `templates/{experiment,paper_reading,design_decision,free_form}.md` — copied verbatim from `reference/bundle/templates/<lang>/`, flattened (no language subdir in target).
- `.gitignore` — append `deep/knowledge-graph.json` (idempotent if file exists).

**Files NOT created:**
- `ARCHITECTURE.md` — target repo relies on upstream design doc.
- No `SKILL.md` files written into target repo (those live in the skill set).
- No content derived from scanning existing code, papers, or notes (that is `wiki-sync` and `wiki-deepscan`'s job).

First log entry format and full reference bundle layout: `reference/consumed-config.md`.

## Behavior contract

- **Never overwrites an existing file.** On conflict, skip and report. (Idempotency)
- **Never analyzes existing code, papers, or notes.** Seed pages are structural scaffolding only. (P8)
- **Never writes interpretive content into any seed page.** No summaries, no inferences, no guesses. (P3, P8)
- **Never invokes Understand-Anything, language scanner, or any index artifact.** Those are `wiki-deepscan` and `wiki-sync`. (Skill boundaries — `ARCHITECTURE.md §3.2`)
- **Stamps `authored_by: llm` and `schema_version: 1`** on every generated page's frontmatter. (P7)
- **Copies reference assets byte-for-byte** with the single `language.default` substitution exception. If a reference asset is missing, abort — do not fall back to generating from memory. (Bundle integrity — see Failure handling)
- **Asks for confirmation before writing.** Shows proposed layout, waits for `y`, only then creates files. (Reversibility)
- **Records the init event in `wiki/log.md`.** This is the only content wiki-init authors into the wiki layer.

## Researcher interaction flow

1. Read flags. For each missing flag, ask one focused question. Do not pile multiple questions.
2. Inspect target repo to detect `--mode adopt` conflicts (existing `CLAUDE.md`, `wiki/`, `research-wiki.config.yaml`). Produce a conflict list if any.
3. Show proposed directory layout and file list, including any skipped items and reasons.
4. Ask explicit confirmation (`y / N`).
5. On `y`, create files. On anything else, abort without writing.
6. Report what was created, what was skipped, and why.
7. Show concise next-steps:
   - Run `wiki-sync` for first Index Layer snapshot.
   - (If `understand-anything` selected) optionally run `wiki-deepscan`. Detection / installation is researcher's responsibility — wiki-init does not auto-install.
   - Use `wiki-log` to record entries.

## Failure handling (essentials)

- **Permission error on write** → abort, suggest fix.
- **`adopt` mode conflict** → list conflicts, ask: skip-conflicts-create-rest or abort.
- **Mid-run interrupt** → idempotency carries recovery; re-invoke.
- **Reference asset missing** (`reference/bundle/CLAUDE.md`, `…/research-wiki.config.yaml`, or any `templates/<lang>/*.md`) → abort. Skill-set packaging bug, not researcher-fixable. Do not fall back to generating from memory.
- **`--seed-from` path doesn't exist** → warn, proceed; record as `(requested: <path>, not found)` in log entry.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference bundle (what gets copied to target)

```
skills/wiki-init/reference/bundle/
├── CLAUDE.md                          → target/CLAUDE.md (verbatim)
├── research-wiki.config.yaml          → target/research-wiki.config.yaml (verbatim except language.default)
└── templates/<lang>/                  → target/templates/ (flattened, single language)
```

If any of these is absent at invocation time, the skill aborts (see Failure handling). Layout details and rationale: `reference/consumed-config.md`.

## Reference (supplementary)

- Worked examples (5): `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Config handling (what wiki-init writes; flag → config field map; bundle layout): `reference/consumed-config.md`
- Bundle assets (the *runtime* files copied to target): `reference/bundle/`
