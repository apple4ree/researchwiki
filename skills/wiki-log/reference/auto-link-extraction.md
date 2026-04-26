# `wiki-log` — Auto-link Candidate Extraction

> Supplementary material. The Python `wiki-log lookup-symbols` and
> `wiki-log find-pages` commands answer "is this in the index/wiki?"
> deterministically. This file covers the *prior step*: scanning the
> researcher's prose to decide which tokens / phrases / IDs to send
> for lookup in the first place.
>
> Aggressive fuzzy-matching here costs more than it saves — false
> positives spam the approval batch and erode researcher trust. Be
> conservative; when in doubt, ask.

---

## 1. Four kinds of candidates

The template's `_template.auto_link.<kind>` directive names which
kinds to scan. For each enabled kind, run a separate extraction pass.

| Kind | Strategy | Source sections (typical) |
|---|---|---|
| `code` | identifier-shape tokens → `lookup-symbols` | `관련 코드`, `Method summary`, body wherever identifiers appear |
| `experiments` | `exp-YYYY-MM-DD-*` ID pattern → `find-pages --kind experiments` | `셋업`, `다음 단계`, body anywhere |
| `papers` | paper-slug or `[[slug]]` pattern → `find-pages --kind papers` | `Implications`, `관찰`, anywhere a citation appears |
| `concepts` | exact-slug match for noun phrases → `find-pages --kind concepts` (failed matches → stub batch) | anywhere; concepts are the most semantically-loaded |

Disabled kinds (`enabled: false` in the template directive) are
skipped entirely — do not even propose candidates.

## 2. Identifier-token extraction (for `code`)

### Token shapes

| Shape | Example | Notes |
|---|---|---|
| snake_case | `train_one_epoch` | Most common Python identifier |
| PascalCase | `MultiHeadAttention` | Class names |
| camelCase | `loadCheckpoint` | Less common but valid |
| Dotted | `Trainer.train_one_epoch` | Method via parent class |
| Path | `src/trainer.py` | File path; `lookup-symbols` matches against `paths_seen` |
| Path:line | `src/trainer.py:23` | Don't extract the line — strip `:23`, send `src/trainer.py` |
| With trailing parens | `train_one_epoch(...)` | Strip parens before lookup |
| Backtick-wrapped | `` `Trainer` `` | Strip backticks |

### What NOT to send to `lookup-symbols`

These look identifier-shaped but are common false positives:

- **English words that are also identifiers** — `Set`, `Mock`, `Type`,
  `New`, `Use`. Heuristic: skip 1–4 character PascalCase tokens unless
  the body has at least two surrounding identifiers (e.g.,
  `Set` next to `Mock` in a clear test-related context).
- **Numbers / units** — `bs=256`, `lr=3e-4`, `step 340` — none of
  these are symbol candidates.
- **Greek letters / math** — `α`, `β`, `λ` — never identifiers.
- **HTTP / URL fragments** — drop tokens like `localhost:8080`, `http`.
- **Common English nouns happening to be PascalCase from being at
  sentence start** — "Loss is high" → don't extract `Loss`. Skip
  the first token of any sentence unless it appears mid-sentence
  elsewhere too.

### Per-section extraction tuning

- `관련 코드` / `Code` / `Implementation`: aggressive — extract
  everything identifier-shaped. The researcher chose to put it here.
- `셋업` / `Setup`: aggressive for code identifiers, conservative for
  short tokens.
- `결과` / `Results`: medium — researchers often paste metric names
  (`val_loss`, `grad_norm`) that are *variable* names, not symbol
  names. Send them but expect most to fail.
- `관찰` / `Observations`: conservative — prose-heavy, many false
  positive candidates.
- `다음 단계`: skip — future-tense plans usually reference
  yet-unwritten symbols.

### Example walk

Researcher's `관련 코드` answer:
> trainer.py 메인 루프, 특히 train_one_epoch(). 그리고 src/data/loader.py의 DataLoader 도 관련.

Extracted tokens (in order, deduped):
```
trainer.py, train_one_epoch, src/data/loader.py, DataLoader
```

Send to `lookup-symbols`:
```bash
wiki-log lookup-symbols --tokens "trainer.py,train_one_epoch,src/data/loader.py,DataLoader"
```

Expected JSON:
```json
[
  {"token": "trainer.py", "matched": true, "path": "src/trainer.py", "confidence": "verified"},
  {"token": "train_one_epoch", "matched": true, "path": "src/trainer.py", "symbol": "train_one_epoch", "confidence": "verified"},
  {"token": "src/data/loader.py", "matched": true, "path": "src/data/loader.py", "confidence": "verified"},
  {"token": "DataLoader", "matched": true, "path": "src/data/loader.py", "symbol": "DataLoader", "confidence": "verified"}
]
```

`matched: false` candidates → present to researcher with the option
to record as `confidence: inferred` if they confirm the symbol exists
but is not yet in `index/signatures.json` (e.g., a private helper in
a file the scanner hasn't picked up).

## 3. Experiment-ID extraction (for `experiments`)

### The pattern

Experiments are slugged `exp-YYYY-MM-DD-<short-name>`. Detection:

```regex
exp-\d{4}-\d{2}-\d{2}-[a-zA-Z0-9-]+
```

### When to extract

- `셋업` section — researchers often reference prior runs ("vs
  exp-2026-04-22-bs128, bs=256"). Always extract.
- `결과` / `관찰` — sometimes; extract if seen.
- `다음 단계` — often references *future* exp-IDs ("후속 실험
  exp-2026-04-25-...") — these will fail `find-pages` because they
  don't exist yet. Either skip extraction here, or extract and let
  the failed lookup drop them from candidates.

### Bidirectional flag

The experiment template's `auto_link.experiments.link_bidirectional:
true` means: when an exp-ID is approved as a ref, the *target* page
gets a back-ref entry too. The Python core handles this in `run_log`
— you only need to ensure the approved IDs land in
`payload.approved_refs.experiments`.

## 4. Paper-slug extraction (for `papers`)

### The pattern

Papers have flexible slugs (`vaswani-2017`, `attention-is-all-you-need`,
`gpt4-tech-report-2023`). Two detection forms:

1. **Wiki-link syntax:** `[[vaswani-2017]]` or `[[attention-is-all-you-need]]`
   — high-confidence; the researcher explicitly opted in.
2. **Bare slug** matching exactly an existing `wiki/papers/<slug>.md` —
   medium-confidence; require a `find-pages --kind papers` lookup
   to confirm.

### What NOT to extract

- Author–year shorthand without a wiki-link wrapper ("Vaswani et al. 2017")
  — too many false matches against unrelated papers. If the researcher
  wrote it bare, ask: "Vaswani et al. 2017 — wiki/papers/vaswani-2017?
  맞으면 [[vaswani-2017]] 로 표시해줄게."
- Paper *titles* in prose ("the Attention is All You Need paper") —
  same: ask if they want it slugged.
- DOIs / arXiv IDs — out of scope for v0.1; record only if explicit
  in the body, not as auto-link.

### Note: papers usually disabled for experiment template

The default experiment template ships with `auto_link.papers.enabled:
false` (papers rarely appear in raw experiment-result prose). Honor
that. The researcher can `refs.papers` manually in the entry file post-write.

## 5. Concept noun-phrase extraction (for `concepts`)

This is the hardest extraction — concepts have no fixed shape.

### What qualifies as a concept candidate

- Multi-word noun phrases with technical specificity:
  `rotary embedding`, `flash attention`, `gradient accumulation`
- Hyphenated compound terms: `cross-entropy`, `data-parallel`,
  `fine-tuning`
- ML-jargon single nouns when domain-specific:
  `attention`, `dropout`, `quantization`
- Proper-noun frameworks/methods: `LoRA`, `RLHF`, `DPO`

### What does NOT qualify

- Generic English / Korean nouns: `model`, `result`, `paper`, `결과`,
  `함수`, `사람`. These are not concepts.
- Brand names of products/companies: `OpenAI`, `Anthropic`, `Hugging Face`
  — these are *organizations*, not concepts. Don't auto-stub.
- People's names: `Vaswani`, `Hinton` — not concepts.
- Verbs: `to fine-tune` — the noun form `fine-tuning` is the concept.
- Hyperparameter names alone: `batch size`, `learning rate` — too
  generic; only concept if domain-specific (e.g., `cosine learning rate
  schedule`).

### Slug computation

Convert the noun phrase to a slug:
- Lowercase
- Replace spaces with hyphens
- Drop punctuation except hyphens and underscores
- Remove articles (`a`, `an`, `the`) at the start: "the rotary embedding" → `rotary-embedding`
- Strip plural `s` if it would change the canonical form: "rotary embeddings" → `rotary-embedding`

Examples:
- `rotary embedding` → `rotary-embedding`
- `Flash Attention` → `flash-attention`
- `KV cache` → `kv-cache`
- `LoRA fine-tuning` → `lora-fine-tuning` (or `lora`? — ask)

### The two-pass match

1. Compute slug; call `find-pages --kind concepts --ids <slug>`.
2. If `matched: true` → existing concept page; add to `payload.approved_refs.concepts`.
3. If `matched: false` → candidate for the **stub suggestion batch**
   (separate approval pass per `conversational-style.md` §5).

### Bidirectional flag

The experiment template has `auto_link.concepts.link_bidirectional:
true`. The target concept page (existing or newly-stubbed) gets a
back-ref to the new entry. The Python core handles this when the
target exists at `wiki-log run` time — for newly created stubs,
the stub's frontmatter `refs.experiments` (or appropriate kind)
needs to point at the new entry. **Currently this is not automated**
— the LLM may need to manually issue a follow-up to update the stub.
File this in `open-questions.md` if you encounter it.

## 6. Korean / English mixed prose

ML researchers freely mix Korean and English. The same identifier-shape
rules apply regardless of surrounding language:

```
trainer.py에서 train_one_epoch을 호출했고, 결과는 val_loss=1.24
```

Tokens to extract: `trainer.py`, `train_one_epoch`, `val_loss`.

For concept noun phrases in mixed prose, the *English* form usually
wins as the slug (the canonical wiki/concepts/ slug is in English by
convention even on a Korean-language wiki):

```
rotary embedding은 길이 적응을 잘 함
```

→ extract candidate phrase `rotary embedding`, slug `rotary-embedding`.

## 7. Confidence assignment

After `lookup-symbols` returns:

| Source | Confidence in payload |
|---|---|
| Exact unique match in `index/signatures.json` | `verified` |
| Researcher-confirmed (after `matched: false` push-back) | `inferred` |
| No researcher confirmation | drop from refs entirely |

**Never** stamp `verified` on something that did not come back from
`lookup-symbols` matched. P7 — provenance — depends on this.

## 8. The whole pipeline (summary)

```
1. wiki-log inspect → template.template_directives.auto_link
2. For each kind with enabled=true:
   a. Scan section_answers for kind-specific candidates
   b. Run lookup-symbols / find-pages (deterministic)
   c. Filter to matched=true; collect failed for stub suggestion (concepts only)
3. Present approval batch to researcher (one batch, kind-grouped)
4. Present stub suggestion batch (concepts only, for failed matches)
5. Assemble payload.approved_refs and payload.approved_stubs
6. wiki-log run --payload <file>
```

Steps 1, 2b, 6 are CLI. Steps 2a, 2c, 3, 4, 5 are LLM judgment.

---

**The shorthand:** extraction is conservative pattern-matching, not
semantic interpretation. When you find yourself reasoning about
*what the token means*, stop — that is interpretation, and
interpretation requires researcher approval per the auto-link
batch. Your job here is to *propose*, not to *decide*.
