# `templates/` — wiki-log Template Format

> Authoritative reference for how `wiki-log` consumes templates and how researchers author custom ones.
>
> Templates live at `<repo>/templates/<slug>.md`. `wiki-init` installs four defaults from `skills/wiki-init/reference/bundle/templates/<lang>/` — copied verbatim, flattened (no language subdirectory in the target repo), one language per workspace selected at init time.

---

## File anatomy

A template is a single Markdown file with two zones:

```
<HTML comment header — instructions for researchers reading the file>

---
{entry frontmatter — copied to the new wiki entry}

_template:
  {template directives — consumed by wiki-log; NOT copied to the entry}
---

# {{TITLE}}

<HTML comment — researcher instructions>

## Section heading  [required|optional]

*Italic guide text shown to the researcher (paraphrased; never read verbatim).*

<!-- example: an example answer -->
```

The `_template:` block sits inside the YAML frontmatter (between the two `---` delimiters) but uses an underscore-prefixed key, which `wiki-log` recognizes as template-only and strips before writing the new entry's frontmatter.

---

## Entry frontmatter (copied to the new entry)

The non-`_template` keys are copied to the new entry's frontmatter, with placeholder substitution. Per `CLAUDE.md §5`, every new page must have at least:

```yaml
schema_version: 1
type: concept | paper | experiment | decision | other
created: {{DATE}}
updated: {{DATE}}
tags: []
refs:
  code: []
  papers: []
  concepts: []
  experiments: []
authored_by: hybrid    # default; `human` when the researcher dictates verbatim. `llm` is FORBIDDEN by wiki-log.
source_sessions: [{{SESSION_ID}}]
```

Type-specific extensions (e.g., `git_ref:`, `seed:`, `paper_id:`, `decision_id:`) live alongside this minimum and follow the same placeholder substitution rules.

### Placeholder substitution

`wiki-log` fills these placeholders at template-load time:

| Placeholder | Value |
|---|---|
| `{{DATE}}` | ISO date `YYYY-MM-DD` of entry creation |
| `{{SESSION_ID}}` | Current LLM session identifier |
| `{{TITLE}}` | Researcher-provided title (from `--title` flag) |
| `{{GIT_REF}}` | `git rev-parse HEAD` output, or `null` if not a git repo |
| `{{PAPER_ID}}` | The slug, when `--type paper` |
| `{{DECISION_ID}}` | The slug, when `--type decision` |

Unknown placeholders are left as-is (the researcher may have intended a literal `{{X}}` for some reason — wiki-log does not assume).

---

## `_template:` block (consumed by wiki-log only)

This block is **stripped** from the output. It tells `wiki-log` how to handle the entry's auto-link pass and other template-specific behaviors.

### `_template.auto_link.<kind>`

Per ref kind (`code`, `papers`, `concepts`, `experiments`):

```yaml
_template:
  auto_link:
    code:
      enabled: true
      strategy: identifier_token   # how to find candidates in the body
      default_confidence: verified # what `confidence` to assign when found in index
    experiments:
      enabled: true
      strategy: exact_id
      link_bidirectional: true     # add a back-ref to the target page's frontmatter on approval
    concepts:
      enabled: true
      strategy: exact_slug
      link_bidirectional: true
    papers:
      enabled: false               # turn off this kind for this template
```

| Field | Type | Meaning |
|---|---|---|
| `enabled` | bool | If `false`, this kind is not scanned for the entry. |
| `strategy` | enum | `identifier_token` (code) — match identifier-shape tokens; `exact_id` (experiments) — match `exp-YYYY-MM-DD-*` patterns; `exact_slug` (concepts/papers) — exact slug match against `wiki/<kind>/`. |
| `default_confidence` | `verified \| inferred \| dynamic` | The `confidence` value written to `refs.<kind>` when the candidate is verifiable. wiki-log never stamps `verified` on data it could not verify. |
| `link_bidirectional` | bool | When `true`, approving a ref also appends a back-ref to the target page's frontmatter `refs:` block. **This is the only place wiki-log touches an existing page**, and the edit is frontmatter-only (CLAUDE.md §3 directory contract permits frontmatter ref edits). |

Other `_template.*` fields are reserved for future versions; current wiki-log ignores unknown keys.

---

## Body sections

The template body is walked section by section. Each `## ` heading becomes a *prompt* in the conversational fill-in.

### Heading flag

```markdown
## Section name  [required]
## Section name  [optional]
```

`[required]`: an empty or placeholder-only answer aborts the entry write. wiki-log re-asks; if the researcher declines, the run aborts.

`[optional]`: presented as a group at the end (`Optional: <names> — skip or fill?`); never forced.

The flag itself is **stripped** from the new entry's heading.

### Italic guide text

```markdown
## 가설  [required]

*무엇을 테스트했나요? 가설은 틀릴 수 있었던 주장 — 목표가 아닙니다.
한두 문장으로.*
```

The italic block (single `*…*` paragraph immediately after the heading) is the researcher's instruction. wiki-log:

1. Reads it internally.
2. Paraphrases it into a natural conversational question in the session's language.
3. **Does not read the italic text back verbatim.**
4. Removes the italic block from the new entry, replacing it with the researcher's answer.

### `<!-- example: ... -->` blocks

```markdown
## 결과  [required]

*숫자가 무엇을 보여줬나요? 직접 관찰만.*

<!-- 예: "3시드 중 2개는 val_loss 1.24로 수렴. 1개는 step 340에서 NaN 발생." -->
```

HTML comments starting with `<!-- 예:` or `<!-- example:` are example answers shown to the researcher (when helpful) but **stripped** from the output.

---

## The four default templates

`wiki-init` installs these into `templates/`:

### `templates/experiment.md`

Records an experiment run. Structure:
- `## 가설 [required]` — the falsifiable claim, not the goal.
- `## 셋업 [required]` — what changed since the last run; references prior `exp-YYYY-MM-DD-*` for auto-link.
- `## 결과 [required]` — direct observations only (P8: no causal claims here).
- `## 관찰 [required]` — patterns visible in logs/plots.
- `## 실패 양상 [optional]` — what went wrong.
- `## 관련 코드 [required]` — drives auto-link against `index/signatures.json`.
- `## 다음 단계 [optional]` — concrete follow-ups.

Auto-link: code (verified), experiments (bidirectional), concepts (bidirectional). Papers off — too noisy in experiment entries.

### `templates/paper_reading.md`

Records a paper summary. Structure (paraphrased):
- Citation metadata (`paper_id`, year, authors, venue) → frontmatter.
- `## 핵심 주장 [required]` — what the paper claims, in one paragraph.
- `## 방법 [required]` — how they measured / reasoned.
- `## 우리에게 의미 [optional]` — relevance to the researcher's project.

Auto-link: concepts (bidirectional), papers (cross-references). Code typically off — the paper isn't a code repo.

### `templates/design_decision.md`

Records a design decision. Structure:
- `## 문제 [required]` — what the decision resolves.
- `## 선택한 접근 [required]` — the approach taken.
- `## 근거 [required]` — why this approach.
- `## 거부된 대안 [required]` — alternatives considered + reasons rejected.
- `## 영향 범위 [optional]` — scope of the decision.

Auto-link: code (verified), concepts (bidirectional), experiments (bidirectional). Decisions often supersede previous ones — the `supersedes:` frontmatter field is reserved (see `wiki-log/reference/open-questions.md` §5).

### `templates/free_form.md`

Default fallback when `--type free` is used or when a typed template is missing. Single `## Notes [required]` section with no special structure. Used for ideas, bugs, observations, anything that doesn't fit the other three.

---

## Custom template authoring

To add a custom template (e.g., `templates/my_lab_experiment.md`):

1. **Start from a default.** Copy `templates/experiment.md` (or whichever is closest) and rename.
2. **Edit frontmatter.** Adjust `type:`, add type-specific fields (e.g., `lab_id:`, `compute_quota:`). All non-`_template` fields are copied to the new entry verbatim (with placeholder substitution).
3. **Edit body sections.** Add / remove / reorder `## ` headings. Mark each `[required]` or `[optional]`. Write the italic guide for what the researcher should answer — keep it short; wiki-log paraphrases.
4. **Adjust `_template.auto_link`.** Turn ref kinds on/off based on what's actually useful for this entry type. Set `link_bidirectional` on the kinds where you want the target page to track the back-link.
5. **Point the config at it.** In `research-wiki.config.yaml`:

   ```yaml
   log_templates:
     experiment: my_lab_experiment   # uses templates/my_lab_experiment.md instead of the default
   ```

6. **Test once.** Run `wiki-log --type experiment --title test-template` and verify the conversation prompts are sensible and the resulting entry has the expected structure. Discard the test entry afterward.

### Common pitfalls

- **Forgetting `[required]`/`[optional]` flags.** Without a flag, wiki-log treats the section as `[required]`. To make optional, add the flag explicitly.
- **Italic guide too long.** wiki-log paraphrases; if the guide is itself a paragraph of flavor text, the paraphrase loses signal. Keep guides 1–2 sentences.
- **Putting `_template:` outside the YAML.** It must be inside the `--- ... ---` block. Outside, it's just markdown text.
- **Using `authored_by: llm`.** wiki-log refuses; every entry must have human intent behind it. The valid values are `hybrid` (default), `human` (researcher dictated), or absence (treated as `hybrid`).
- **Putting placeholders in section bodies.** Placeholders only substitute in frontmatter. In bodies, `{{DATE}}` would survive verbatim into the new entry. If a body needs a date, the researcher writes it manually, or you put it in frontmatter where `{{DATE}}` lives.

---

## Where wiki-log strips template-only content

When wiki-log assembles the new entry from a template:

| Source content | Action |
|---|---|
| Top HTML comment block (instructions for researchers reading the template) | Stripped |
| Frontmatter `_template:` block | Stripped |
| `## ` headings with `[required]`/`[optional]` flag | Flag stripped, heading kept |
| Italic guide text under each heading | Stripped, replaced with researcher's answer |
| `<!-- example: ... -->` HTML comments | Stripped |
| `{{PLACEHOLDER}}` in frontmatter | Substituted |
| `{{PLACEHOLDER}}` in body | Left as-is (intentional escape hatch; researcher may use literal placeholders) |

The result is a clean wiki entry that reflects the researcher's answers, not the template's machinery.

---

## When wiki-log can't find a template

If `log_templates.<type>` points to a slug that does not exist in `templates/`:

```
wiki-log: Template for `experiment` not found at templates/my_lab_experiment.md;
falling back to templates/free_form.md. Check research-wiki.config.yaml → log_templates.
```

If `templates/free_form.md` is also missing, wiki-log aborts — that is a `wiki-init` packaging failure, not a researcher-fixable error. Re-run `wiki-init` (or restore from git) to recover the bundle.

---

## See also

- `skills/wiki-log/SKILL.md` — the agent-facing prompt that consumes templates.
- `skills/wiki-log/SPEC.md` — design rationale for the template-driven approach.
- `skills/wiki-log/reference/examples.md` — five worked examples of wiki-log filling these templates.
- `skills/wiki-init/reference/bundle/templates/{ko,en}/` — the source-of-truth bundled templates.
- `docs/CONFIG.md` — `log_templates` config keys.
