# `wiki-fix-stale` — Worked Examples

> Supplementary material for `wiki-fix-stale`. Not loaded at LLM runtime.

---

## Example 1 — Happy path: weekly stale-cleanup after a renaming refactor

Last week the researcher renamed `OldAttention` → `LegacyAttention` in code. `wiki-sync` flagged `stale: true` on three wiki pages that referenced `OldAttention`.

```
> wiki-fix-stale

wiki-fix-stale: 3 pages with unresolved stale refs.
  Oldest: 6 days ago.
  Total occurrences: 3 frontmatter refs + 4 body mentions [unverified]
  Walking pages oldest-first.

Continue? [y/N]

> y

────────────────────────────────────────────────────────────
[Page 1/3]  wiki/concepts/attention.md  (flagged 6d ago)

Occurrence 1/3 (frontmatter ref)
  Symbol: OldAttention
  Line 18 — context:
     > OldAttention은 우리 모델의 baseline이다.

  Action?  (1) replace  (2) wrap-deprecated  (3) delete  (4) skip
> 1
  New symbol name?
> LegacyAttention

✓ Recorded: replace OldAttention → LegacyAttention at line 18.

Occurrence 2/3 (body mention [unverified])
  Symbol: OldAttention
  Line 27 — context:
     > LegacyAttention 대비 14% 빠르며, OldAttention 대비도 18% 빠름.

  Action?
> 1
  New symbol name? (suggest LegacyAttention from previous choice)
> LegacyAttention

✓ Recorded.

Occurrence 3/3 (body mention [unverified])
  Symbol: OldAttention
  Line 42 — context:
     > OldAttention 분석은 별도 페이지로 분리.

  Action?
> 2

✓ Recorded: wrap-deprecated at line 42.

Page diff (not yet written):
  Line 18:  s/OldAttention/LegacyAttention/
  Line 27:  s/OldAttention/LegacyAttention/g
  Line 42:  prepend [deprecated 2026-04-25]

Frontmatter clearance:
  refs.code[OldAttention] → flag removed
  body_stale_mentions     → 2 entries removed

Apply? [y/N/edit]
> y

✓ Written.

────────────────────────────────────────────────────────────
[Page 2/3]  wiki/experiments/exp-2026-04-19.md  ...
```

After all 3 pages, the session record appends to log.md and the researcher's wiki is internally consistent again — no body lies, no stale flags.

---

## Example 2 — Refusal: nothing to fix

```
> wiki-fix-stale

No stale flags to fix.
Exit code: 0.
```

The skill does not invent work. If `wiki-sync` has not produced any unresolved stale flags, there is nothing to do.

---

## Example 3 — Partial session: researcher decides to defer

```
> wiki-fix-stale --page wiki/concepts/legacy-cache.md

[Page 1/1]  wiki/concepts/legacy-cache.md  (flagged 23d ago)

Occurrence 1/4 (frontmatter ref)
  Symbol: LegacyCache
  Line 12 — context:
     > LegacyCache는 더 이상 권장되지 않으며 다음 분기 제거 예정.

  Action?
> 4

(researcher continues skipping all 4 occurrences)

Page diff: (none — all 4 skipped)
Frontmatter clearance: skipped (skips present, flag retained)

Page written? No edits to apply.

Session summary:
  Pages fully cleared: 0
  Pages partially handled: 1 (4 skipped)
  Body edits applied: 0
```

The researcher decided this page documents intentional deprecation and the body should remain as-is until the symbol is actually removed. The flag stays; the page resurfaces next time `wiki-fix-stale` is invoked.

---

## Example 4 — False positive: symbol not found in body

```
[Page 1/1]  wiki/decisions/why-bs128.md  (flagged 9d ago)

Frontmatter stale ref: OldAttention
Body grep: 0 occurrences found.

This page references OldAttention only in frontmatter `refs.code`, not in body prose.
  Action?
    (1) Clear the frontmatter flag (no body edits)
    (2) Skip and leave the flag

> 1

✓ Frontmatter flag cleared. No body edits.
```

The skill recognized the false-positive case (frontmatter says stale but body never mentions the symbol) and offered the right narrow action.
