# ResearchWiki

> A skill set for LLM coding agents that maintains a **living research journal** — structured, cross-linked, honest — while you do the research.

A vertical application of the [Codified Context](https://arxiv.org/abs/2602.20478) framework to the research domain.

## Status

**Draft v0.3 — five MVP + two retrieval + one remediation skill, all specs and implementations drafted.**

This repository contains the architecture specification, per-skill design documents (`SPEC.md`), `SKILL.md` documents, and Python implementations for all 8 skills: five MVP skills (`wiki-init`, `wiki-log`, `wiki-sync`, `wiki-deepscan`, `wiki-lint`), two retrieval extensions (`wiki-query`, `wiki-recall`), and one remediation skill (`wiki-fix-stale`) that closes the body / frontmatter decoupling gap with strict P3 compliance. `wiki-log` is the only Python + LLM hybrid (the conversational interview + P8 detection require LLM reasoning); the other 7 skills are pure code. Other-language `wiki-sync` scanners and release packaging are still pending — see "Not yet done" below.

## What problem this solves

Researchers accumulate knowledge in three forms at once: code they write, papers they read, and experiments they run. The connections between them — which code implements which paper's idea, which experiment tested which hypothesis, which design decision resolved which contradiction — are where the real understanding lives. These connections are rarely captured. They live in the researcher's head, get forgotten, and have to be rediscovered.

Existing tools address at most one of these. Zotero handles papers. MLflow handles experiments. Understand-Anything handles code. None of them handle the *crossings*.

ResearchWiki is the glue layer. An LLM agent with this skill set maintains a markdown wiki that links across all three, updates as the research evolves, and refuses to speculate.

## How it works

Three cooperating layers inside a `wiki/` directory:

- **Wiki Layer** — the researcher's interpretations, decisions, paper summaries (daily updates, human-authored with LLM help)
- **Index Layer** — a lightweight factual snapshot of the current codebase (regenerated on demand)
- **Deep Analysis Layer** — optional rich code knowledge graph via [Understand-Anything](https://github.com/Lum1104/Understand-Anything) (regenerated weekly or at milestones)

Eight skills — five MVP, two read-only retrieval extensions, one remediation skill:

| Skill | When | Tier |
|---|---|---|
| `wiki-init` | First-time setup | MVP |
| `wiki-log` | Record any new entry (experiment, paper, decision, note) | MVP |
| `wiki-sync` | Daily refresh of the code index + stale-link check + reverse-ref index | MVP |
| `wiki-deepscan` | Weekly / milestone refresh of the deep knowledge graph | MVP |
| `wiki-lint` | Audit wiki health — broken links, speculation, gaps, contradictions | MVP |
| `wiki-query` | Natural-language search over wiki contents (read-only) | extension |
| `wiki-recall` | Surface stale-but-relevant pages relative to recent activity (read-only) | extension |
| `wiki-fix-stale` | Walk the researcher through unresolved stale refs and apply per-occurrence-approved body edits | remediation |

## The eight principles

Design is governed by eight numbered principles defined in `ARCHITECTURE.md §1.4` and enforced in `CLAUDE.md`. The most important:

- **P1 — Fact and interpretation stay separate.**
- **P3 — Skills propose; they do not mutate interpretation.**
- **P7 — Every claim has provenance.**
- **P8 — Analysis yes, speculation no.**

P8 is the heart of the design. The LLM agent writes only what it can ground in sources. When it cannot, it says so explicitly. Speculation, if it happens at all, is tagged `[speculation]` and quarantined.

## Repository layout

```
.
├── README.md                       ← you are here
├── ARCHITECTURE.md                 ← full design rationale (read this second)
├── CLAUDE.md                       ← constitution for LLM agents working on a ResearchWiki repo
├── skills/                         ← per-skill SPEC.md (design) + SKILL.md (implementation)
│   ├── wiki-init/                  ← MVP — SPEC.md + SKILL.md + reference/ (constitution + config + templates bundled for init-time copy)
│   ├── wiki-log/                   ← MVP — SPEC.md + SKILL.md
│   ├── wiki-sync/                  ← MVP — SPEC.md + SKILL.md
│   ├── wiki-deepscan/              ← MVP — SPEC.md + SKILL.md
│   ├── wiki-lint/                  ← MVP — SPEC.md + SKILL.md
│   ├── wiki-query/                 ← extension (retrieval) — SPEC.md + SKILL.md
│   ├── wiki-recall/                ← extension (surfacing) — SPEC.md + SKILL.md
│   └── wiki-fix-stale/             ← remediation — SPEC.md + SKILL.md
├── prompts/                        ← authoring guides
│   ├── writing-skill-md.md         ← how to author a SKILL.md for this project
│   ├── enforcing-p8.md             ← the hardest principle, in operational detail
│   └── skill-interplay-scenarios.md← six worked scenarios of skills composing
└── docs/                           ← reserved for longer-form docs (TBD)
```

Read order for a new contributor:

1. This README
2. `ARCHITECTURE.md`
3. `CLAUDE.md`
4. One skill SPEC.md to get a feel (start with `wiki-log`)
5. `prompts/enforcing-p8.md`

## Install as a Claude Code plugin

This repository is a [Claude Code plugin](https://code.claude.com/docs/en/plugins.md) — `.claude-plugin/plugin.json` manifest at the root, eight skills under `skills/`. After install, every skill becomes a slash command namespaced under the plugin name (e.g., `/researchwiki:wiki-log`).

**Prerequisite — Python package.** The skills' `SKILL.md` files invoke CLI commands (`wiki-init`, `wiki-log`, `wiki-sync`, ...) that ship with the Python package in this repo. Install it first:

```bash
git clone https://github.com/jeongdamilab/skill_factory.git
cd skill_factory
pip install -e .
```

(The seven Class A skills are pure Python; `wiki-log` is a Python + LLM hybrid — see `ARCHITECTURE.md §3.5`.)

**Plugin install.** Two paths:

- **Local dev** — point Claude Code at the cloned repo:
  ```bash
  claude --plugin-dir /path/to/skill_factory
  ```
  Inside Claude Code: `/researchwiki:wiki-init`, `/researchwiki:wiki-log`, etc.

- **From a marketplace** — once published to a `.claude-plugin/marketplace.json` repo:
  ```
  /plugin marketplace add <org>/<plugin-repo>
  /plugin install researchwiki@<marketplace-name>
  ```

**Bundle path resolution.** `wiki-init` ships a runtime asset bundle (`skills/wiki-init/reference/bundle/`) that gets copied verbatim to the target repo at init time. The locator (`src/researchwiki/init.py:_find_bundle`) tries env overrides (`RESEARCHWIKI_BUNDLE`, `CLAUDE_PLUGIN_ROOT`) before falling back to the source-relative path. Editable installs (`pip install -e .`) and Claude-Code-managed plugin installs both work without configuration.

## Implemented

Source under `src/researchwiki/`. CLI entry points via `pip install -e .`.

- **`wiki-init` v0.1** — bootstraps a target repo into a ResearchWiki workspace by copying the bundle (`skills/wiki-init/reference/bundle/{CLAUDE.md, research-wiki.config.yaml, templates/<lang>/}`) into place and seeding the wiki/index/deep/raw/templates directory scaffolding. Substitutes `language.default` per `--language` (only post-copy substitution; otherwise byte-for-byte verbatim). Generates the four wiki meta files (index/log/questions/discrepancies) and appends a first log entry recording the init event. Idempotent — re-runs skip existing files and append a new init log entry. `.gitignore` handling adds `deep/knowledge-graph.json` (idempotent). CLI: `wiki-init [target] --mode new --language ko -y`.
- **`wiki-sync` v0.1** — Python (stdlib `ast`), JSON (top-level keys), and Markdown (ATX headings, frontmatter / code-fence aware) scanners. Produces `index/signatures.json`, `index/reverse_refs.json`, and per-run `index/snapshots/sync_*.md`. Stale-link pass marks frontmatter `stale: true` and appends to `wiki/questions.md` (idempotent on re-run; never touches wiki page bodies). CLI: `wiki-sync --repo <path>`.
- **`wiki-lint` v0.1** — all 8 mechanical checks: frontmatter schema, `authored_by` enum, intra-wiki link existence (Obsidian-style root-relative resolution), `refs.code.path` file existence, speculation density (default 0.30 threshold), persistent stale-ref age (default 7 days), cross-page `confidence` conflicts, orphan pages with `seeded_by:` grace period (default 30 days). Meta pages excluded from frontmatter/speculation checks. Audit report + append to `wiki/questions.md` / `wiki/discrepancies.md`. `--strict` for release gating. CLI: `wiki-lint --repo <path>`.
- **`wiki-deepscan` v0.1** — wrapper around an external knowledge-graph tool (typically Understand-Anything). Loads a graph (or invokes the binary), filters architecturally significant nodes by inbound-edge threshold, seeds wiki concept stubs (frontmatter-only + structural facts + open-questions template — never LLM-authored prose), appends verified `refs.code` to existing same-concept pages, detects naming conflicts (logs to `wiki/questions.md`) and graph-vs-frontmatter discrepancies (logs to `wiki/discrepancies.md`). Writes `deep/knowledge-graph.json`, `deep/last-scan.yaml`, and per-run `deep/deepscan-report-*.md`. `--from-graph <path>` lets you feed a pre-built graph (for testing or non-UA tools). CLI: `wiki-deepscan --repo <path>`.
- **`wiki-query` v0.1** — BM25 lexical search over wiki contents. Tokenizer splits on identifier delimiters (snake/camel/kebab + dots/slashes) AND keeps the whole chunk for exact-path queries; ko/en mix preserved. Returns ranked page paths with extractive snippets to stdout. Pages with unresolved `stale: true` flags get a `⚠ stale: …` badge prefix. Meta pages skipped by default; `--include-meta` opts in. `--scope`, `--top`, `--frontmatter-only`, `--no-stale-warnings` flags. Stdlib only. CLI: `wiki-query "rotary attention" --repo <path>`.
- **`wiki-recall` v0.1** — surfaces stale-but-relevant pages by intersecting recent `wiki/log.md` activity refs with stale-page frontmatter. Skill-meta entries (`from wiki-sync`, `from wiki-lint`, `from wiki-deepscan`) filtered by header pattern. Default ref weights: code=2.0, concepts=1.5, papers=1.0, experiments=1.0. `seeded_by:` / `authored_by: llm` empty-body stubs excluded by default; `--include-stubs` opts in. `--lookback`, `--stale-since`, `--scope`, `--top` flags. CLI: `wiki-recall --repo <path>`.
- **`wiki-sync` v0.2** — three additions on top of v0.1:
  - `--scan-body` body link rot (opt-in heuristic). Tokenizes wiki page bodies with a multi-cap-PascalCase + dotted + paren-suffix regex (avoids English false-positives like "Use" / "Set"). Records missing tokens as `body_stale_mentions: [{line, token, detected}]` in frontmatter. Implicitly `[unverified]`.
  - **Rename heuristic.** After the symbol diff, pairs removed × added symbols by same path + line proximity + `difflib` signature similarity (default 0.80). Output as `## Possible renames (heuristic, [unverified])` section in the snapshot. Configurable via `sync.rename_heuristic.{enabled, similarity_threshold, line_window}`.
  - **End-of-run nag.** When unresolved `stale: true` flags older than `sync.nag_after_days` (default 7) exist, prints `⚠ stale 플래그 N개, X일 이상 미해결. wiki-fix-stale로 처리하시겠어요?`. Suppress with `--no-nag`.
- **`wiki-fix-stale` v0.1** — the *one* P3-carve-out skill that legitimately edits wiki page bodies, under researcher-initiated invocation + per-occurrence approval + four mechanical transformations (replace symbol with researcher-supplied identifier / wrap with `[deprecated YYYY-MM-DD]` tag / delete the line / skip). After all occurrences on a page are addressed, `stale: true` flags and `body_stale_mentions:` entries are auto-cleared from frontmatter. Walks both frontmatter `refs.code` stale flags AND `body_stale_mentions:` from `wiki-sync --scan-body`. Session record appended to `wiki/log.md`. Atomic per page (mid-page abort discards in-memory edits). Dependency-injected `prompt_fn` and `display_fn` for testability. CLI: `wiki-fix-stale --repo <path>`.
- **`wiki-log` v0.1 (Python + LLM hybrid)** — the *only* LLM-essential skill. Mechanical core (`src/researchwiki/log.py` + 5 CLI subcommands: `inspect`, `lookup-symbols`, `find-pages`, `find-amend-target`, `run`) handles template parsing (HTML-comment-aware, `{{PLACEHOLDER}}`-quoting), `index/signatures.json` lookup, exact-slug page lookup, atomic write of entry + log.md append + index.md update + bidirectional back-refs + concept stub creation + questions.md append. The conversational interview (italic-guide paraphrasing, P8 detection + three-route flow, identifier/noun-phrase extraction, summary writing) is the LLM's job, guided by 9 reference docs under `skills/wiki-log/reference/` (notably `p8-detection.md`, `conversational-style.md`, `auto-link-extraction.md`, `refusal-patterns.md`, `templates-deep-dive.md`). `authored_by: llm` is rejected by the validator — every entry requires human intent. CLI: `wiki-log {inspect | lookup-symbols | find-pages | find-amend-target | run} ...`.
- **`docs/CONFIG.md`** and **`docs/TEMPLATES.md`** — user-facing reference docs aggregating per-skill `consumed-config.md` files and the wiki-log template format.
- **Integration tests** under `tests/integration/` exercise the cross-skill data flow on temp-directory fixtures bootstrapped by `wiki-init`. Five end-to-end scenarios (refactor remediation, weekly audit + query + recall, deepscan stub × lint orphan grace, body link rot round trip, wiki-log full CLI flow) plus two pairwise contracts (recall filters skill-meta log entries, fix-stale clears the same finding lint reports).

168 tests, all passing (159 unit + 9 integration).

## Not yet done

- Other-language scanners for `wiki-sync` (TypeScript / JavaScript via tree-sitter, ctags fallback)
- Release packaging (license, classifiers, CI, PyPI)

## License and status

This project is designed with eventual open-source release in mind. License selection and release timing are at the author's discretion.

Citations to Codified Context (arXiv:2602.20478) and Understand-Anything (github.com/Lum1104/Understand-Anything) are mandatory in any derivative work.
