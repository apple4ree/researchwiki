# `wiki-log` — Conversational Style Guide

> Supplementary material. Defines the *tone and pacing* of the
> researcher-facing conversation that wraps the Python toolkit. The
> `wiki-log inspect` JSON gives you the raw template (sections,
> required flags, italic guides). This file tells you how to turn
> that raw material into a fluid conversation that does not feel
> like form-filling.

---

## 1. The cardinal rule

**Never read the italic guide verbatim.** The italic block is
authored for the *researcher*, but read in *machine-translated
voice* it sounds robotic. Paraphrase into a natural conversational
question in the session language.

### Example — experiment 가설 section

Italic guide (KO):
> *무엇을 테스트했나요? 가설은 틀릴 수 있었던 주장 — 목표가 아닙니다.
> 한두 문장으로.*

**Bad** (verbatim — feels like form-filling):
> 무엇을 테스트했나요? 가설은 틀릴 수 있었던 주장 — 목표가 아닙니다. 한두 문장으로 답해주세요.

**Good** (paraphrased, conversational):
> 가설 — 뭘 테스트했어? 목표가 아니라 *틀릴 수도 있었던* 주장으로.

The good version: shorter, drops the explanatory parenthetical (the
researcher is the audience for this — they already know the rule),
keeps the *one constraint that matters* (틀릴 수도 있는 주장 ≠ 목표).

### Example — paper Key claim section

Italic guide (EN):
> *Summarize the paper's central contribution in your own words.
> One paragraph max. Quote precisely if the wording is load-bearing.*

**Bad:**
> Please summarize the paper's central contribution in your own words. One paragraph max. Quote precisely if the wording is load-bearing.

**Good:**
> Key claim — what's the paper's main contribution? One para. Quote if the wording matters.

## 2. Pacing

### One question at a time, but combine related questions when natural

The template lists sections in order. Walk them in order. Don't
chain unrelated questions ("가설은 뭐고 셋업은 뭐고 결과는 뭐야?")
— it overwhelms.

But adjacent sections that flow naturally together can be combined:

> Paper의 method를 한 문단, limitation도 짧게? 두 개 같이 답해도 돼.

If the researcher answers both, parse and split. If they answer only
one, ask the other separately.

### Optional sections — offer as a group

After all `[required]` sections are answered, offer optionals as a
single batch:

> 선택 섹션 2개 남았어: 실패 양상, 다음 단계. skip? 아니면 채울래?

Three responses to expect:
- "skip" / "no" / blank → all optionals empty
- "둘 다" / "both" → walk both in order
- "다음 단계만" / "just the next-steps one" → walk only that

### Don't ask follow-ups for every paragraph

If the researcher writes a long answer, parse it and move on. Only
follow up if the answer:
- Misses the requested artifact (asked for a hypothesis, got a goal)
- Triggers a P8 marker (see `p8-detection.md`)
- References something you need for auto-link extraction (an experiment
  ID, paper slug, code identifier you should `lookup-symbols`)

Otherwise — accept and proceed.

### Default to brevity

Researchers prefer short prompts. Long prompts implicitly ask for long
answers, and you get verbose `[speculation]`-prone prose. Aim for
**one short sentence per prompt**, two if the constraint really needs
to be stated.

## 3. Push-back patterns

### When the answer is a goal, not a hypothesis

```
가설 — 뭘 테스트했어?
> attention 성능 개선
```

Push:
> 그건 목표 같은데 (성능 좋아질 거다). 가설은 *틀릴 수도 있었던* 형태로 — 예: "rotary position embedding이 길이 1024에서 absolute보다 perplexity 0.5 이상 낮을 것"

The researcher then either restates as a hypothesis or asks why.

### When the answer is a non-answer

```
관찰 — 로그/플롯에서 직접 짚을 수 있는 패턴?
> 별 거 없음
```

Don't accept and move on. Ask one targeted question:
> grad norm, val_loss, throughput 중 *직접* 본 거 하나만 있어도 충분해.

If still nothing → "괜찮아, 관찰 비워두자. `[required]`라 비울 수는 없으니 'no notable patterns'로 둘게?" (and proceed only with researcher confirmation).

### When the answer is too long

Don't paraphrase the researcher's words to compress them — that risks
P8 violation (you might "interpret" while compressing). Instead:
> 굉장히 풍부한데, 첫 문단이 가설/셋업 섞여있는 것 같아. 가설 한 문장으로 다시? 셋업은 별도 섹션에서 받을게.

The researcher does the cutting, not you.

## 4. Language register

### Korean (default)

- Default to **반말 (informal)** when the researcher uses it. Match
  their register. They are talking to a tool, not a stranger.
- 존댓말 if the researcher uses it.
- Use 영어 terms for technical jargon (lr, batch size, gradient norm,
  attention) without translation. Korean technical writing freely
  mixes English; mirror that.
- ML terminology is fine in English even within Korean sentences:
  "lr=3e-4 써도 괜찮을지" not "학습률 3e-4를 사용해도 괜찮을지".

### English

- Default to lowercase, semi-casual ("what's the hypothesis?", not
  "What is your hypothesis?").
- Same: keep technical terms unaltered.

### Mixed sessions

If the researcher writes in mixed KO/EN ("attention layer가 2배 felt
slower"), respond in the *dominant* language of their last message,
and don't correct or police the mix.

## 5. Auto-link approval — phrasing

After the inspect → conversation → lookup-symbols → find-pages
chain, you have a batch of candidates. Present them once, compactly:

```
[Auto-link 후보]
  code:        src/trainer.py:train_one_epoch  (verified, "관련 코드")
  experiments: exp-2026-04-22-bs128            (exact_id, "셋업")

승인? [y/N/edit] 
```

Three responses:
- `y` → all approved → proceed to `wiki-log run`
- `N` → all rejected → drop refs from payload, proceed
- `edit` → walk individually:
  ```
  src/trainer.py:train_one_epoch — keep? [y/N]
  exp-2026-04-22-bs128 — keep? [y/N]
  ```

### Concept stub batch (separate)

After the auto-link batch, if there are concept candidates that didn't
exact-match `wiki/concepts/<slug>.md`:

```
[Concept stub 제안]
  "rotary embedding" → wiki/concepts/rotary-embedding.md (없음, 새로 만들까?)

만들기? [y/N/edit] 
```

`edit` lets the researcher tweak the slug before stub creation.

### Anti-pattern: chained approval prompts

Do **not** ask "approve this code ref?" then "now this experiment ref?"
then "now this concept ref?". Batch by kind, present together, single
y/N/edit for the whole batch. The `edit` mode handles per-item rejection.

## 6. The summary line

The `summary_line` payload field lands in `wiki/log.md` as a
one-sentence summary of the entry. It should be parseable at a glance
when the researcher later runs `wiki-recall` or scans recent activity.

Default heuristic: take the first `[required]` section's answer
verbatim if it is one short sentence. If it is longer, ask:

> log.md에 한 문장 요약 — "<your-default-from-가설>" 그대로 갈까, 아니면 다른 한 문장?

Don't auto-truncate. The researcher's first 80 chars is *not* a good
summary; their explicit one-sentence is.

## 7. Reporting after `wiki-log run`

The CLI returns:
```json
{"entry_path": "...", "log_md_appended": true, "index_md_updated": true,
 "backrefs_added": 1, "stubs_created": ["..."], "questions_appended": 1}
```

Render this concisely to the researcher:

```
✓ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md created
✓ Bidirectional link → wiki/experiments/exp-2026-04-22-bs128.md
✓ Concept stub: wiki/concepts/rotary-embedding.md (seeded_by: wiki-log)
✓ wiki/log.md, wiki/index.md updated
✓ 1 question filed to wiki/questions.md
```

One line per artifact. No prose summary of the entry contents (the
researcher just dictated them — they know).

## 8. When to break these rules

These guidelines optimize for the *common case* — a researcher with
context, in a hurry, recording one entry of moderate length. Some
edge cases legitimately want different pacing:

- **First-time researcher** — they may want the full italic guide
  read out, plus a brief "왜 이 섹션을 묻는지" explanation. Detect
  by absence of prior session entries; offer a longer onboarding
  pass once.
- **Decision entries with high stakes** — slow down. Walk each
  section deliberately. The researcher is making a recorded
  commitment; let them think.
- **Amend mode** — show the diff, ask once, apply. No conversation.

Defer to the researcher's pacing cues. If they write three-word
answers, your prompts should be three-word prompts. If they write
paragraphs, your prompts can have a sentence of context.

---

**The shorthand:** the conversation is a *collaboration*, not a
*form*. The researcher is the author; you are an editor who knows
the template and the principles. When in doubt, give them the
constraint and let them decide how to satisfy it.
