# Prompt: Writing a ResearchWiki Skill

> **Use case:** When implementing a new skill for the ResearchWiki skill set, or revising an existing one.
> **Read before writing any skill files.** This enforces consistency across all 8 skills.
> **File naming note:** This prompt's filename is `writing-skill-md.md` for historical reasons; it now covers the full four-file model (SKILL.md + SPEC.md + `reference/` directory), not just SKILL.md.

## The four-file model of a skill

Every ResearchWiki skill lives in a per-skill directory `skills/<name>/` with exactly this layout:

```
skills/<name>/
├── SKILL.md                ← LLM-runtime prompt — what gets loaded into the agent's context every invocation
├── SPEC.md                 ← Human-facing design document — what the skill is and why it is shaped this way
└── reference/
    ├── examples.md         ← worked examples (3–5)
    ├── failure-modes.md    ← detailed failure catalog
    ├── open-questions.md   ← deferred design decisions
    └── consumed-config.md  ← config keys this skill reads + skill-output dependencies + writes
```

Why three locations:

- **SKILL.md is the LLM runtime prompt.** It must be self-contained for the agent to invoke correctly, but every line costs context budget. Keep it tight (~100–180 lines per skill).
- **SPEC.md is the architect's reference.** Captures design intent, the *why* behind decisions, alternatives considered. Read by humans, not loaded by agents at runtime.
- **`reference/` holds supplementary material** that a reader (or an LLM doing deep analysis) may want, but which would bloat the agent's runtime context if inlined into SKILL.md. Each file in `reference/` carries a header noting "Supplementary material for `<skill>`. Not loaded at LLM runtime."

This prompt governs how to write the SKILL.md (layer 1). The SPEC.md governs the design layer; `reference/` files follow conventions described in "The reference/ subdirectory" section below.

### Special case: `wiki-init/reference/bundle/`

`wiki-init` is the only skill that ships **runtime assets** (the constitution, default config, default templates) that get copied to the target repo at init time. Those live under `skills/wiki-init/reference/bundle/`, alongside the four documentation files at `skills/wiki-init/reference/{examples,failure-modes,open-questions,consumed-config}.md`. No other skill has a `bundle/` subdirectory.

## Mandatory structure for every SKILL.md

Every file must contain these sections in this order:

1. **YAML frontmatter** — `name:` + `description:` (for Claude Code's skill discovery; see "Description field discipline" below)
2. **Title + one-line description** — what the skill does, in 1 sentence
3. **Principles inheritance** — explicit reference to the P1-P8 principles in `CLAUDE.md` (one bullet per relevant principle, brief)
4. **When to use** — bullet list of clear triggers
5. **When NOT to use** — bullet list of anti-triggers (especially: which *other* ResearchWiki skill to use instead)
6. **Inputs** — flags, arguments, interactive prompts
7. **Outputs** — files written, reports shown, side effects
8. **Behavior contract** — bulleted rules the skill must follow, each citing the relevant principle (copied and adapted from SPEC.md)
9. **Researcher interaction flow** — what the conversation looks like (or "one-shot" + brief stdout shape if not interactive)
10. **Failure handling (essentials)** — the 4–6 most common failure modes inline; pointer to `reference/failure-modes.md` for the full catalog
11. **Reference** — bullet list pointing at the four files in `reference/` (no examples in SKILL.md itself)

**Examples do NOT go in SKILL.md.** They live in `reference/examples.md`. Inlining them bloats the LLM runtime context without proportional benefit — the agent learns the pattern from one or two short snippets in the Outputs section, not from five worked end-to-end traces.

## Tone and voice rules

- **Second-person imperative to the agent.** "Read the config file. Do not modify `wiki/` bodies." Not "The skill reads..." or "You should probably...".
- **Concrete paths, not abstractions.** Say `wiki/concepts/` not "the concepts directory".
- **One rule per sentence.** Do not pack multiple constraints into one clause.
- **No hedging.** "The skill **must** not overwrite" is better than "The skill should generally try not to overwrite".

## P1-P8 citations

Every SKILL.md must cite the relevant principles from `CLAUDE.md` in its Behavior contract section. Format:

```
## Behavior contract

- The skill never modifies `wiki/` page bodies. (P3 — propose, do not mutate interpretation)
- The skill never speculates about intent. (P8 — analysis yes, speculation no)
```

This citation is non-optional. It makes the constitutional basis of each rule explicit and auditable.

## Description field discipline (for skill discovery)

Claude Code's skill picker relies on the description to route user requests. Follow the skill-description guidelines Anthropic publishes. In particular:

- Start with "Use when..." or "Use this skill to..."
- Include the concrete Korean / English trigger phrases the researcher is likely to say
- Name the *other skills this replaces* in ambiguous cases

Example:

> Use this skill when the researcher wants to add a new entry to their research journal — an experiment result, a paper summary, a design decision, or a free-form observation. Trigger phrases include "기록할래", "실험 결과 정리해줘", "이 논문 읽었어", "디자인 결정 남겨줘", "log this", "add to wiki". Do not use for regenerating the code index (use `wiki-sync`) or for auditing the wiki (use `wiki-lint`).

## P8 enforcement — folded into principles + behavior contract

Earlier drafts of skill files included a separate `### P8 enforcement` subsection that restated the analysis-vs-speculation contract verbatim per skill. The current convention **folds that material into two existing places** to avoid duplication:

1. The **Principles inheritance** section's `P8 — Analysis yes, speculation no.` bullet states the rule for that specific skill (one sentence — what the skill does and does not do regarding analysis vs. speculation).
2. The **Behavior contract** section has one or more bullets that operationally enforce the P8 rule for the skill's specific operations (e.g., "No synthesis. Pointers + extractive snippets only."; "Never composes new prose. Replace takes researcher's literal token.").

Do not add a separate `### P8 enforcement` subsection. The principle is load-bearing enough that it must appear in *every* skill, but separate restatement bloats the runtime context without adding information beyond what the bullets already specify.

Skills that have a non-trivial P8 risk surface (notably `wiki-log` and `wiki-fix-stale`) should expand the relevant behavior-contract bullets with the specific intervention the skill performs (e.g., wiki-log's three-route flow for hedge / causal / intent claims). Other skills can keep the bullets short.

## The `reference/` subdirectory

Each of the four files in `reference/` has a defined role. Stick to the role; do not invent extra files unless the next time you draft a skill genuinely calls for one (and then propose adding the file type to this prompt).

### `reference/examples.md`

3–5 worked examples ordered from simplest to most nuanced:

1. **Happy path** — the most common, cleanest invocation.
2. **Ambiguity** — when the skill has to ask the researcher a clarifying question or surface an `[unverified]` heuristic.
3. **Refusal** — when the skill refuses to act (e.g., overwriting interpretation, running without config, P3 violations).
4. **Recovery** — when something goes wrong mid-run and the skill recovers gracefully.
5. **(Optional) Edge case** — a representative non-standard invocation that illustrates a behavior contract bullet.

Each example is a short dialogue or command-output block, not prose description. Header line: `> Supplementary material for <skill>. Not loaded at LLM runtime.`

### `reference/failure-modes.md`

The full failure catalog, grouped into categories (Workspace state / Config / Per-page / Cross-skill / Output / Edge cases). Each entry has:

- The condition (in bold heading or `**Action:** abort. ...` form)
- The skill's response
- (Where applicable) recovery suggestion for the researcher

Group by category — flat lists become unmaintainable past ~6 entries.

### `reference/open-questions.md`

Deferred design decisions. Each entry has:

- A title (one line)
- Status — `decided` / `proposed` / `rejected` / `undecided`
- Brief context
- Proposed resolution (if not yet decided) or rationale (if decided/rejected)

Resolved entries stay (with `Status: decided`) so the *why* is preserved. Don't delete them when the question is settled.

### `reference/consumed-config.md`

A per-skill index of `research-wiki.config.yaml` keys this skill reads. Sections:

- **Read at every invocation** — paths and other always-needed keys
- **Read by `<namespace>:` section** — the skill's own config namespace (e.g., `lint.*` for wiki-lint)
- **Reserved (declared, not yet used)** — keys that are documented but not yet consumed
- **Writes to** — what the skill writes (files + frontmatter edits + appends)
- **Reads from / interacts with other skills' outputs** — frontmatter fields and JSON files this skill consumes from other skills' outputs (NOT config — but worth indexing for cross-skill traceability)
- **Not consumed** — namespaces explicitly *not* read by this skill (helps reviewers verify boundaries)

This file's collected form across all 8 skills is the raw material for `docs/CONFIG.md` and `docs/FRONTMATTER.md` (TBD). Keep it disciplined.

## Do not include

- Vendor-specific Claude Code internals that may change
- Marketing language ("powerful", "intelligent", "seamless")
- Speculation about future versions of the skill
- Apologies or hedging about the skill's limitations — state limits as facts, not as regrets

## Final check before saving a skill

Before finalizing any new or revised skill:

**SKILL.md (the runtime prompt):**

1. Does every behavior-contract rule cite a principle (P1-P8)?
2. Does the YAML `description:` field contain trigger phrases in both Korean and English?
3. Is the **Reference** section at the bottom listing all four `reference/` files?
4. Are examples *not* present (they live in `reference/examples.md`)?
5. Does every "may write" action have a corresponding "may not write" rule?
6. Is the "When NOT to use" section at least as long as the "When to use"?
7. Is the file under ~200 lines? (Above that, content probably belongs in `reference/`.)

**SPEC.md (the design document):**

1. Is the `> Frequency / Tier / Writes-to` header present at the top?
2. Are the design rationale and principle references explicit?
3. Does the **Reference** section point to all four `reference/` files?
4. Is the file under ~80 lines?

**`reference/` files:**

1. Does each file's first line note "Supplementary material for `<skill>`. Not loaded at LLM runtime"?
2. `examples.md`: 3–5 worked examples in the standard order (happy / ambiguity / refusal / recovery / optional edge)?
3. `failure-modes.md`: grouped into categories, not a flat list?
4. `open-questions.md`: each entry has Status (`decided` / `proposed` / `rejected` / `undecided`)?
5. `consumed-config.md`: covers the six standard sections (read-at-every / `<namespace>:` / reserved / writes / cross-skill reads / not consumed)?

If any answer is no, the skill is not ready.
