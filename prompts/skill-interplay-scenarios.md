# Prompt: Skill Interplay Scenarios

> **Use case:** Reference for how the five **MVP** ResearchWiki skills compose during real research.
> Shows the researcher-visible flow and the file mutations each skill causes.
>
> **Note:** This file documents only the MVP skills (`wiki-init`, `wiki-log`, `wiki-sync`, `wiki-deepscan`, `wiki-lint`). The retrieval extensions (`wiki-query`, `wiki-recall`) and the remediation skill (`wiki-fix-stale`) are not yet covered here — the retrieval extensions are read-only and one-shot, and `wiki-fix-stale` is the one skill that legitimately edits wiki page bodies (under researcher-initiated, per-occurrence-approved conditions). Their interplay is described in their own SPEC/SKILL files; the most consequential interaction is the `wiki-sync` (detects stale) → `wiki-fix-stale` (resolves stale) sequence, optionally surfaced by `wiki-query` badges between syncs.

## Scenario 1 — First day of a new project

Researcher has just cloned a fresh research repository and wants to set up ResearchWiki.

```
> wiki-init --language ko --deepscan-tool understand-anything

  [ResearchWiki] Proposed structure:
    CLAUDE.md
    research-wiki.config.yaml
    wiki/{concepts,papers,experiments,decisions}/
    wiki/{index,log,questions,discrepancies}.md
    index/
    deep/
    raw/{papers,experiments}/
    templates/{experiment,paper_reading,design_decision,free_form}.md

  Confirm? [y/N] y

  ✓ Created 14 files, 7 directories
  ✓ First log entry appended to wiki/log.md

  Next: run `wiki-sync` to scan the current code into the Index Layer.

> wiki-sync

  Index refreshed (1.8s).
    Files scanned: 12
    Symbols indexed: 47
    Stale wiki refs flagged: 0

> wiki-log --type decision --title initial-architecture

  (interactive conversation; researcher explains initial architecture;
   LLM drafts entry with refs.code populated from index/signatures.json;
   researcher approves)

  ✓ wiki/decisions/initial-architecture.md created
  ✓ wiki/log.md appended
  ✓ wiki/index.md updated
```

Result: project bootstrapped, one real decision recorded, wiki is alive.

## Scenario 2 — Daily morning ritual

Researcher sits down, has coffee, wants to know what happened yesterday and plan the day.

```
> wiki-sync

  Index refreshed (2.1s).
    Files scanned: 47
    Symbols indexed: 312 (+18, -3 since last sync)
    Stale wiki refs flagged: 2
      → wiki/concepts/auth-flow.md references removed `Trainer.old_step`
      → wiki/experiments/exp-2026-04-19.md references renamed `Model.forward_v1`

  Appended 2 notes to wiki/questions.md.
```

Researcher reads `wiki/changes.md` and `wiki/questions.md`, decides whether to update the flagged pages now or later. `wiki-sync` does not force them to decide.

## Scenario 3 — Recording an experiment

Researcher just ran an experiment and wants to log it.

```
> wiki-log --type experiment --title lr-sweep-bs256

  Template: experiment

  Hypothesis?
  > batch size 256 lets us use lr=3e-4 without instability

  Setup?
  > same as exp-2026-04-22 but bs=256, lr=3e-4, 3 seeds

  Result?
  > 2/3 seeds converged to val_loss 1.24. 1 seed NaN at step 340.

  Failure mode for the NaN run?
  > gradient norm spiked at step 300, then loss exploded

  Related code?
  > trainer.py, main loop

  [Auto-link candidates:]
    code: src/trainer.py:Trainer.train_one_epoch (verified)
    experiments: exp-2026-04-22-bs128 (based on title similarity)
    concepts: learning-rate-schedule (mentioned in body)

  Approve all? [y/N/edit] y

  ✓ wiki/experiments/exp-2026-04-23-lr-sweep-bs256.md created
  ✓ Bidirectional link added to wiki/experiments/exp-2026-04-22-bs128.md frontmatter
  ✓ wiki/log.md appended
```

Note the skill did **not** speculate on why the NaN happened. The researcher's answer ("gradient norm spiked") is recorded verbatim. The skill did not add a sentence like "this is likely due to the higher learning rate" because that would be P8 speculation.

## Scenario 4 — Ingesting a paper

Researcher read a paper worth filing.

```
> wiki-log --type paper --title original-2024

  Template: paper_reading

  Key claim?
  > contrastive loss with learnable temperature outperforms fixed temperature on benchmark X

  Relevance to my work?
  > I use fixed temperature in my current implementation. This is a possible direction.

  Method summary (your words)?
  > they parameterize tau and backprop through it. loss = -log(softmax(sim / tau))

  Open questions?
  > does learnable tau cause instability early in training?

  [Auto-link candidates:]
    concepts: contrastive-loss (exists, will bidi-link)
    concepts: temperature (does not exist — gap flagged to wiki-lint)
    code: src/losses.py (will link, but no specific symbol match)

  Approve? [y/N/edit] y

  ✓ wiki/papers/original-2024.md created
  ✓ Gap noted: temperature concept mentioned but no page exists

  Suggestion: consider running `wiki-log --type concept --title temperature`
  to turn this into a canonical concept page.
```

## Scenario 5 — Discovering a code-vs-paper discrepancy

Research is ongoing. The researcher asks the agent a question that crosses layers.

```
> ask: is my current loss function consistent with the original paper?

  [Agent procedure:]
    - Read wiki/papers/original-2024.md → "learnable temperature"
    - Read index/signatures.json → `src/losses.py:ContrastiveLoss`
    - Read src/losses.py directly → temperature is a constant 0.07

  [Agent response:]

  The current implementation uses a constant temperature (0.07, src/losses.py:14),
  while wiki/papers/original-2024.md records that the paper uses a learnable
  temperature. This is a discrepancy.

  Would you like me to:
    (a) record this in wiki/discrepancies.md
    (b) add a question to wiki/questions.md
    (c) both
    (d) nothing — you already know

> (a) and (b)

  ✓ wiki/discrepancies.md appended
  ✓ wiki/questions.md appended: "Align loss fn with paper — learnable tau?"
```

Note: the agent observed and reported. It did **not** claim the discrepancy is a bug, a mistake, or intentional. It let the researcher decide what the discrepancy means.

## Scenario 6 — Weekend audit

End of week. Researcher wants to clean house.

```
> wiki-deepscan

  Running Understand-Anything...
  ✓ Scan complete (3m 12s)
    Nodes: 412 (+47 since last scan)
    Edges: 1087

  Wiki updates:
    - 3 new stub pages created (authored_by: llm)
      wiki/concepts/data-loader.md
      wiki/concepts/config-loader.md
      wiki/concepts/checkpoint-manager.md
    - 12 existing pages had new verified refs.code added (frontmatter only)

  Suggested next step: fill in the 3 new stubs via wiki-log.

> wiki-lint

  wiki-lint — 2026-04-27

  Frontmatter: 2 warnings
  Links: 3 warnings
  Speculation: 1 warning
    wiki/decisions/batch-size-choice.md — 4 of 9 claims (44%) lack supporting refs
  Orphans: 1 info
  Gaps: 1 info
    "temperature" mentioned in 4 pages but no wiki/concepts/temperature.md
  Contradictions: 0

  Full report: index/lint-report-2026-04-27.md
  Findings appended to wiki/questions.md (5).
```

Researcher reviews the report, decides which to fix, asks the agent explicitly to revisit `wiki/decisions/batch-size-choice.md` to add missing references. That explicit request is what gives the agent permission to edit the interpretation layer (P3).

## What this shows about the architecture

- **The researcher never has to remember which file to edit.** They invoke a skill by intent ("log an experiment", "check the wiki's health") and the skill knows where things go.
- **No skill ever silently rewrites interpretation.** Every mutation of `wiki/` body content either came from `wiki-log` (which has researcher intent) or from a researcher-initiated explicit edit request.
- **The skills compose without overlap.** `wiki-sync` does not try to log. `wiki-log` does not try to scan. `wiki-lint` does not try to fix.
- **Bidirectional links are the backbone.** A healthy wiki is a graph, not a list.

## What this does not show (open questions)

- Cross-project workflows — the researcher with two parallel projects
- Team collaboration — two researchers editing the same wiki via git
- Long-running research — multi-month wiki behavior, link decay, concept drift

These scenarios need their own worked-out flows and are deferred to later design rounds.
