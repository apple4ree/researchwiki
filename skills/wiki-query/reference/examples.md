# `wiki-query` — Worked Examples

> Supplementary material for `wiki-query`. Not loaded at LLM runtime — read for orientation, design discussion, or when debugging unexpected output.

---

## Example 1 — Happy path

The researcher wants to find pages about rotary attention.

```
> wiki-query "rotary attention"

1. wiki/concepts/attention.md                            score 8.3
   ...around line 42:
   The MultiHeadAttention block uses scaled dot-product attention with rotary
   position embedding. We chose this over standard sinusoidal embeddings because
   ...

2. wiki/papers/sparse-attention.md                       score 6.1
   ...around line 18:
   Authors propose sparse attention patterns to reduce the O(n²) cost; they do
   not address rotary embeddings, so this is orthogonal to our experiments.
   ...

3. wiki/experiments/exp-2026-04-19.md                    score 4.7
   ...around line 31:
   Compared three attention variants on the rotary benchmark; results in the
   appendix table show RoPE outperforming ALiBi by 1.2 BLEU.
   ...

(7 more results suppressed; pass --top 20 to see them)
```

The researcher opens `wiki/concepts/attention.md` and reads. wiki-query has done its job — it never claimed any page contained "the answer", only that these pages mention the search terms.

---

## Example 2 — Scoped query

The researcher only wants paper notes:

```
> wiki-query "attention" --scope papers --top 5

1. wiki/papers/sparse-attention.md                       score 7.4
   ...
2. wiki/papers/flash-attention.md                        score 6.8
   ...
3. wiki/papers/attention-is-all-you-need.md              score 6.5
   ...
```

`--scope` narrows the corpus deterministically. No experiment or concept pages will appear, even if they have higher raw scores.

---

## Example 3 — No results

```
> wiki-query "blockchain"

0 results in wiki/ (excluding meta pages).

Suggestions:
  - drop quotes if you used them
  - try shorter or alternate terms
  - rerun with --include-meta to include log.md / questions.md

Exit code: 1.
```

The skill is honest about the empty result. No "did you mean..." inference — that would be speculation about what the researcher really meant.

---

## Example 4 — Frontmatter-only search by code path

The researcher wants every page that lists `src/trainer.py` in `refs.code`:

```
> wiki-query "src/trainer.py" --frontmatter-only

1. wiki/concepts/training-loop.md                        score 5.0
   ...frontmatter:
   refs.code:
     - path: src/trainer.py
       symbol: Trainer
       confidence: verified

2. wiki/experiments/exp-2026-04-19.md                    score 5.0
   ...frontmatter:
   refs.code:
     - path: src/trainer.py
       symbol: Trainer.train_one_epoch
       confidence: verified
```

This duplicates what `index/reverse_refs.json` provides in machine-readable form, but is convenient for ad-hoc browsing without pulling out `jq`. For programmatic access (impact analysis tools, lint helpers), prefer the JSON.

---

## Example 5 — Refining a too-broad query

The researcher's first query returns too many irrelevant results:

```
> wiki-query "model"
(28 results, mostly noise)

> wiki-query "model" --scope decisions --top 5
(5 design decisions that mention "model" — much more useful)

> wiki-query "model checkpoint format"
(2 highly specific results)
```

There is no "smart" suggestion engine — the researcher iterates by adjusting flags or terms. The skill stays stateless and predictable.

---

## Example 6 — Stale badge in action

After `wiki-sync` flagged `OldAttention` as stale on `attention.md` 23 days ago:

```
> wiki-query "attention rotary"

1. ⚠ wiki/concepts/attention.md  [stale: 1 ref unaddressed for 23d]   score 8.3
   ...around line 42:
   The MultiHeadAttention block uses scaled dot-product attention with rotary
   position embedding. We chose this over standard sinusoidal embeddings because
   ...
```

The badge surfaces the body / frontmatter decoupling risk. The researcher can either trust the page cautiously, or run `wiki-fix-stale` to address the stale ref before relying on the content. The page is **not filtered out** — wiki-query's job is to retrieve, the researcher's job is to judge. Suppress with `--no-stale-warnings`.
