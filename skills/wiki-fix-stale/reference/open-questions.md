# `wiki-fix-stale` — Open Questions

> Supplementary material for `wiki-fix-stale`. Not loaded at LLM runtime.

---

## 1. `--apply-to-all <choice-type>` per page

**Status:** designed, not yet shipped.

When a researcher is repeatedly choosing the same option (e.g., "wrap-deprecated" for all 5 mentions of the same removed symbol on a page), there should be a one-keystroke "apply this choice to all remaining occurrences on this page" option.

**Constraints:**
- Per page, per choice type — no cross-page bulk apply.
- Requires explicit per-page confirmation, not a session-wide setting.
- Does not bypass per-occurrence visibility — the skill still shows what would happen and asks `[y/N]`.

**Open:** UX — how to present the option without making it accidentally hit. Proposed: after the first 2 occurrences with the same choice on a page, the skill offers "apply (2) wrap-deprecated to remaining 3 occurrences? [y/N]".

---

## 2. Cross-skill integration with `wiki-log`

**Status:** rejected.

Idea: at the end of a fix-stale session, offer to invoke `wiki-log` to file a new entry that supersedes the deprecated material.

**Rejected:** keep skills composable but separately invoked. Conflating fix-stale (mechanical edits) with wiki-log (interpretive entry) muddies the skill boundary. Researcher invokes wiki-log next if they want.

---

## 3. Per-edit history versioning

**Status:** rely on git.

Every body edit applied by wiki-fix-stale is a regular file modification visible in git diff. The session record in `wiki/log.md` summarizes counts but does not duplicate per-edit history.

**Open:** is `wiki/log.md`'s session record granular enough? Currently lists counts (`9 body edits applied (4 replace, 3 wrap-deprecated, 2 delete)`) without per-edit detail. For research provenance, sometimes per-edit detail is useful.

**Proposed:** rely on git. Do not duplicate. If a researcher needs detail, `git log -p wiki/concepts/<page>.md` after the fix-stale session shows every change with timestamp and author.

---

## 4. Stale refs in `refs.papers`, `refs.concepts`, `refs.experiments`

**Status:** out of scope for v1.

Currently `wiki-fix-stale` only handles `refs.code` stale flags (set by `wiki-sync`). Wiki-internal refs (concepts, papers, experiments) can also become stale (deleted target page, renamed slug), but those are surfaced by `wiki-lint` Check #3 (intra-wiki link existence), not by wiki-sync.

**Proposed:** if this gap accumulates pain, extend wiki-fix-stale (or add `wiki-fix-broken-links`) for v1.x. For now, broken intra-wiki links are findings the researcher resolves manually based on wiki-lint reports.

---

## 5. Auto-suggesting replacement names

**Status:** rejected.

Idea: when `wiki-sync`'s rename heuristic in the snapshot detected a possible rename (e.g., `OldAttention → LegacyAttention` with 87% similarity), wiki-fix-stale's "replace symbol" option could pre-fill the suggestion.

**Rejected:** P8 risk. The rename heuristic is `[unverified]`; pre-filling a suggested name encourages the researcher to accept without verification. Better: surface the rename hint *adjacent* to the menu but require the researcher to type the new name explicitly.

**Compromise (accepted):** display "Note: wiki-sync's heuristic flagged `<old> → <new>` as a possible rename ([unverified] in sync_<date>.md)". Do not pre-fill. Researcher types the name themselves if they choose option 1.
