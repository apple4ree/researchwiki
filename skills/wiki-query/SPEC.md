# Skill Spec: `wiki-query`

> **Frequency:** On-demand, every time the researcher needs to find a wiki page whose path they cannot recall
> **Tier:** Read-only retrieval
> **Writes to:** Nothing.

## Purpose

Take a natural-language query string from the researcher and return a ranked list of wiki pages that match it, with extracted snippets. wiki-query exists because grep is too narrow (it requires the researcher to remember exact wording) and `wiki/index.md` is too coarse (it is a flat catalog).

This is a **retrieval** skill, not a synthesis skill. The output is *pointers* to existing pages and *extracted spans* from those pages. wiki-query never composes an answer from page contents.

## When to invoke

- "Where is that page about attention I wrote three months ago?" (recall failure)
- "Which experiments referenced the `LegacyTrainer` class?" (cross-link discovery)
- Pre-`wiki-log`: "Have I already written about this?" (duplicate avoidance)
- Pre-paper-write: "What was my reasoning for this hyperparameter?" (citation traceback)

## When NOT to invoke

- For an LLM-synthesized summary of multiple pages → wiki-query returns pointers only.
- For listing all pages of a type → use `wiki/index.md` or `ls wiki/concepts/`.
- For finding stale or orphan pages → use `wiki-lint`.
- For surfacing stale-but-relevant pages → use `wiki-recall`.

## Inputs

| Flag | Default | Rationale |
|---|---|---|
| query (positional) | required | The string to search for; quote if multi-word |
| `--top N` | 10 | Limit result count |
| `--scope` | `all` | Limit to a wiki subdirectory (`concepts \| papers \| experiments \| decisions`) |
| `--include-meta` | off | Opt in to log.md / questions.md / discrepancies.md / index.md noise |
| `--snippets` | `one` | Density of extracted spans per result (`none \| one \| all`) |
| `--frontmatter-only` | off | Search refs / tags without prose noise |
| `--no-stale-warnings` | off | Suppress `⚠ stale: …` badge prefix |

Consumed config keys: `paths.wiki`, `paths.index`, `query.backend`, `query.stale_warnings`, `query.ko_tokenizer`, `query.top_default`. See `reference/consumed-config.md` for defaults and rationale.

## Outputs

Stdout only. Format: ranked list `<rank>. <stale-badge?> <path>  score <N>` followed by snippet(s). Pages with unresolved `stale: true` flags get a `⚠ stale: …` badge prefix — informational, not a filter. Exit code `0` if ≥1 result, `1` if zero (shell-pipeline friendly).

## Behavior contract

- **Read-only.** No file writes. (P1, P3)
- **No synthesis.** Pointers + extractive snippets only. Snippets are verbatim spans with `...` truncation. (P8)
- **Deterministic.** Mechanical BM25 scoring; no LLM judgment in scoring or selection.
- **Lexical MVP backend.** Whitespace + identifier tokenizer (snake/camel/kebab + ko/en mix). Embedding-based semantic search reserved for v2 behind `query.backend: hybrid`. (P4)
- **Frontmatter included in corpus.** `refs.code`, tags, etc., are directly searchable.
- **Meta pages skipped by default.** Append-only diaries would dominate keyword frequency. `--include-meta` opts in.
- **Stale awareness informational.** Badge prefix surfaces decoupling risk; ranking and content unchanged. (P7)
- **No "did you mean".** Empty results suggest structural broadening; never invent alternate queries. (P8)

## Reference

- Worked examples: `reference/examples.md`
- Full failure-mode catalog: `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys (per-skill index; full schema in `docs/CONFIG.md` TBD): `reference/consumed-config.md`
