# `wiki-log` — Refusal Patterns

> Supplementary material. wiki-log refuses certain requests by design,
> not because the Python core would fail, but because the request
> would violate a principle (P3, P7, P8) or step on another skill's
> turf. This file catalogs each refusal class and the alternative
> routes to offer.

---

## 1. Refusal class: edit existing page body (P3)

**Trigger phrases.** Researcher requests of the form:
- "auth-flow.md 의 'Redis' 부분을 'Postgres'로 바꿔줘"
- "기존 페이지 X 본문을 수정해줘"
- "wiki/concepts/foo.md 의 두 번째 문단을 다시 써줘"
- "rewrite the body of <page>"
- "fix the wording in <existing entry>"

**Why refuse.** P3 — wiki-log creates new entries; it does not silently
mutate interpretation. Researcher-initiated body rewrites are *the
researcher's* job (or `wiki-fix-stale`'s, under strict per-occurrence
approval).

**Refusal template (KO).**
```
wiki-log: 기존 페이지의 body 수정은 내 역할이 아니야. wiki-log는 새 엔트리를
만들고, 기존 페이지의 frontmatter refs만 업데이트해. 해석 계층(wiki/ body)은
조용히 다시 쓰지 않아 — CLAUDE.md §3 디렉토리 컨트랙트 + 원칙 P3.

세 가지 경로:

  (a) 에디터에서 직접 수정.
        $ $EDITOR <page-path>
      수정 후 frontmatter `updated:` 도 오늘 날짜로.

  (b) 새 decision 엔트리로 변경 이유를 남기기.
        > wiki-log --type decision --title <slug>
      decision 본문이 "문제 / 선택한 접근 / 근거"를 묻고, refs.<kind>로
      원래 페이지에 back-ref가 걸림. 원래 페이지 body는 그대로지만
      decision이 변경의 이유를 명시적으로 남김.

  (c) frontmatter ref가 stale 인 경우면 wiki-sync → wiki-fix-stale 사용.
      wiki-sync가 stale 플래그를 붙이고, wiki-fix-stale이 P3 carve-out
      모드로 per-occurrence 승인 받아 4가지 mechanical edit 만 수행.

어느 쪽?
```

**Refusal template (EN).**
```
wiki-log: editing existing page bodies isn't my role. wiki-log creates new
entries and updates frontmatter refs only — the interpretation layer
(wiki/ body) is never silently rewritten. CLAUDE.md §3 directory contract
+ principle P3.

Three routes:

  (a) Direct edit in your editor.
        $ $EDITOR <page-path>
      Bump frontmatter `updated:` to today after.

  (b) New decision entry recording the change.
        > wiki-log --type decision --title <slug>
      The decision template asks for problem / chosen-approach / rationale;
      a back-ref lands in the original page's frontmatter while the body
      stays untouched.

  (c) For stale frontmatter refs: wiki-sync → wiki-fix-stale. wiki-sync
      flags, wiki-fix-stale walks the flags under P3 carve-out (per-
      occurrence approval, 4 mechanical transformations only).

Which one?
```

**Do NOT do these things in response.** Even if the researcher pushes:
- Don't write a "patched" version of the body to a new file and link
  it as superseding — that creates two pages that disagree, with no
  governance.
- Don't open the page and re-emit the body with your "fixes".
- Don't append `[updated: ...]` annotations to the body.

The only acceptable mechanical edits to existing pages are:
1. **Frontmatter back-ref appending** (wiki-log itself does this when
   `link_bidirectional: true`) — and *only* to the `refs:` block.
2. **Stale-flag clearing + sentence-level mechanical replacement** —
   delegated to `wiki-fix-stale`.

## 2. Refusal class: LLM-only entries (P7/P8)

**Trigger phrases.**
- "이 코드 구조 보고 자동으로 concept 페이지 만들어줘"
- "그 논문 한 번 더 요약해서 entry 추가해줘" (when the researcher has
  not actually read the paper or dictated the summary)
- "summarize this commit and log it"
- "make a wiki entry from this README"

**Why refuse.** Every wiki-log entry must have human intent (`authored_by`
must be `human` or `hybrid`; `llm` is forbidden by design and by the
Python validator). An entry the researcher did not author or dictate
violates P7 (every claim has provenance) and P8 (analysis without
grounding is speculation).

**Refusal template.**
```
wiki-log: 모든 wiki 엔트리는 사람의 의도가 있어야 해 (`authored_by` 가
`human` 또는 `hybrid`; `llm` 은 금지). 네가 직접 본 적 없는 코드/논문에
대해 내가 추측 기반 엔트리를 만들면 P8 (analysis yes, speculation no)
위반이야.

대신:

  (a) 직접 읽고 짧게 dictate — "이 commit 요약하면 ..." 한두 문장 →
      그걸 가지고 free-form 엔트리 만들 수 있어.

  (b) wiki-deepscan — 코드 구조 기반 stub 자동 seeding (frontmatter +
      single italicized line, prose 없음). 본문은 네가 나중에 채워.

  (c) wiki-query — 이미 같은 주제 entry가 있는지 먼저 검색.
```

**Why offer wiki-deepscan as alternative.** Stubs from deepscan are
explicitly empty-bodied (just `*Auto-seeded by wiki-deepscan...*`) and
carry `seeded_by: wiki-deepscan`. They are flagged as such for
downstream skills (e.g., wiki-lint orphan check applies a grace
period). They do not pretend to be researcher-authored interpretation.

## 3. Refusal class: bulk import (out of scope)

**Trigger phrases.**
- "이 폴더의 .md 파일 전부 wiki에 import 해"
- "여기 5개 실험 결과를 한 번에 log 해줘"
- "import all entries from <other-tool>"

**Why refuse.** wiki-log is one entry per invocation by design. Bulk
mode would either (a) skip the conversational P8 enforcement on each
entry, or (b) spawn 5 sequential conversations — at which point the
researcher should run wiki-log 5 times anyway.

**Refusal template.**
```
wiki-log: bulk import 은 의도적으로 빠져있어. 한 번에 한 엔트리씩 P8
검증 + auto-link 승인이 들어가야 해서 묶어서 처리하면 그 검증을 우회하게 돼.

5개 실험이면 5번 호출 — 각각 짧으니까 큰 부담은 아닐 거야.
첫 번째부터 시작할까?

(외부 도구에서 import 라면, 직접 templates/experiment.md 형태로 파일을
만들어서 wiki/experiments/ 에 넣는 것은 여전히 가능. 단 frontmatter는
사람이 손으로 검수.)
```

## 4. Refusal class: workspace not initialized

**Trigger.** `wiki-log inspect` (or any subcommand) returns
`FileNotFoundError: template not found: templates/experiment.md`.

**Refusal template.**
```
wiki-log: 이 디렉토리는 ResearchWiki 초기화가 안 돼있어 (templates/ 가
없어). 먼저 wiki-init 실행:

  $ wiki-init [--language ko|en]

초기화 후 다시 wiki-log 호출.
```

Don't auto-run `wiki-init` — it's a one-time setup with multiple
configuration choices (language, deepscan tool, etc.) that the
researcher should make explicitly.

## 5. Refusal class: target path collision

**Trigger.** `wiki-log inspect` returns `collision: true`, OR
`wiki-log run` raises `FileExistsError`.

**This is not a "refuse forever" — it is a "refuse this slug, suggest alternatives".**

**Response template.**
```
wiki-log: <entry-path> 가 이미 있어. 옵션:

  (a) --title 을 다른 slug 로:
        > wiki-log --type experiment --title <slug>-v2

  (b) 기존 엔트리에 amend (24h 안이면):
        > wiki-log --type experiment --amend
      → wiki-log find-amend-target 으로 후보 확인

  (c) 같은 주제 새 엔트리를 supersede 형식으로:
        새 엔트리 본문에 "supersedes <old-slug>" 명시 + frontmatter
        refs.<kind> 에 old slug 추가
```

(c) is the most subtle — it does not refuse, it points the researcher
at the supersession pattern that keeps both entries.

## 6. Refusal class: amend window expired

**Trigger.** `wiki-log find-amend-target --type T` returns null.

**Response template.**
```
wiki-log: 24h amend 창 안에 <type> 엔트리 없음.
가장 최근 <type>: <last-entry-path> (생성 <Xh Ym> 전).

선택:
  (a) 직접 편집 — $ $EDITOR <path>
  (b) 수정을 대체하는 새 엔트리 (supersedes 필드 사용)
  (c) amend_window 늘리기 — research-wiki.config.yaml → log.amend_window: 72h

Aborting.
```

Don't auto-extend the window. The window is a configuration choice;
respecting it is part of P4 (configuration over convention).

## 7. Refusal class: speculation dispute (researcher refuses all 3 P8 routes)

**Trigger.** Researcher hits a P8 marker, you offer (a)/(b)/(c), and
they reject all three ("난 이대로 그냥 쓰고 싶어").

**Why refuse.** This is the hardest refusal because it can feel
adversarial. But the entry would silently inject ungrounded claims
into the knowledge base — exactly what P8 forbids. The right move is
to abort with no output rather than write an entry that violates the
constitution.

**Response template.**
```
wiki-log: 그럼 이 엔트리는 안 쓸게. P8 (analysis yes, speculation no)
원칙은 wiki-log가 묵묵히 위반할 수 있는 게 아니야 — 위반 한 번이 한참
뒤에 발견되면 그 사이에 다른 entry/decision 이 그걸 사실로 받아들이고
쌓일 수 있어서.

세 route 가 다 마음에 안 들면, 일단 중단하고:

  (a) 며칠 두고 추가 실험으로 인과를 확인한 다음 다시 log.
  (b) 그냥 wiki/notes/ 에 free-form 으로 짧게 메모 — free-form 은 구조가
      덜 빡빡해서 hedge 가 좀 들어가도 lint가 같은 강도로 잡진 않아 (단,
      lint speculation-ratio 카운트는 됨).

지금은 abort. 다시 호출하면 새 시작점에서 갈게.
```

Note: don't write a partial entry to /tmp or anywhere — abort is
abort. The CLI never wrote the entry, so there is nothing to roll
back.

## 8. Refusal class: out-of-scope skill request

**Trigger phrases.**
- "wiki-log 로 전체 wiki 검색해줘" → wiki-query
- "stale ref 다 정리해" → wiki-fix-stale
- "code index 다시 만들어" → wiki-sync
- "deep scan 돌려줘" → wiki-deepscan
- "audit 결과 보여줘" → wiki-lint
- "최근 잊혀진 페이지 보여줘" → wiki-recall

**Response template.**
```
wiki-log: 그건 <correct-skill> 의 역할이야. 다음 호출:

  $ <correct-skill-cli> [--repo .]

<correct-skill> 이 무엇을 하는지 짧게 알려줄까? 아니면 바로 호출?
```

Don't try to mimic the other skill — the principle separation is
intentional and each skill has its own approval semantics.

## 9. Edge case: ambiguous request that *might* be wiki-log

Sometimes the researcher's request is ambiguous between wiki-log and
another skill. Examples:

- "이 paper 한 번 정리해" → could be: read + summarize (wiki-log
  paper) OR check if it's already in wiki (wiki-query).
- "이 코드 구조 wiki에 남겨" → could be: a researcher-dictated
  concept entry (wiki-log) OR a graph-based stub (wiki-deepscan).

In these cases, ask one clarifying question:

```
wiki-log: 두 가지로 해석돼.
  (1) 새 paper-reading 엔트리를 같이 만들기 (네가 읽고 dictate)
  (2) 이미 정리된 entry 가 있는지 먼저 검색 (wiki-query)
어느 쪽?
```

Don't assume — researchers are sensitive to skills doing more than
they asked for.

---

**The shorthand:** wiki-log refuses to do anything that would (a)
write LLM-authored interpretation to disk without human intent, (b)
mutate existing interpretation silently, or (c) bypass the per-entry
P7/P8 enforcement that is the *only* thing keeping the wiki from
slow-drifting into a plausible-but-wrong knowledge base. When in
doubt, refuse and route to the appropriate skill.
