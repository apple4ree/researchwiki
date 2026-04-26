# `wiki-lint` — Open Questions

> Supplementary material for `wiki-lint`. Not loaded at LLM runtime.

---

## 1. Audit report location

**Status:** decided.

`index/audits/lint_YYYYMMDD_HHMM.md` (mirrors `index/snapshots/`). `wiki-init` creates the directory at bootstrap.

**Rejected alternative:** `wiki/audits/` — closer to other wiki-meta files, but breaches the P1 fact/interpretation split. Audits are facts about wiki health, not interpretation.

---

## 2. Severity definitions

**Status:** partially codified.

Per-check defaults are listed in the catalog. The boundary between `warn` and `error` for several checks is not fully codified.

**Proposed:** `error` only for violations of `CLAUDE.md §5` frontmatter requirements (Checks 1, 2). Everything else `warn` (links, speculation, stale-age, contradictions) or `info` (orphans).

**Decision needed before:** first wiki-lint implementation, since severity drives `--strict` mode escalation behavior.

---

## 3. Speculation tokenization unit

**Status:** undecided — implementation-dependent.

Density (Check 5) requires a denominator. Two options:

- **Sentence-level:** count `[speculation]`-tagged sentences over total non-frontmatter sentences. Granular but requires a sentence segmenter.
- **Paragraph-level:** simpler; coarser. A single tagged sentence in a long paragraph still counts as 1/N.

**Decision needed:** the first implementation will set the de facto standard. Two implementations choosing differently produce non-comparable audit reports.

**Proposed:** sentence-level. Coarser units would dilute the speculation signal in long pages.

---

## 4. Gap detection

**Status:** half-spec'd; depends on `wiki-deepscan`.

`README §37` lists "gaps" as a finding category. Mechanically defining a "gap" without speculation is hard.

**Proposed compromise:** a gap is a deep-graph node (when `deep/knowledge-graph.json` is present) classified as architecturally significant by Understand-Anything, with no inbound `refs.code` entry from any wiki page. Data-grounded; skippable when the deep layer is absent.

**Decision needed before:** Check 9 (or higher) is added to the catalog. For MVP, gaps are not a check.

---

## 5. Should wiki-lint check `index/` for self-consistency?

**Status:** rejected.

E.g., `signatures.json` schema validity, snapshot file naming, `reverse_refs.json` integrity.

**Rejected:** that is `wiki-sync`'s output; if it is malformed, fixing wiki-sync is the right response, not adding a lint check. wiki-lint stays focused on wiki health, not index health.

---

## 6. Stub orphan grace period (Check #8 refinement)

**Status:** known follow-up (per `ARCHITECTURE.md` Appendix B 2026-04-25).

Pages with `seeded_by: wiki-log` or `seeded_by: wiki-deepscan` are *expected* to be orphans at creation time (the researcher hasn't filled the body yet, no other page links to them). Flagging them on the next audit is noise.

**Proposed:** Check #8 refinement — exclude `seeded_by:` pages whose `created:` is within `lint.stub_grace_period_days` (default 30). After the grace period, treat normally.

**Decision needed before:** stubs become a noise problem in real-world use. Currently a known follow-up, not a blocker.
