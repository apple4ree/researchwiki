# `wiki-log` — Worked Examples

> Supplementary material for `wiki-log`. Not loaded at LLM runtime — read for orientation, design discussion, or when debugging unexpected behavior. Each example shows full conversational flow, file diffs, and reasoning.

---

## Example 1 — Happy path: recording an experiment (full end-to-end)

**Setup.** Target repo `/home/researcher/attention-study/`, initialized with `--language ko`. Current git HEAD: `5a3f9e2`. Prior experiment file exists at `wiki/experiments/exp-2026-04-22-bs128.md`. `index/signatures.json` is current (freshly produced by `wiki-sync` this morning).

**Invocation.**

```
> wiki-log --type experiment --title lr-sweep-bs256
```

**Template load + placeholder fill.**

```
wiki-log: Loading templates/experiment.md (ko).

Auto-filled placeholders:
  {{DATE}}        = 2026-04-23
  {{SESSION_ID}}  = 2026-04-23-s3
  {{GIT_REF}}     = 5a3f9e2
  {{TITLE}}       = lr-sweep-bs256

필수 섹션 5개 (가설, 셋업, 결과, 관찰, 관련 코드). 답은 자연어로.
```

**Conversation.**

```
**가설 — 뭘 테스트했어? 목표가 아니라 "틀릴 수도 있었던 주장".**
> batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것

**셋업 — 이전 런과 뭐가 달랐어? 기존 실험을 ID로 참조하면 자동 링크 걸어줄게.**
> exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일

**결과 — 숫자가 뭘 보여줬어? 직접 관찰만.**
> 3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.

**관찰 — 로그/플롯에서 직접 짚을 수 있는 패턴?**
> NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐

**관련 코드 — 어떤 함수·파일이 관련됐어? 이름만 적으면 돼.**
> trainer.py 메인 루프, 특히 train_one_epoch

선택 섹션 2개 남았어: 실패 양상, 다음 단계. skip? 아니면 채울래?
> skip
```

**Auto-link pass.** Each scan obeys the experiment template's `_template.auto_link`.

```
scan: code (strategy: identifier_token)
  tokens considered from body:
    trainer.py, train_one_epoch, bs, lr, grad, norm, val_loss, ...
  index/signatures.json lookup:
    train_one_epoch → src/trainer.py:23  (unique match → verified)
    trainer.py      → module file         (verified)
  rejected (ambiguous or not in index): bs, lr, grad, norm, val_loss

scan: experiments (strategy: exact_id)
  `exp-YYYY-MM-DD-*` pattern matches found in "셋업":
    exp-2026-04-22-bs128 → wiki/experiments/exp-2026-04-22-bs128.md ✓
  link_bidirectional: true → back-ref will be written

scan: concepts (strategy: exact_slug)
  no matches under wiki/concepts/ for body tokens

scan: papers — disabled for experiment template
```

**Approval.**

```
[Auto-link candidates]
  code:         src/trainer.py:train_one_epoch   (verified,   from "관련 코드")
  experiments:  exp-2026-04-22-bs128              (exact_id,    from "셋업")

Approve all? [y/N/edit] y
```

**Write phase.** Four file changes occur atomically.

**(1)** New entry `wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md`:

```markdown
---
schema_version: 1
type: experiment
created: 2026-04-23
updated: 2026-04-23
tags: []
refs:
  code:
    - path: src/trainer.py
      symbol: train_one_epoch
      confidence: verified
  papers: []
  concepts: []
  experiments:
    - exp-2026-04-22-bs128
authored_by: hybrid
source_sessions: [2026-04-23-s3]
git_ref: 5a3f9e2
run_duration: null
seed: null
---

# lr-sweep-bs256

## 가설
batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것

## 셋업
exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일

## 결과
3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.

## 관찰
NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐

## 관련 코드
trainer.py 메인 루프, 특히 train_one_epoch
```

Note: the `_template:` block from the source template is stripped. Section headers no longer carry `[required]` flags. HTML comments (`<!-- example: ... -->`) are dropped.

**(2)** Append to `wiki/log.md`:

```
## [2026-04-23 14:37] log | experiment | lr-sweep-bs256

batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것

→ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md
```

**(3)** Update `wiki/index.md`, under the "Experiments" section (diff):

```diff
 ## Experiments
 - [exp-2026-04-21-baseline](experiments/exp-2026-04-21-baseline.md)
 - [exp-2026-04-22-bs128](experiments/exp-2026-04-22-bs128.md)
+- [exp-2026-04-23-lr-sweep-bs256](experiments/exp-2026-04-23-lr-sweep-bs256.md)
```

**(4)** Bidirectional back-ref on `wiki/experiments/exp-2026-04-22-bs128.md` **frontmatter only** (body untouched, P3):

```diff
 refs:
   code:
     - path: src/trainer.py
       symbol: train_one_epoch
       confidence: verified
   papers: []
   concepts: []
-  experiments: []
+  experiments:
+    - exp-2026-04-23-lr-sweep-bs256
```

**Final report.**

```
✓ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md created (34 lines)
✓ Bidirectional link added to wiki/experiments/exp-2026-04-22-bs128.md frontmatter
✓ wiki/log.md appended
✓ wiki/index.md updated
```

---

## Example 2 — Ambiguity: speculative language triggers P8 enforcement

Same invocation as Example 1, but the researcher's **관찰** answer crosses into cause attribution. wiki-log pauses and invokes the P8 three-route flow.

**The speculative answer.**

```
**관찰 — 로그/플롯에서 직접 짚을 수 있는 패턴?**
> NaN은 lr이 너무 높아서 발생했을 것이다
```

**Diagnosis.** wiki-log identifies two markers in a single sentence:

- "너무 높아서 발생했을" — causal claim (X → Y) without supporting log evidence cited.
- "것이다" — hedge construction; claim asserted without grounding.

**Intervention.**

```
wiki-log: 그 문장은 원인 귀인이야. 로그에 "lr이 원인"이라는 증거가 있어?
(예: 같은 bs=256에서 lr만 낮춘 런의 안정성 비교, 또는 grad norm 궤적이
lr에 의존한다는 직접 근거)

증거가 있으면 관찰을 그 증거로 구체화해줘.
증거가 없으면 세 가지 선택지:

  (a) 관찰로 다시 쓰기 — 직접 본 현상만. 인과는 빼고.
  (b) 추측으로 태그하고 유지 — `[speculation] NaN은 lr이 너무 높아서...`
      wiki-lint의 30% 임계치에 카운트됨.
  (c) `wiki/questions.md`로 분리 — "왜 bs=256, lr=3e-4 조합에서 NaN?"을
      미해결 질문으로 남기고, 관찰 섹션은 직접 본 현상만.

어느 쪽?
```

**Route (a) — researcher rewrites as observation.**

```
> (a) 다시 쓸게. grad norm이 step 300부터 단조 증가했고 step 340에서 inf로 튐.
```

The rewritten answer replaces the speculative one. Auto-link and write phases proceed identically to Example 1. No `[speculation]` tag is added; `wiki/questions.md` is not touched.

**Route (b) — researcher keeps the guess but tags it.** The 관찰 section in the final entry reads:

```
## 관찰
[speculation] NaN은 lr이 너무 높아서 발생했을 것이다
```

The `[speculation]` tag is preserved in the written entry. When `wiki-lint` runs its speculation-ratio check, this sentence counts toward the unsupported-claims total. At the default 30% threshold, one tagged claim in a 5-section entry (20% of sentences) stays below — but repeated (b) choices across the wiki accumulate.

**Route (c) — researcher moves the guess to questions.md.** Two file effects:

- `wiki/questions.md` gets a new append-only block:
  ```
  ## [2026-04-23 14:35] from wiki-log (exp-2026-04-23-lr-sweep-bs256)

  **Question:** 왜 bs=256, lr=3e-4 조합에서 NaN이 발생했는가?

  **Context:** exp-2026-04-23-lr-sweep-bs256의 Observations에서 분리.
  Grad norm이 step 300부터 단조 증가한 사실은 기록됨. 원인 귀속은 로그로
  확정되지 않음.

  **Status:** open
  ```
- The experiment entry's **관찰** section contains only the direct observation
  (the grad-norm trajectory), no cause claim.

In all three routes, **wiki-log never silently tags, rewrites, or discards** the researcher's claim. The route is always the researcher's choice.

---

## Example 3 — Refusal: researcher asks wiki-log to edit an existing page body

The researcher wants to fix an inaccuracy in `wiki/concepts/auth-flow.md`. wiki-log cannot do this (P3 — propose, do not mutate interpretation).

**Invocation.**

```
> wiki-log auth-flow concept 페이지의 "session storage uses Redis" 부분
  Postgres로 바꿔줘
```

**Refusal with concrete alternatives.**

```
wiki-log: concept 페이지의 body 수정은 내 역할이 아니야. wiki-log는 새 엔트리를
만들고, 기존 페이지의 frontmatter refs만 업데이트해. 해석 계층(wiki/ body)은
조용히 다시 쓰지 않아 — CLAUDE.md §3 디렉토리 컨트랙트 + 원칙 P3.

이 상황에 맞는 세 가지 경로:

  (a) 에디터에서 직접 수정.
        $ $EDITOR wiki/concepts/auth-flow.md
      수정 후 frontmatter `updated:` 날짜도 오늘로 바꿔줘.
      이건 연구자의 의식적 편집이라 P3에 안 걸림.

  (b) 새 decision 엔트리로 변경 이유를 남기기.
        > wiki-log --type decision --title session-storage-postgres-migration
      decision 템플릿이 "문제", "선택한 접근", "근거" 등을 묻고, `scope:`
      frontmatter에 auth-flow concept을 넣으면 auto-link이 back-ref까지
      걸어줘. auth-flow body는 안 바뀌지만, decision이 그 변경의 이유를
      명시적으로 남김 → wiki-lint가 나중에 concept과 decision 사이의
      discrepancy를 감지하고 questions.md에 리뷰 요청을 남길 수 있음.

  (c) concept 페이지가 "Redis"라는 stale code ref를 갖고 있으면, `wiki-sync`
      가 stale 플래그를 붙여줘.
        > wiki-sync
      Redis 관련 심볼이 index에서 사라졌으면 auth-flow.md frontmatter의
      refs.code[].stale = true가 되고, wiki/questions.md에 리뷰 노트가
      추가됨. 그러면 연구자가 (a)로 수동 업데이트.

어느 쪽?
```

**Researcher chooses (b).** wiki-log proceeds with the decision template:

```
> (b)

wiki-log: OK, decision 엔트리로 전환.

Loading templates/design_decision.md (ko).
Auto-filled: {{DATE}}=2026-04-23, {{DECISION_ID}}=session-storage-postgres-migration, ...

**문제 — 이 결정이 해결하는 문제는?**
> Redis 세션 스토어가 고가용성 요구에서 장애 포인트. Postgres는 이미 운영 중
  이라 운영 부담이 적음.

[... decision 템플릿의 나머지 섹션 계속 ...]
```

**Outcome.** `auth-flow.md` body stays untouched. A new decision entry at `wiki/decisions/session-storage-postgres-migration.md` captures the change and its rationale. `auth-flow.md` frontmatter gets a back-ref entry in `refs.decisions` (if the template's auto-link `link_bidirectional: true`). The next `wiki-lint` run may observe that `auth-flow.md` body still mentions Redis while a decision has moved storage to Postgres, and flag this in `wiki/discrepancies.md`.

---

## Example 4 — Recovery: `--amend` to fix a typo on a recent entry

37 minutes after Example 1, the researcher notices their own Result section says "step 340" but their log file shows the NaN actually occurred at step 380.

**Invocation.**

```
> wiki-log --type experiment --amend
```

**Amend-window lookup.**

```
wiki-log: --amend 창(24h, 설정: research-wiki.config.yaml → log.amend_window)
안의 가장 최근 experiment 엔트리:

  wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md  (생성 37분 전, 2026-04-23 14:37)

현재 body (읽기 전용 보기):

  ## 가설
  batch size 256으로 올리면 lr=3e-4 써도 불안정하지 않을 것

  ## 셋업
  exp-2026-04-22-bs128 대비 bs=256, lr=3e-4, 3 seeds, 나머지 동일

  ## 결과
  3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.

  ## 관찰
  NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐

  ## 관련 코드
  trainer.py 메인 루프, 특히 train_one_epoch

뭘 고칠까? amend는 body만 수정. frontmatter refs를 바꾸려면 새 엔트리를 쓰고
거기서 auto-link pass를 다시 돌려야 해.
```

**Describe the fix.**

```
> 결과 섹션의 "step 340" 을 "step 380"으로. 그리고 관찰에도 "step 340"이
  있으면 같이 바꿔야 돼.
```

**Proposed diff.**

```
wiki-log: 두 군데 다 발견. 확인해줘.

 ## 결과
-3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN.
+3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 380에서 NaN.

 ## 관찰
-NaN 난 런의 grad norm이 step 300부터 단조 증가, step 340에서 inf로 튐
+NaN 난 런의 grad norm이 step 300부터 단조 증가, step 380에서 inf로 튐

[y] apply both / [1] 결과만 / [2] 관찰만 / [e]dit 직접 편집 / [N] 취소
> y
```

**Write phase.** Two file changes (index.md unchanged, no structural shift).

**(1)** `wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md`:
- Body: "step 340" replaced with "step 380" in both sections.
- Frontmatter `updated:` unchanged (same day — stays `2026-04-23`).
- Frontmatter `source_sessions:` extended with the current amend session:
  ```diff
  -source_sessions: [2026-04-23-s3]
  +source_sessions: [2026-04-23-s3, 2026-04-23-s4]
  ```

**(2)** Append to `wiki/log.md`:

```
## [2026-04-23 15:14] amend | experiment | lr-sweep-bs256

Fixed typo: "step 340" → "step 380" in 결과 and 관찰 sections.

→ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md
```

**Final report.**

```
✓ Amended wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md (2 lines changed)
✓ source_sessions extended
✓ wiki/log.md appended (amend note)
```

**If the amend window had no matching entry** (e.g., 30 hours after the most recent experiment):

```
wiki-log: 24h amend 창 안에 experiment 엔트리 없음.
가장 최근 experiment: wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md
                      (생성 30h 14m 전)

선택:
  (a) 파일을 직접 편집 — `$EDITOR wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md`
  (b) 수정을 대체하는 새 엔트리 로그 — supersedes 필드에 원본 엔트리 참조
  (c) amend_window를 설정에서 늘리기 — research-wiki.config.yaml →
      log.amend_window: 72h

Aborting.
```

---

## Example 5 — Concept stub creation (auto-link extension)

Continuing Example 1 — but the researcher's "관련 코드" answer also mentions a concept that doesn't exist yet:

```
**관련 코드 — 어떤 함수·파일이 관련됐어? 이름만 적으면 돼.**
> trainer.py 메인 루프, 특히 train_one_epoch. rotary embedding은 해제 상태.
```

**Auto-link concept scan now finds:**

```
scan: concepts (strategy: exact_slug)
  candidate noun phrases extracted: rotary embedding
  exact slug match in wiki/concepts/: none
  → routed to stub suggestion batch
```

**After the auto-link approval batch, a separate concept stub batch:**

```
[Concept stub suggestions]
  "rotary embedding"  → suggested slug: rotary-embedding   (no matching page exists)

Create stub? [y/N/edit] y
```

**Resulting stub at `wiki/concepts/rotary-embedding.md`:**

```yaml
---
schema_version: 1
type: concept
created: 2026-04-23
updated: 2026-04-23
tags: []
refs:
  code: []
  papers: []
  concepts: []
  experiments: []
authored_by: hybrid
source_sessions: [2026-04-23-s3]
seeded_by: wiki-log
seed_context:
  from_entry: wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md
  from_phrase: "rotary embedding"
---

*Stub created by wiki-log. Add interpretation here.*
```

The triggering experiment's `refs.concepts` is updated to point at the new stub:

```diff
   concepts:
+    - rotary-embedding
   experiments:
     - exp-2026-04-22-bs128
```

**Final report adds a line:**

```
✓ Concept stub created: wiki/concepts/rotary-embedding.md (seeded_by: wiki-log)
```

The stub is empty-bodied by design — wiki-log never writes prose about what a concept "is for" (P8). The researcher fills the body via direct edit (or a future "expand stub" interaction). `wiki-lint` Check #8 (orphan) recognizes `seeded_by:` and applies a grace period before flagging.
