---
name: wiki-query
description: Use this skill when the researcher wants to find a wiki page they cannot recall the path of — a concept page, paper summary, experiment writeup, or design decision — using a natural-language query. wiki-query is **read-only** retrieval that returns ranked page paths with extracted snippets; it never composes an answer from page contents (P8). The MVP backend is lexical (BM25-style scoring with a whitespace + identifier tokenizer that handles `snake_case`, `camelCase`, `kebab-case`, and Korean/English mixed text); embedding-based semantic search is reserved for v2. The tokenizer ingests both frontmatter and body, so refs and tags are directly searchable. Trigger phrases include "wiki-query", "위키 검색", "그 페이지 어디였더라", "...에 대해 쓴 거 찾아줘", "예전에 정리한 거 찾아줘", "find the wiki page about", "search the wiki for", "where did I write about". Do not use for an LLM-synthesized summary of multiple pages — wiki-query returns pointers, the researcher reads. Do not use to list all pages of a type (use `wiki/index.md` or `ls`). Do not use to find stale or orphan pages (use `wiki-lint`). Do not use to surface stale-but-relevant pages relative to recent activity (use `wiki-recall`). Do not use to add new entries (use `wiki-log`).
---

# wiki-query

Find a wiki page by natural-language query. Return ranked paths with extracted snippets. Never synthesize.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 / P3 — Read-only on `wiki/`.** Reads pages, emits to stdout. No file writes, no frontmatter edits, no appends.
- **P4 — Configuration over convention.** Backend, tokenizer hints, default `top`, meta-inclusion, and stale-warning toggle read from `query:` section of `research-wiki.config.yaml` (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Each result carries a numeric score. Pages with unresolved `stale: true` flags get a `⚠ stale: …` badge prefix so the researcher can judge before trusting body content.
- **P8 — Analysis yes, speculation no.** Output is page paths + extractive snippets. Never composes prose, never paraphrases, never picks "the best" page in any semantic sense, never guesses the researcher's intent. Empty results suggest *structural* broadening only — no "did you mean" alternate queries.

## When to use

- Recall failure ("그 페이지 어디였더라").
- Cross-link discovery ("which experiments referenced X?").
- Pre-`wiki-log` duplicate avoidance ("have I already written about this?").
- Pre-paper-write citation traceback.
- Frontmatter-keyed browsing via `--frontmatter-only`.

## When NOT to use

- For an LLM-synthesized summary of multiple pages → wiki-query returns pointers only; the researcher reads.
- For listing all pages of a type → use `wiki/index.md` or `ls`.
- For stale/orphan auditing → use `wiki-lint`.
- For surfacing stale-but-relevant pages → use `wiki-recall`.
- For adding entries → use `wiki-log`.
- The repo is not initialized → run `wiki-init` first.

## Inputs

- Positional: **query string** (required). Quote if multi-word: `wiki-query "rotary attention"`.
- `--top N` — number of results. Default 10.
- `--scope <all | concepts | papers | experiments | decisions>` — limit to one wiki subdirectory. Default `all` (excludes meta pages).
- `--include-meta` — also search `wiki/log.md`, `wiki/questions.md`, `wiki/discrepancies.md`, `wiki/index.md`. Default off.
- `--snippets <none | one | all>` — snippet density. `none` paths only; `one` highest-scoring snippet per page (default); `all` every match.
- `--frontmatter-only` — restrict matching to frontmatter (refs, tags). Default off.
- `--no-stale-warnings` — suppress the `⚠ stale: …` badge prefix. Default off (badges shown).

## Outputs

Stdout only. No files created or modified.

```
> wiki-query "rotary attention"

1. ⚠ wiki/concepts/attention.md  [stale: 1 ref unaddressed for 23d]   score 8.3
   ...around line 42:
   The MultiHeadAttention block uses scaled dot-product attention with rotary
   position embedding. We chose this over standard sinusoidal embeddings because
   ...

2. wiki/papers/sparse-attention.md                       score 6.1
   ...around line 18:
   Authors propose sparse attention patterns to reduce the O(n²) cost; they do
   not address rotary embeddings, so this is orthogonal to our experiments.
   ...
```

Stale pages get a `⚠ stale: …` badge prefix summarizing count and age of unresolved stale refs. The badge is informational — the page is still returned. Use `wiki-fix-stale` to clear.

Exit code: `0` if at least one result, `1` if zero (pipeline-friendly). For broader worked examples (scoped queries, no-results, frontmatter-only, refining), see `reference/examples.md`.

## Behavior contract

- **Read-only.** No file writes, no frontmatter edits, no appends. (P1, P3)
- **No synthesis.** Page paths + extractive snippets only. Never composes, summarizes, paraphrases, or ranks by "answer quality". (P8)
- **Deterministic.** Same query + same wiki state → same output. Mechanical BM25 scoring; no LLM judgment in scoring or selection.
- **Lexical MVP.** BM25 over a whitespace + identifier tokenizer (handles `snake_case`, `camelCase`, `kebab-case`, ko/en mix). Frontmatter and body ingested as one document — refs and tags directly searchable. Semantic backend (embedding-based) reserved for v2 behind `query.backend: hybrid`. (P4)
- **Snippets are extractive.** Verbatim spans (±2 lines around match), `...` truncation. Never edited.
- **Meta pages skipped by default.** `wiki/log.md`, `wiki/questions.md`, `wiki/discrepancies.md`, `wiki/index.md`, and `index/audits/*` are excluded from `--scope all` (their append-only diary content would dominate keyword frequency). `--include-meta` opts in.
- **Stale awareness is informational, not a filter.** Stale pages still returned with `⚠` badge prefix; ranking unchanged; page contents not modified. (P7)
- **No "did you mean".** Empty results suggest structural broadening (drop quotes, shorter terms, `--include-meta`); never invent alternate queries. (P8)

## Failure handling (essentials)

- `wiki/` missing → abort, suggest `wiki-init`.
- Empty wiki → exit 1 with clear message.
- Empty / malformed query → refuse, exit 2.
- Page parse error → skip, log to stderr, continue.

Full failure-mode catalog: `reference/failure-modes.md`.

## Reference

- Worked examples: `reference/examples.md`
- Failure modes (full catalog): `reference/failure-modes.md`
- Open questions / deferred decisions: `reference/open-questions.md`
- Consumed config keys: `reference/consumed-config.md`
