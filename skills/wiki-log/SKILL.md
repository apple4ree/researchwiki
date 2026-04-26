---
name: wiki-log
description: Use this skill when the researcher wants to add a new entry to their research journal — an experiment result, a paper summary, a design decision, or a free-form observation. This is the most-used ResearchWiki skill, invoked multiple times per day. The skill is a *Python + LLM hybrid*: deterministic operations (template parsing, frontmatter assembly, atomic file writes, code-symbol lookup, bidirectional back-refs) run via the `wiki log <subcommand>` CLI; the conversational interview, P8 speculation detection, identifier/noun-phrase extraction, and summary writing are the LLM's job. Trigger phrases include "기록할래", "실험 결과 정리해줘", "이 논문 읽었어", "디자인 결정 남겨줘", "wiki에 추가해", "log this", "add to wiki", "record the experiment", "file this paper reading", "log a decision". Do not use for regenerating the code index (use `wiki-sync`), running deep code analysis (use `wiki-deepscan`), auditing existing wiki content (use `wiki-lint`), initializing the workspace (use `wiki-init`), or editing the body of an existing wiki page (use `wiki-fix-stale` for stale-ref body edits, or refuse per `reference/refusal-patterns.md` §1).
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

## The full flow (every invocation)

1. **Parse the trigger.** Extract `--type` and `--title` from the
   researcher's first message. If either is missing, ask one focused
   question per missing field. Don't chain.

2. **`wiki log inspect`.** Get the template + path + workspace state.
   - `collision: true` → invoke the collision flow
     (`reference/refusal-patterns.md` §5).
   - `signatures_available: false` → warn, disable code auto-link
     extraction, continue.

3. **Walk sections.** For each section in `template.sections`:
   - Read the italic_guide internally; paraphrase to a natural
     question in the session language. **Never read italic verbatim.**
     (`reference/conversational-style.md` §1)
   - Wait for answer. Empty `[required]` → re-ask once. If still
     empty, abort or accept "no notable patterns" with researcher
     confirmation.
   - Run P8 detection on each answer. Hits → invoke the three-route
     flow (`reference/p8-detection.md` §1). Encode the chosen route
     into the payload before submission.

4. **Optional sections as a batch.** After all `[required]` filled,
   offer `[optional]` as a group ("선택 섹션 N개 남았어: ...").

5. **Auto-link extraction.** For each kind with
   `template_directives.auto_link.<kind>.enabled: true`:
   - Extract candidates from `section_answers` per
     `reference/auto-link-extraction.md`.
   - Run `wiki log lookup-symbols` (for `code`) or
     `wiki log find-pages` (for `experiments` / `concepts` / `papers`).
   - Build the candidate list; failed concept candidates → stub
     suggestion batch.

6. **Approval batches.** Two batches in order:
   - **Auto-link candidates** — single y/N/edit prompt
     (`reference/conversational-style.md` §5).
   - **Concept stub suggestions** — separate y/N/edit prompt for
     candidates that failed `find-pages --kind concepts`.

7. **Summary line.** Default to the first `[required]` answer if it
   is one short sentence; otherwise ask
   (`reference/conversational-style.md` §6).

8. **Assemble payload.** Build the JSON dict per the schema above.
   Set `authored_by: hybrid` (or `human` if researcher dictated
   verbatim). Write to a temp file (or stdin-pipe).

9. **`wiki log run --payload <file>`.** Atomic write. On success,
   render the result concisely (`reference/conversational-style.md` §7).
   On failure (FileExistsError / ValueError), surface the message
   and route accordingly.

### Quick mode

`--quick` skips steps 5–6 (auto-link extraction + approval batches +
stub suggestion). Required-field validation, P8 enforcement, and
`authored_by` discipline still apply.

### Amend mode

`--amend` replaces step 1's `inspect` with `wiki log find-amend-target
--type T`. If null, run the expired-window flow
(`reference/refusal-patterns.md` §6). Otherwise, show the body preview
and ask what to change. Apply via direct `Edit` (file in place — this
is the only case where wiki-log touches an existing entry's body, and
only because the researcher is amending *their own recent entry* in
`--amend` mode within the configured window). Append a single amend
note to `wiki/log.md`.

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
