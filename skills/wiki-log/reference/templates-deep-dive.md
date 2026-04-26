# `wiki-log` — Per-Template Authoring Guide

> Supplementary material. The `wiki-log inspect` JSON gives you the
> raw section list (titles + required flags + italic guides). This
> file tells you *what makes a strong vs weak answer* for each
> section and what anti-patterns to push back on.

---

## 1. `experiment` template

**When to use.** A run was performed (regardless of outcome). Includes
hyperparameter sweeps, ablation studies, debug runs that produced
useful negative results.

**When NOT to use.**
- A *plan* for an experiment that hasn't been run → use `free` for
  the planning note (or just don't log it yet — plans without
  results are noise).
- A finding that came from reading a paper (not from running code)
  → use `paper`.
- A code-rewriting decision that hasn't been validated by an
  experiment → use `decision`.

### Section-by-section

#### 가설 / Hypothesis `[required]`

**Strong.** Falsifiable claim with a measurable threshold.
> "batch size 256으로 올리면 lr=3e-4 써도 val_loss divergence 없을 것 (3 시드 중 0개 NaN)."

**Weak.** A goal, not a claim.
> "성능을 올리고 싶다."

**Anti-pattern: hypothesis = result.** Researchers sometimes write the
result in the hypothesis box ("bs=256, lr=3e-4 → 1.24"). Push back:
"가설은 결과 *전*에 있었던 추측이야. '~ 일 것이다' 형태로."

**Pacing.** This is the most fluid section. Do not over-prompt; one
short researcher sentence is fine.

#### 셋업 / Setup `[required]`

**Strong.** Diff from the prior run, with prior run referenced by
exp-ID. Hyperparameters listed compactly.
> "exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일."

**Weak.** Full hyperparameter dump unrelated to this run's question.

**Anti-pattern: setup contains result.** "Set bs=256 because lr=3e-4
needed it" — that is rationale, not setup. Push to 가설 or out.

**Auto-link goldmine.** Watch for exp-ID patterns
(`exp-YYYY-MM-DD-*`) — almost always prior-run references; extract
to `find-pages --kind experiments`.

#### 결과 / Results `[required]`

**Strong.** Numbers, with units, and what they were measured on.
> "3 시드 중 2개는 val_loss 1.24 (test set). 1개는 step 340에서 NaN."

**Weak.** Vague ("좋아짐", "improved", "slower"), no comparison
baseline.

**Anti-pattern: causal language.** "lr이 너무 높아서 NaN" — that is
the most common P8 trap. See `p8-detection.md` §3 (the experiment
template's 결과 row is high-risk for this exact reason).

**Special case: failed runs.** Include the failure mode (NaN, OOM,
crashed at step X) — it is observation, not negative finding. Move
*causes* of the failure to 실패 양상 (with same P8 discipline).

#### 관찰 / Observations `[required]`

**Strong.** Direct readouts from logs / plots, with line numbers /
step numbers / file names.
> "NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐 (logs/run-0312/grad_norm.csv)."

**Weak.** Adjective-laden vague claims ("learning seemed unstable",
"results looked weird").

**Anti-pattern: Observations = causes.** This section attracts P8
violations more than any other in any template. See
`p8-detection.md` §3 (highest risk).

#### 실패 양상 / Failure modes `[optional]`

**Strong.** "What" only, not "why":
> "step 340에서 grad norm inf, NaN propagation across all params, 다음 step에서 forward NaN."

**Weak.** Mixing "what" with "why":
> "lr이 너무 높아서 grad explosion 후 NaN 발생."

If the researcher wants to record their causal hypothesis, push to
`questions.md` (P8 route c). The failure-mode section stays observational.

**When to skip.** No failure occurred → skip cleanly.

#### 관련 코드 / Related code `[required]`

**Strong.** Identifier / file lists. Short.
> "trainer.py 메인 루프, train_one_epoch."

**Weak.** Prose narrative. ("우리는 trainer 모듈에서 train_one_epoch을 호출하는데...").

**Auto-link goldmine.** Aggressive extraction here — researchers put
identifiers in this section *for* the auto-link pass.

#### 다음 단계 / Next steps `[optional]`

**Strong.** Specific, scoped plans:
> "exp-2026-04-24: bs=256 + lr=1e-4 (lower lr 비교) + grad clip 1.0."

**Weak.** Vague aspirations ("improve stability").

**Anti-pattern: too many next steps.** If there are 4+ planned
follow-ups, push the researcher to log each as its own entry later
rather than burying them all here.

---

## 2. `paper` template

**When to use.** Researcher read a paper worth filing. The wiki entry
captures *the researcher's reading*, not a generic summary — i.e., it
captures what was relevant to *this researcher's questions*.

**When NOT to use.**
- The paper is just being cited in passing without a real reading →
  add to `refs.papers` of an existing entry, don't make a paper page.
- The "paper" is actually a blog post / talk / tutorial → consider
  `free` instead, or extend with a custom template.
- The researcher hasn't actually read it → see `refusal-patterns.md`
  §2 (LLM-only entries).

### Section authoring patterns

The KO/EN paper templates ship with a section structure roughly:
- Citation / metadata `[required]`
- Key claim / main contribution `[required]`
- Method summary `[required]`
- Limitations / criticism `[optional]`
- Implications / connections `[optional]`
- Open questions `[optional]`

Walking each:

**Citation.** Strong = author–year + venue. Weak = "the attention paper".

**Key claim.** Quote the paper's abstract sentence verbatim, OR
paraphrase tightly. The discipline: this section reports what *the
paper* claims, not what the *reader* concludes. P8 risk: medium.

**Method summary.** Strong = the paper's stated mechanism in 1–2
paragraphs. Watch for the researcher *interpreting* the method
("they're really doing X by Y") — fine if grounded in the paper's
own text, P8 risk if extrapolating.

**Limitations / criticism.** Two flavors:
- Limitations stated by the paper — quote/paraphrase, attribute to
  the paper.
- Limitations the *researcher* observed — these are interpretation;
  fine to record but should be marked as such ("내 관점:" / "I'd add:").

**Implications / connections.** Highest P8 risk in the paper template.
See `p8-detection.md` §3 (the row "Implications / connections —
高 risk"). Push back hard if the implication is "therefore X" without
the paper itself saying so.

**Open questions.** Encourage these — they convert nicely to
`questions.md` follow-up entries later.

### Auto-link patterns

- `papers` auto-link **disabled** by default (the paper template's
  `_template.auto_link.papers.enabled: false`) — paper-to-paper refs
  in prose are too prone to false matches. Researcher should add
  `refs.papers` manually for cited works.
- `concepts` auto-link enabled — paper readings often introduce or
  reference concepts ("rotary embedding", "flash attention").
- `code` auto-link usually disabled — paper readings rarely reference
  the researcher's own code.
- `experiments` auto-link enabled — papers sometimes inspire follow-up
  experiments referenced by exp-ID.

---

## 3. `decision` template

**When to use.** A non-trivial design or implementation choice was
made that future-you (or a collaborator) will want to find the
rationale for. Examples:
- "Switched from SGD to AdamW after lr-warmup investigation."
- "Adopted Postgres for session storage."
- "Decided to delete the deprecated `legacy_attn` module."

**When NOT to use.**
- A trivial choice ("renamed `f` to `forward`") — git commit message
  is enough.
- A choice that hasn't been made yet, only considered → use `free`
  for the deliberation note.
- A finding from an experiment → use `experiment`; the decision
  template is for the *choice*, not the *evidence*.

### Section authoring patterns

The decision template typically asks:
- Problem `[required]`
- Options considered `[optional]` (often skipped if obvious)
- Chosen approach `[required]`
- Rationale `[required]`
- Trade-offs `[optional]`
- Reversal cost `[optional]`

**Problem.** Concrete need, not abstract preference. Strong =
"Redis가 single-node failure 시 30분 다운"; weak = "want better
storage".

**Options considered.** Two patterns:
- Short list with one-sentence reasons for rejection — fine.
- Long deliberation with intent attribution to the rejected
  options' authors → P8 risk; just say "considered X, ruled out
  because Y" not "they probably designed X for Z reason".

**Chosen approach.** Description, no justification (justification
goes in Rationale).

**Rationale.** **High P8 risk.** Watch for forward-looking causal
claims ("this *will* prevent the issue"). Push to grounded
predictions: "X 솔루션은 Y constraint 를 만족 (논문/measurement reference)".

**Trade-offs.** Strong = symmetric ("gain X, lose Y, net positive
because Z"). Weak = "no real trade-offs" (always suspect — push back).

**Reversal cost.** Encourage this — it makes implicit risk explicit.

### Auto-link patterns

- `code` enabled — decisions often touch named modules.
- `concepts` enabled — decisions often invoke named patterns
  ("adopted CQRS").
- `papers` enabled — decisions sometimes cite published prior art.
- `experiments` enabled — decisions sometimes cite specific runs as
  evidence.

`link_bidirectional: true` for all enabled kinds is the typical
default — decisions are high-value link anchors.

---

## 4. `free` template

**When to use.** Anything that doesn't fit the other three:
- Random observations ("noticed our CI is 30% slower this week")
- Bug reports ("seeing flaky test on darwin only")
- Half-formed ideas worth not losing
- Quick references / bookmarks

**When NOT to use.**
- A real experiment / paper / decision is being shoehorned to skip
  the structured template — push back.

### Section authoring patterns

The free template is *minimal* — usually just:
- Notes `[required]` (the body)
- (sometimes) Tags `[optional]`

This is by design. Free-form should be **fast**: the researcher
should be in and out in 30 seconds.

**Don't impose structure.** If the researcher's note is one sentence,
that's a one-sentence entry. Don't ask for a follow-up paragraph.

**P8 still applies, but with lower friction.** Hedge language is more
acceptable in free-form ("seems like X is broken") because the entire
template is implicit "this is informal". Still reject *causal claims
without evidence* and *intent attribution* — those are damaging in any
context.

**No auto-link.** Free-form has minimal auto-link by default. The
researcher can add refs manually if they want.

---

## 5. Cross-template guidance

### When the researcher picks the wrong template

Example: researcher says `--type free` for what is clearly an
experiment result. Push back gently:

> 이거 실험 결과 같은데 — `--type experiment` 로 가면 가설/셋업/결과
> 가 강제되어서 나중에 wiki-recall 로 찾을 때 더 잘 잡혀. free 가
> 좋은 이유가 있어?

Two acceptable responses:
- "그래, experiment 로" → restart with the right type.
- "그냥 free 로 짧게 메모만 하고 끝낼 거야" → respect; free is
  legitimate for "I want to record this without ceremony".

### Custom templates (per `log_templates:` config)

If the workspace's `research-wiki.config.yaml` overrides
`log_templates.experiment: my_custom`, then `templates/my_custom.md`
ships in place of the default. The mechanical surface
(section parsing, required-field validation, auto-link extraction)
works the same — but the section titles, required-flag distribution,
and `_template.auto_link` rules will differ.

In that case, **trust the inspect JSON** — don't apply this guide's
"strong/weak" examples to a custom template's sections. Use the
italic guides as the authoritative source of what the researcher
intended each section to capture.

### When to suggest splitting an entry

If the researcher's content for one section is large enough to be its
own entry, suggest the split:

> 이 "관찰" 답변이 길어서 거의 두 발견 — grad norm pattern + checkpoint
> overflow. 두 번째를 별도 free 엔트리로 분리할까?

The researcher is the gate; if they say "no, keep it together", do so.

---

**The shorthand:** the template structure encodes what the principal
designer (the researcher who set up this workspace) thought was
worth recording for each kind of activity. Trust the structure;
push back when the answer doesn't match the section's intent.
