# `wiki-query` — Open Questions

> Supplementary material for `wiki-query`. Not loaded at LLM runtime — these are deferred design decisions for future iterations.

---

## 1. Backend

**Status:** MVP lexical; semantic reserved.

The MVP backend is BM25-style lexical scoring. A v2 extension could add embedding-based semantic re-ranking using a local sentence-transformer model (e.g., `ko-sentence-transformers` for Korean-heavy wikis). Config field `query.backend: lexical | hybrid` is reserved for this.

**Decision needed before implementing:** which embedding model? How is the index built and refreshed? Does it become a `wiki-sync` responsibility (precompute embeddings) or a `wiki-query` responsibility (compute on demand)?

---

## 2. Korean tokenization

**Status:** MVP whitespace + identifier split.

The MVP tokenizer under-segments Korean compound nouns (e.g., "주의집중" stays as one token instead of "주의" + "집중"). Mixed ko/en text (e.g., "rotary attention 적용") is correctly split at the space boundary, but pure Korean compounds are not.

**Proposed:** ship as-is for MVP; add a ko-morphological adapter behind `query.ko_tokenizer:` config when researcher feedback shows real loss.

---

## 3. Result `match_type` field

**Status:** proposed for v1.1.

Each result currently shows just a numeric score. A `match_type ∈ {exact, partial, frontmatter-only}` field would expose *why* a page was returned — useful for debugging unexpected rankings and for the researcher to judge relevance.

**Decision needed:** the field's enum values (the three above are a starting set) and how it surfaces in stdout (inline next to score? separate column?).

---

## 4. Pagination

**Status:** rejected.

Currently `--top N` controls result count. Should there be `--page` for browsing past N?

**Decision:** no. The skill is stateless; re-invoke with a larger `--top`. Pagination would imply caching previous results, which contradicts the deterministic, single-query model.

---

## 5. Should `--frontmatter-only` honor `--scope`?

**Status:** ambiguous in MVP.

Currently `--frontmatter-only` is a search-mode toggle, and `--scope` is a corpus filter. They compose without conflict, but the interaction is not documented. Specifically: if a user runs `wiki-query "src/trainer.py" --frontmatter-only --scope concepts`, do they expect (a) only `wiki/concepts/` pages whose frontmatter matches, or (b) "frontmatter-only" to override `--scope` and search all pages' frontmatter?

**Proposed:** (a). `--scope` is always a corpus filter; `--frontmatter-only` is always a match-mode toggle. Document explicitly.
