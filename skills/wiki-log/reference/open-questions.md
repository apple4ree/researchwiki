# `wiki-log` — Open Questions

> Supplementary material for `wiki-log`. Not loaded at LLM runtime — these are deferred design decisions for future iterations.

---

## 1. `--quick` mode for short entries

**Status:** designed, MVP includes the flag.

`--quick` skips the auto-link pass (and the concept stub suggestion pass) but keeps required-field validation, `authored_by` tagging, and P8 enforcement. Useful for short free-form notes where the auto-link approval batch would be more friction than value.

**Open:** should `--quick` also skip the conversational walk and accept all answers as one pasted blob? Proposed: no. Quick mode is about the auto-link cost, not the conversation cost.

---

## 2. Multi-language entries in the same session

**Status:** rejected.

A wiki initialized as `--language ko` ships with Korean templates only. If the researcher wants to file a single English entry inside an otherwise Korean wiki, current behavior is to use the Korean template and write English answers (the template prompts will still be Korean — confusing).

**Proposed:** one language per wiki, detected at init from `language.default`. Multi-language wikis are out of scope for MVP.

**Reconsider:** if a researcher feedback shows substantial mixed-language workflow.

---

## 3. `--amend` window default

**Status:** 24h, configurable via `log.amend_window`.

24h is long enough to catch "I noticed a typo right after writing" and short enough to avoid amending entries the researcher has already mentally moved on from.

**Open:** should the default differ by `--type`? Experiments often have post-run analysis that comes hours later (long window helpful); papers/decisions are usually settled at write time (short window safer). Proposed: keep uniform; let the researcher override per-config if needed.

---

## 4. `seed_context` field expansion

**Status:** MVP captures `from_entry` and `from_phrase` for `wiki-log`-seeded stubs.

**Open:** should `wiki-deepscan`-seeded stubs (which use the same `seeded_by:` mechanism) carry analogous `seed_context`? E.g., `from_graph_node:`, `from_centrality_score:`. Proposed: yes when wiki-deepscan's stub-seed mechanism is implemented; document the field schema in `docs/FRONTMATTER.md` (TBD).

---

## 5. `supersedes:` frontmatter for amend-window-expired entries

**Status:** mentioned in failure-modes.md as a recovery path, not implemented as schema.

When `--amend` window has expired and the researcher writes a new entry that supersedes the old one, there's no formal `supersedes:` frontmatter field today. Proposed: add `supersedes: [<entry-id>]` to the frontmatter schema; `wiki-lint` Check #3 (broken intra-wiki links) treats superseded targets as resolved (not broken).

**Decision needed before implementing wiki-lint refinement.**

---

## 6. Conversation logging

**Status:** not done.

The conversation between researcher and wiki-log is in-memory only. The final entry captures the *answers*, but not the *rejected drafts*, P8 interventions, or auto-link rejections. For research provenance, sometimes the rejected paths are interesting (especially the speculation-rewrite cases).

**Proposed:** optional `--log-session <path>` that appends the full conversation to a session log file. Off by default. Reconsider when researchers ask for it.
