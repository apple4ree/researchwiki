# `wiki-log` — P8 Speculation Detection

> Supplementary material. The Python core (`src/researchwiki/log.py`)
> does **not** detect speculation; that is the LLM's responsibility
> during the conversational fill-in. This file is the runbook.
>
> P8 — *Analysis yes, speculation no* — is the most damaging principle
> to violate, because plausible-but-wrong claims slow-poison the
> knowledge base for weeks before anyone catches them. Err on the side
> of asking the researcher to choose a route over silently accepting
> a tagged claim.

---

## 1. The three-route enforcement flow

When you detect a marker (see §2 / §3), you do **not** silently rewrite
the answer and you do **not** silently tag it. You name the issue and
offer the researcher the same three routes every time:

```
(a) 관찰로 다시 쓰기 — 직접 본 현상만. 인과/추정은 빼고.
(b) 추측으로 태그하고 유지 — `[speculation] <원문>`
    (wiki-lint speculation-ratio 임계치에 카운트됨)
(c) wiki/questions.md 로 분리 — 미해결 질문으로 남기고
    원래 섹션은 직접 관찰만
```

The route is **always the researcher's choice.** If they refuse all
three routes, abort the entry — do not write a partial entry to disk.

Encode the chosen route into the payload before calling `wiki-log run`:

| Route | Payload effect |
|---|---|
| (a) | The researcher's rewritten answer goes into `section_answers[<section>]`. No special tagging. |
| (b) | The original answer with `[speculation]` prefix goes into `section_answers[<section>]`. No `questions` entry. |
| (c) | The section answer is replaced with the *direct observation only*. The speculative claim becomes one entry in the `questions` array (with `question` and `context`). |

**The CLI does not validate this — you are the gate.** A `[speculation]`
tag in a section answer is honored verbatim. A `question` entry is
appended to `wiki/questions.md` as written. Garbage in → garbage
written.

## 2. Hedge-language markers

These constructions strongly suggest speculation. They are *signals
to ask*, not deterministic verdicts — context decides.

### Korean

| Marker | Example | When it is fine |
|---|---|---|
| `~것 같다` | "lr이 너무 높은 것 같다" | Subjective uncertainty as observation: "처음 봤을 때는 typo인 것 같았다" — fine if framed as a *first impression* the researcher then verified or chose to record as ambiguity |
| `~듯하다` | "수렴이 늦은 듯하다" | Same as above |
| `~보인다` | "수렴이 안정적으로 보인다" | If the surrounding sentence quantifies what was *observed* (val_loss curve flatness, gradient norm range), the verb is harmless |
| `~추정된다`, `~짐작된다` | "병목은 데이터 로더로 추정된다" | Almost always a P8 violation — "추정된다" is the literal Korean for *speculated*. Push to (b) or (c). |
| `~때문에`, `~덕분에` (without log evidence) | "lr이 높아서 NaN이 발생했다" | Fine if the same paragraph cites the controlled comparison or log line that supports the causal arrow |
| `~려고 했다`, `~의도한 것이다`, `~위해 ... 한 것` (intent attribution) | "이 함수는 캐시 무효화를 위해 만들어진 것이다" | Only if the researcher is the one who *wrote* the function being described, OR the comment block / commit message is quoted verbatim |
| `~로 보아`, `~을 보면` | "X를 보면 Y가 원인이다" | Often hides causal claims in inference language; ask for the X→Y mechanism |

### English

| Marker | Example | When it is fine |
|---|---|---|
| `seems`, `appears`, `looks like` | "the loss seems to plateau" | If quantified: "the loss appears to plateau (val_loss change < 0.5% over 50 steps)" — the marker is then redundant but harmless |
| `probably`, `likely`, `presumably`, `apparently` | "the spike is probably the dataloader" | Almost always P8 unless followed by *and the evidence is X* |
| `suggests that`, `implies` | "the gradient norm suggests overflow" | Same as above; "suggests" = the researcher inferring beyond direct observation |
| `due to`, `because of`, `caused by` (no evidence) | "the divergence was caused by the higher lr" | Fine if a controlled comparison or log line is cited adjacent |
| `was meant to`, `was designed to`, `intended` | "this method was meant to short-circuit caching" | Same rule as Korean intent attribution |
| `should`, `must`, `can only` (about behavior) | "the cache should hit on the second call" | Fine when describing a contract / specification; speculative when describing what *did* happen |

### Counter-examples (do **not** flag)

These look hedge-like but are not P8 violations:

- **Future tense / planning** — "다음 런에서는 lr=1e-4 시도할 것" / "We will try lr=1e-4 next" → that is `다음 단계` content, not an observation.
- **Reporting a hypothesis as a hypothesis** — the entire `가설` section is *by design* a falsifiable claim. Hedge language there is fine; hedges in `결과` or `관찰` are the issue.
- **Quoting a paper / commit message / colleague** — quoted speculation is fact-of-the-quote, not your own claim. Preserve the quotation marks.
- **Quantified subjective observation** — "the curve looks unusually noisy (variance 3× the baseline)" — the parenthetical grounds the claim.
- **Negative findings** — "데이터 변화가 결과에 영향을 주지 않았음" with backing numbers is observation, not speculation.

## 3. Section-by-section risk map

Different template sections attract different speculation patterns. Use
this table to know where to look hardest.

### `experiment` template

| Section | Risk | Watch for |
|---|---|---|
| 가설 | low | Hedges are fine here — the section is *for* hypotheses |
| 셋업 | low | Mostly factual; flag only if a setup choice is justified by intent attribution ("이렇게 한 이유는 ... 일 것이라 생각해서") |
| 결과 | **high** | Direct measurements only. Any "because" or "due to" without evidence is route (a)/(c) |
| 관찰 | **highest** | This is the section P8 was written for. Causal claims, intent claims, and unquantified hedges are all suspect |
| 실패 양상 | high | "왜" 가 끼면 곧장 P8. "어떤" 만 적게 |
| 관련 코드 | low | Mostly identifier listing |
| 다음 단계 | low | Future-tense plans are fine |

### `paper` template

| Section | Risk | Watch for |
|---|---|---|
| Citation / metadata | low | — |
| Key claim / main contribution | medium | Should be the *paper's* claim, not the reader's interpretation; quotation or close paraphrase preferred |
| Method summary | medium | If the paper's method is summarized in researcher's words, ensure no extension beyond what is in the paper |
| Limitations / criticism | **high** | Anything not stated by the paper itself is the researcher's own analysis — fine if grounded, P8 if speculative |
| Implications / connections | **high** | "This implies that ..." beyond what the paper itself says is the most common P8 violation in paper entries |

### `decision` template

| Section | Risk | Watch for |
|---|---|---|
| Problem | low | Statement of need |
| Options considered | low–medium | Sometimes researchers attribute intent to the rejected option's authors — flag those |
| Chosen approach | low | Description of the chosen path |
| Rationale | **high** | "We chose X because Y *will* happen" — flag forward-looking causal claims unless backed by data |
| Trade-offs | medium | Trade-off claims should be grounded in measurements or explicit constraints, not "feels right" |

### `free` template

No required structure → P8 risk distributed across the entire entry.
Apply the markers in §2 line-by-line.

## 4. Common P8 traps

### Trap 1 — explanation creep in the 결과 section

```
결과: 3시드 중 2개는 val_loss 1.24로 수렴.
1개는 step 340에서 NaN.  ← OK (observation)

높은 lr 때문에 발생한 NaN으로 보임. ← NOT OK (causal + hedge)
```

Push: "그 인과를 뒷받침하는 로그/플롯 있어? 없으면 (a) 직접 관찰만 두고, 원인 가설은 questions.md (c)."

### Trap 2 — paper "implications" beyond the paper

```
Key claim: 이 논문은 attention layer가 N^2 비용임을 측정.  ← OK
Implications: 따라서 long-context 모델은 sparse attention이 필수다.  ← NOT OK
```

Even if the implication is *true*, the paper may not have said it.
Route (a): "논문이 직접 명시한 implication만." Route (c): the
"Therefore..." becomes a question for `wiki/questions.md`.

### Trap 3 — intent attribution in code-related sections

```
관련 코드: train_one_epoch 함수.
이 함수는 메모리를 줄이려고 chunked forward를 쓴다. ← suspect
```

Verify: is this stated in a comment / commit / docstring? If not,
push the claim to `wiki/questions.md` as "왜 chunked forward인가?"
or rewrite as observation: "함수는 chunked forward 패턴을 사용한다."

### Trap 4 — premature causal language in paired-comparison results

The researcher might write "bs=256 because lr=3e-4 is too high" when
they actually only ran the one configuration. Without the comparison
run (lr=1e-4 at bs=256, or lr=3e-4 at bs=128), the causal claim is
speculation — even if it later turns out to be correct.

This is the trap from `examples.md` Example 2. The route-c split is
particularly clean for this case: the *fact* (NaN at step 340) lives in
the entry; the *unverified cause* lives in questions.md as
"Why does (bs=256, lr=3e-4) NaN?".

## 5. The "implicit speculation" trap

Sometimes there is no hedge marker, no causal verb, no intent verb —
but the claim is still ungrounded. Examples:

- "The cache hit rate improved." (Compared to what? On which workload?)
- "Memory usage is fine." (Threshold?)
- "Convergence is faster." (vs. baseline?)

These are quietly speculative because they assert without grounding.
The fix is rarely route (b) or (c) — usually push back to the
researcher: "기준이 뭐야? 어떤 메트릭으로?" and let them either
ground the claim or downgrade it.

## 6. When to NOT enforce P8

- **Quoted material.** The quote belongs to whoever said it; you are
  reporting that they said it.
- **Self-reported subjective state.** "I felt X" / "이게 더 직관적이었음"
  is the researcher's own subjective state, recorded as such. Not a
  claim about the world.
- **Explicit `[speculation]` tag.** If the researcher has already
  tagged it, your job is done — they made an informed choice.
- **The `실패 양상` section's "what" content.** Describing what failed
  is not speculative even if the cause is unknown. The cause guesses
  are the issue.

## 7. Edge cases worth knowing

### "방향이 맞다" / "제대로 동작한다"

These are sometimes observations ("test passed") and sometimes value
judgments ("this design is right"). If the surrounding context
quantifies success criteria, they are observations. If they appear in
isolation in a `Rationale` or `Implications` section, they are
speculation.

### Conditional / hypothetical phrasing

"만약 X였다면 Y였을 것" — these are explicitly counterfactual and
fine to record, but should usually live in `다음 단계` or `Implications`,
not `결과` / `관찰`.

### Comparison to "common knowledge"

"이 결과는 일반적으로 알려진 trend와 일치한다" → ask which trend, citing
which paper. Either ground or downgrade.

---

**The shorthand:** if removing the sentence would not lose any
*observation*, only an *interpretation*, then it is interpretation,
and interpretation belongs to the researcher — not silently to you.
