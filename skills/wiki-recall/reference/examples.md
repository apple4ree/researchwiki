# `wiki-recall` — Worked Examples

> Supplementary material for `wiki-recall`. Not loaded at LLM runtime.

---

## Example 1 — Happy path: monthly memory refresh

The researcher has been working hard on a new attention experiment for three weeks and wants to surface older pages they may have built on without re-linking.

```
> wiki-recall

1. wiki/concepts/auth-flow.md                            score 6.5  (updated 2026-01-12, 103 days ago)
   Overlaps with recent activity:
     - shared refs.code      src/trainer.py:Trainer        (logged 3 days ago in exp-2026-04-22)
     - shared refs.concepts  rotary-attention              (logged 8 days ago in design decision)

2. wiki/decisions/why-bs128.md                           score 4.0  (updated 2026-02-03, 81 days ago)
   Overlaps with recent activity:
     - shared refs.experiments  exp-2026-04-19              (logged 6 days ago)

3. wiki/papers/sparse-attention.md                       score 3.5  (updated 2026-01-28, 87 days ago)
   Overlaps with recent activity:
     - shared refs.concepts  attention-pattern-sparsity    (logged 2 days ago in concept page)

(7 more results suppressed; pass --top 20 to see them)

Window: --lookback 30 days, --stale-since 60 days
Recent log entries scanned: 14   |   Stale pages considered: 38   |   Pages with overlaps: 11
```

The researcher opens `wiki/concepts/auth-flow.md`, realizes the rotary-attention discussion there contradicts a more recent decision, and uses `wiki-log` to file a new design decision page reconciling them. wiki-recall did not propose the reconciliation — it only surfaced the page.

---

## Example 2 — Pre-paper-write check

The researcher is drafting a paper section on training loop choices and wants to be reminded of decision pages whose refs touch the current draft's topics.

```
> wiki-recall --scope decisions --lookback 14 --stale-since 30 --top 5

1. wiki/decisions/why-bs128.md                           score 4.0  (updated 2026-02-03, 81 days ago)
   Overlaps with recent activity:
     - shared refs.experiments  exp-2026-04-19              (logged 6 days ago)
     - shared refs.experiments  exp-2026-04-22              (logged 3 days ago)

2. wiki/decisions/lr-schedule-choice.md                  score 2.0  (updated 2026-03-01, 55 days ago)
   Overlaps with recent activity:
     - shared refs.code      src/trainer.py:lr_schedule    (logged 9 days ago)

(no further results within --top 5)
```

The researcher cites both decision pages in the paper draft.

---

## Example 3 — Empty result with helpful suggestions

```
> wiki-recall --stale-since 365

0 stale-but-relevant pages found.

Window: --lookback 30 days, --stale-since 365 days
Recent log entries scanned: 14   |   Stale pages considered: 4   |   Pages with overlaps: 0

Suggestions:
  - shorter --stale-since (default 60) to include more candidates
  - longer --lookback to widen the recent-activity window
  - --include-stubs if you have many wiki-deepscan-seeded pages

Exit code: 1.
```

The skill states the parameters and the empty-set causes structurally. It does not invent results.

---

## Example 4 — Refusal: nothing to compare against

```
> wiki-recall

wiki-recall: wiki/log.md is empty or missing.

There is no recent-activity corpus to compare stale pages against. wiki-recall
needs `wiki/log.md` entries within the --lookback window to compute overlaps.

Suggestions:
  - run wiki-log to start journaling, or
  - if you want raw keyword search instead of activity-based recall, use wiki-query.

Exit code: 1.
```

No partial output. The researcher is told exactly what is missing and what their alternatives are.
