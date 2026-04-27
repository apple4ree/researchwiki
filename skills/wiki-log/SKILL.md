---
name: wiki-log
description: Use this skill when the researcher wants to add a new entry to their research journal — an experiment result, a paper summary, a design decision, or a free-form observation. This is the most-used ResearchWiki skill, invoked multiple times per day. The skill is a *Python + LLM hybrid* that runs in **conversation-as-source mode by default**: extract candidate entries from the recent conversation, validate them with `wiki log validate-candidate` (P8 marker detection, ref resolution, collision check), then present a batch with status flags so the researcher chooses per-entry depth — `[a]` auto-save clean ones, `[r]` review only flagged sections, `[f]` full interview, `[d]` drop. Most calls produce 0–3 questions instead of the prior 12–15. Three friction dials: `--default` (recommended), `--strict` (always review), `--quick` (auto-save all, tag P8 markers as `[speculation]`). Trigger phrases include "기록할래", "실험 결과 정리해줘", "이 논문 읽었어", "디자인 결정 남겨줘", "wiki에 추가해", "log this", "add to wiki", "record the experiment", "file this paper reading", "log a decision". Do not use for regenerating the code index (use `wiki-sync`), running deep code analysis (use `wiki-deepscan`), auditing existing wiki content (use `wiki-lint`), initializing the workspace (use `wiki-init`), or editing the body of an existing wiki page (use `wiki-fix-stale` for stale-ref body edits, or refuse per `reference/refusal-patterns.md` §1).
---

# wiki-log

> **Invocation:** `wiki log {inspect | lookup-symbols | find-pages | find-amend-target | run} ...` via Bash. The unified `wiki` CLI ships with the `researchwiki` Python package (`pip install researchwiki`).

Add a new entry to the research journal. The researcher's primary
daily skill. **Ease of use is the design driver** — the conversation
should feel fluid, not form-filling.

The mechanical I/O is delegated to the `wiki log` CLI subcommands. Your
job — the LLM's job — is everything *between* CLI calls: interviewing
the researcher, paraphrasing template guides into natural questions,
detecting and routing P8 speculation markers, extracting identifier
candidates from prose, gathering approval, and choosing the summary
line. The full reasoning toolkit lives in `reference/`; consult it
when you hit a non-trivial case.

## Principles inheritance

Operates under P1–P8 (see `CLAUDE.md`).

- **P1 — Fact and interpretation are separate.** Writes only to `wiki/`. Consults `index/signatures.json` for code auto-link but never writes to `index/` or `deep/`.
- **P3 — Propose, do not mutate interpretation.** Creates new entries. Does not rewrite bodies of existing pages. The only edits to existing pages are frontmatter back-refs (allowed by CLAUDE.md §3) and `wiki-fix-stale`'s carve-out (handled by a different skill).
- **P4 — Configuration over convention.** Template paths, target directories per type, auto-link defaults read from `research-wiki.config.yaml` (see `reference/consumed-config.md`).
- **P7 — Explicit uncertainty.** Every approved code ref carries a `confidence` level (`verified` only when the symbol came back matched from `lookup-symbols`; `inferred` only after researcher confirmation; otherwise drop). Every entry carries an `authored_by` tag.
- **P8 — Analysis yes, speculation no.** You detect hedge / causal / intent claims and route them via the three-route flow (rewrite as observation / `[speculation]` tag / move to `wiki/questions.md`). Never silently rewrite or silently tag. Full pattern catalog in `reference/p8-detection.md`.

## When to use

- Researcher ran an experiment — regardless of outcome.
- Researcher read a paper worth filing.
- Researcher made a non-trivial design or implementation decision.
- Researcher wants to record a free-form observation, bug, or idea.
- Any message of the form "log X", "기록해줘", "wiki에 남겨줘", "정리해줘".

## When NOT to use

- For regenerating the Index Layer → `wiki-sync`.
- For deep code analysis → `wiki-deepscan`.
- For audit / lint reports → `wiki-lint`.
- For editing an existing page body → refuse politely (see `reference/refusal-patterns.md` §1); offer manual edit, supersede with new decision entry, or `wiki-fix-stale` for stale-ref cases.
- For bulk import → out of scope; one entry per invocation. (`reference/refusal-patterns.md` §3)
- The repo is not initialized → `wiki-init` first. (`reference/refusal-patterns.md` §4)

## The CLI surface

The `wiki log` subcommand exposes five sub-subcommands. All emit JSON
on stdout for easy LLM consumption.

```
wiki log inspect           --type T --title X [--today YYYY-MM-DD] [--session-id ID] [--git-ref REF]
wiki log lookup-symbols    --tokens "t1,t2,..."         (or --tokens-file <path>)
wiki log find-pages        --kind K --ids "id1,id2,..." (or --ids-file <path>)
wiki log find-amend-target --type T [--window-hours 24]
wiki log run               --payload <json-file>        (or --payload - to read stdin)
```

### `inspect` — what the LLM uses to drive the conversation

Returns:
```jsonc
{
  "template": {
    "type": "experiment",
    "template_path": "/path/to/templates/experiment.md",
    "entry_frontmatter": { ... template defaults ... },
    "template_directives": {
      "auto_link": {
        "code": {"enabled": true, "strategy": "identifier_token", ...},
        "experiments": {"enabled": true, "link_bidirectional": true, ...},
        ...
      }
    },
    "sections": [
      {"title": "가설", "required": true, "italic_guide": "...", "example": "..."},
      ...
    ]
  },
  "entry_path": "/path/to/wiki/experiments/exp-2026-04-23-<title>.md",
  "today": "2026-04-23",
  "session_id": "2026-04-23-s1",
  "git_ref": "5a3f9e2",
  "placeholder_values": {"DATE": "2026-04-23", "TITLE": "...", ...},
  "existing_peer_pages": ["wiki/experiments/exp-2026-04-22-bs128.md"],
  "signatures_available": true,
  "collision": false
}
```

You use `sections` to drive the interview, `template_directives.auto_link`
to know which kinds of refs to scan for, `existing_peer_pages` for
contextual reference, and `collision: true` to short-circuit (offer
amend or alternative slug — `reference/refusal-patterns.md` §5).

### `lookup-symbols` — verify code identifier matches

After extracting identifier-shape tokens from researcher's prose
(per `reference/auto-link-extraction.md` §2), batch them through
`lookup-symbols`. Returns per-token `{matched, path, symbol, parent,
confidence, line}`. Build `payload.approved_refs.code` from the
`matched: true` results, plus any `matched: false` items the
researcher confirmed (record those as `confidence: inferred`).

### `find-pages` — exact-slug existence check

For experiment-IDs, paper-slugs, concept-slugs extracted from prose:
batch them through `find-pages`. Returns per-id `{matched, path}`.
The unmatched concept candidates flow into the **stub suggestion
batch** (separate approval pass; the approved ones go into
`payload.approved_stubs`).

### `find-amend-target` — amend-mode lookup

Returns the most-recent same-type entry within `--window-hours`, plus
a body preview. Use this when the researcher invokes `--amend` to
confirm the candidate before walking the diff conversation.

### `run` — atomic write phase

Takes the assembled payload (see schema below). Performs entry write,
log.md append, index.md update, bidirectional back-refs, concept stub
creation, and questions.md append in one call. Refuses (`exit 2`) on:
- `authored_by: llm` (forbidden)
- Required section blank
- Path collision

## The payload schema

JSON file (or piped stdin) handed to `wiki log run`:

```jsonc
{
  "type": "experiment",                          // required
  "title": "lr-sweep-bs256",                     // required (slug)
  "today": "2026-04-23",                         // required (ISO date)
  "session_id": "2026-04-23-s3",                 // required
  "git_ref": "5a3f9e2",                          // optional (auto-detected if omitted in inspect)
  "section_answers": {                           // required: every [required] section must have non-empty value
    "가설": "...",
    "셋업": "...",
    "결과": "...",
    "관찰": "...",
    "관련 코드": "..."
    // optional sections may be omitted or empty
  },
  "approved_refs": {                             // required (may be empty)
    "code": [{"path": "...", "symbol": "...", "confidence": "verified"}, ...],
    "experiments": ["exp-...", ...],             // bare slugs
    "concepts":    ["...", ...],
    "papers":      ["...", ...]
  },
  "approved_stubs": [                            // optional
    {"slug": "rotary-embedding", "from_phrase": "rotary embedding"}
  ],
  "questions": [                                 // optional (P8 route-c entries)
    {"question": "...", "context": "..."}
  ],
  "summary_line": "...",                         // required (1 sentence for log.md)
  "authored_by": "hybrid",                       // required: "human" | "hybrid" (NOT "llm")
  "extra_frontmatter": {                         // optional template-specific fields
    "run_duration": "2h 14m",
    "seed": [1, 2, 3]
  }
}
```

## The flow — Conversation-as-source (default)

Default mental model: the *current conversation* is the raw material.
You don't run a fresh interview — you extract candidate entries from
what the researcher already said, present a batch with status flags,
and ask only about flagged items. This is dramatically less friction
than the prior interview-first model and is the recommended path.

The full eight-step interview model is still available via `--full`
mode (see below) for high-stakes entries, but for daily journaling
**default to the batch-extraction flow**.

### Step 1 — Read recent conversation context

When the researcher invokes wiki-log (`/researchwiki:wiki-log`,
"기록해줘", "log this", etc.), scan the recent conversation in this
session. Identify segments that look like loggable events:

- **Experiment results** — they ran something and reported numbers /
  observations.
- **Paper readings** — they discussed a paper's claims / methods.
- **Decisions** — they chose X over Y with stated reasons.
- **Free notes** — bug reports, ideas, observations worth keeping.

For each segment, draft a candidate. Multiple candidates from one
session are fine — the batch UI handles them.

### Step 2 — Build draft candidates

For each candidate:
- Pick a `type` (`experiment` / `paper` / `decision` / `free`).
- Compute a slug `title` (e.g., `lr-sweep-bs256` from researcher's
  prose mentioning a learning rate sweep at batch size 256).
- Run `wiki log inspect --type T --title X` once to get template
  metadata (sections + auto-link directives).
- Extract `section_answers` from the conversation, mapping researcher's
  utterances onto the template's required + optional sections.
- Extract identifier tokens / noun phrases / experiment-IDs / paper-slugs
  into `extracted_refs` (don't filter yet — that's the validator's job).

This gives you a `CandidateDraft` JSON per candidate.

### Step 3 — Validate each candidate

Pipe each draft through:

```bash
wiki log validate-candidate --draft <draft.json>
```

Returns a `CandidateValidation` JSON with:
- `status`: `ok` / `needs-review` / `fatal`
- `issues`: list of `{kind, severity, ...}` — `missing-required`,
  `p8-marker`, `ref-unresolved`, `stub-candidate`, `collision`
- `ref_resolution`: per-ref-kind matched/unmatched details
- `collision`: bool
- `entry_path`: where it would be written

### Step 4 — Present batch to researcher

Render a compact summary, one line per candidate, with status icon:

```
[wiki-log] 최근 대화에서 3개 후보 발견:

  [1] ✓ experiment / lr-sweep-bs256
      모든 섹션 추출됨, 깨끗
      refs: trainer.py:train_one_epoch (verified), exp-2026-04-22-bs128

  [2] ⚠ experiment / nan-debug
      "관찰" 에 P8 마커 1개 ("lr 때문에 ... 발생했을 것")
      refs: 없음

  [3] ⚠ decision / adopt-postgres
      "근거" 에 P8 마커 2개
      "options considered" 누락 (optional)
      stub 후보: postgres-migration

저장 방식?
  [a] 모두 자동저장 (P8 마커는 [speculation] 자동 부착, 누락 optional 은 빈 칸)
  [r] 1 자동, 2·3 만 review (예상 질문 3~4개)
  [f] 전부 full interview (예상 질문 12~15개)
  개별 지정: 1=a 2=r 3=f
  [d 1] 1번만 drop, 나머지는 review
```

**Default: `[r]`.** Auto-save clean candidates, review only flagged.

### Step 5 — Per-tier handling

For each selected tier:

#### `[a]` Auto-save (clean only)

Skip questions entirely. Build `LogPayload`:
- `section_answers` from draft as-is.
- `approved_refs` from `ref_resolution` — only `matched: true` items.
- `approved_stubs` from `stub-candidate` issues — auto-create the
  suggested slug. **(This is the one auto-action under `[a]`.)**
- `summary_line` = first sentence of the first required section.
- `authored_by: hybrid`, `auto_extracted: true` in `extra_frontmatter`.
- For P8-flagged sections in auto-save mode, prepend `[speculation]`
  to the flagged span (do NOT route to questions.md silently — that
  changes information; tagging in place preserves it).

Then call `wiki log run --payload <file>`.

#### `[r]` Review (default)

For each flagged item only:
- **P8 marker** → run the three-route flow (`reference/p8-detection.md` §1)
  on that section only. Don't re-ask other sections.
- **missing-required** → ask one focused question for that section.
- **ref-unresolved** → ask "이거 verified 로? inferred 로? 빼?".
- **stub-candidate** → ask y/N/edit per phrase.

After flagged items are resolved, build payload + `wiki log run`.

#### `[f]` Full interview

Fall back to the legacy step-by-step interview (the prior 9-step model).
See "Legacy `--full` interview model" at the bottom of this file.

#### `[d N]` Drop

Don't save candidate N. No file written.

### Step 6 — Report

After all selected candidates are processed:

```
✓ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md created  ([a])
✓ wiki/experiments/exp-2026-04-23-nan-debug.md created       ([r], 1 P8 question resolved)
✗ wiki/decisions/adopt-postgres.md skipped                   ([d])
✓ Concept stub: wiki/concepts/postgres-migration.md
✓ wiki/log.md, wiki/index.md updated
```

## Tier modes — friction dial

The default flow above maps to `--default` (i.e., omitted). Two other
modes shift the question budget:

- **`--strict`** — even "ok" candidates go through review (no auto-save).
  For paper / decision entries where curation matters more than speed.
- **`--quick`** — auto-save *all* candidates regardless of P8 flags
  (markers get `[speculation]` tags but no questions). For inbox-style
  rapid capture; pair with `wiki-lint` periodically to catch drift.

## Legacy `--full` interview model

If the researcher invokes `wiki-log --full`, OR a candidate is
selected with `=f`, OR no recent conversation context exists (e.g.,
fresh session), fall back to the explicit interview:

1. Parse `--type` / `--title` flags or ask.
2. `wiki log inspect`. Handle collision.
3. Walk sections in order, paraphrasing italic guides into natural
   questions (`reference/conversational-style.md` §1). P8 detect on
   each answer.
4. Optional sections as a batch.
5. Extract candidates → `wiki log lookup-symbols` / `find-pages`.
6. Approval batches (auto-link + stub suggestion).
7. Summary line.
8. Assemble payload, `wiki log run`.

This is the prior heavy-friction model. Available but no longer the
default — most invocations take the conversation-as-source path.

### Amend mode

`--amend` replaces the candidate flow with `wiki log find-amend-target
--type T`. If null, run the expired-window flow
(`reference/refusal-patterns.md` §6). Otherwise, show the body preview
and ask what to change. Apply via direct `Edit` (file in place — the
only case where wiki-log touches an existing entry's body, and only
because the researcher is amending *their own recent entry* within
the configured window). Append a single amend note to `wiki/log.md`.

## Reasoning resources (`reference/`)

Consult these whenever the conversation goes off the happy path:

| File | When to consult |
|---|---|
| `reference/p8-detection.md` | Every section answer — scan for hedge/causal/intent markers. Use the three-route flow when one fires. |
| `reference/conversational-style.md` | Pacing, paraphrasing, push-back patterns. Read once early in any session if conversation feels stilted. |
| `reference/auto-link-extraction.md` | Identifier / noun-phrase / paper-slug / experiment-ID extraction rules. Section-level tuning notes. |
| `reference/refusal-patterns.md` | When the researcher asks for something out of scope (body edit, LLM-only entry, bulk import, etc.). Each refusal class has a template response. |
| `reference/templates-deep-dive.md` | Per-template authoring guidance — what makes a strong vs weak answer for each section, what anti-patterns to push back on. |
| `reference/examples.md` | Five worked end-to-end examples (happy path, P8 enforcement, body-edit refusal, amend, concept stub). |
| `reference/failure-modes.md` | Full failure-mode catalog (workspace not init, missing template, signatures absent, target collision, etc.). |
| `reference/consumed-config.md` | Config keys this skill reads from `research-wiki.config.yaml`. |
| `reference/open-questions.md` | Deferred design decisions; do not implement these on your own. |

## Behavior contract

- **Template-driven.** Section walking obeys `template.sections` order
  + `[required]` flag. Auto-link obeys `template.template_directives.
  auto_link.<kind>` rules.
- **One entry per invocation.** No bulk mode.
- **`authored_by`:** default `hybrid`; `human` when researcher
  dictates verbatim; **`llm` is forbidden** by the Python validator
  and by design — every wiki-log entry has human intent.
- **Required sections enforced.** Empty / placeholder-only `[required]`
  answer → re-ask. If researcher declines, abort with no output.
- **No body edits on existing pages (P3).** New entry referencing /
  contradicting / superseding an existing page → add the ref
  (frontmatter back-ref via `link_bidirectional`), file a tension note
  to `wiki/questions.md` if the new entry contradicts an existing
  page, do **not** modify the existing body. (Exception: `--amend`
  on the researcher's own recent entry within the configured window.)
- **No speculation (P8).** Hedge verbs, causal claims without log
  evidence, intent attribution → name the issue, offer three routes,
  never silently rewrite or silently tag.
- **Auto-link obeys template directives.** Only scan kinds with
  `enabled: true`. Use declared `strategy`. Never stamp `verified`
  on data the skill cannot verify in `index/signatures.json` or as
  an existing wiki page.
- **Auto-link requires approval.** Present candidates as a batch.
  Write no ref without explicit approval. `edit` lets researcher
  accept/reject individually.
- **File existence respected.** Target path collision → refuse;
  offer alternative slug or `--amend`.
- **`--quick` skips auto-link, not validation.** Required-field,
  `authored_by`, P8 still apply. Concept stub suggestion also skipped
  (it's part of auto-link).
- **Concept stubs are create-only and body-empty.** Frontmatter +
  single italicized line. Carry `seeded_by: wiki-log` +
  `seed_context:` for downstream skill recognition. `wiki log run`
  enforces this — you cannot accidentally write prose to a stub.

## Failure handling (essentials)

- Target repo not initialized → `wiki log inspect` raises
  FileNotFoundError; abort and route to `wiki-init`.
- Template missing → fall back to free_form, warn.
- `index/signatures.json` absent → `inspect` reports
  `signatures_available: false`; warn, skip code auto-link, continue.
- Required section blank → re-ask; abort if researcher declines.
- Target file exists → `inspect.collision: true`; route to
  refusal-patterns §5 (alternative slug or `--amend`).
- Researcher asks to edit existing page body → refusal-patterns §1.
- Speculation dispute (researcher refuses all three routes) →
  refusal-patterns §7; abort with no output.
- `--amend` with no entry in window → refusal-patterns §6.

Full failure-mode catalog: `reference/failure-modes.md`.

---

**The shorthand:** the CLI is your toolkit, not your script. The
*conversation* is what the researcher experiences and what determines
whether the wiki is a useful living journal or a graveyard of
half-formed entries. Use the reference materials liberally; that is
what they are for.
