# `wiki-init` — Failure Modes (Detailed Catalog)

> Supplementary material for `wiki-init`. Not loaded at LLM runtime — the most common failure modes are inlined in `SKILL.md`. This file holds the full catalog including edge cases.

---

## Filesystem failures

### Permission error on write

- **Action:** abort the run. Report the offending path and the OS-level error.
- **Recovery:** researcher fixes permissions or chooses a different target directory and re-invokes.

### Target path does not exist

- **Action:** abort with a clear message. Do not auto-create the parent directory (the researcher may have typo'd).

### Disk full mid-write

- **Action:** abort. Idempotency guarantees re-invocation completes the missing pieces once disk space is restored. Do not attempt rollback.

---

## State-detection failures

### `adopt` mode finds conflicting files (existing `CLAUDE.md` with different content)

- **Action:** do not modify or delete anything. Present the conflict list and ask how to proceed:
  - (a) skip the conflicting files and create only the missing ones
  - (b) abort
- **Default:** wait for researcher choice; never auto-pick.

### Target path is inside another ResearchWiki workspace (nested `CLAUDE.md` found higher up)

- **Action:** warn the researcher. Ask for confirmation before proceeding, because the nested wiki may conflict with the outer one at lint time.
- **Recovery:** researcher confirms or moves to a different target.

### Researcher interrupts mid-run (Ctrl-C, network drop)

- **Action:** rely on idempotency — re-invocation of `wiki-init` picks up cleanly, creating only the missing pieces. Do not attempt automatic rollback (which could itself fail and leave a worse state).

---

## Reference asset failures (skill-set packaging bugs)

### Reference asset missing from the skill set

Any file listed under `reference/bundle/` being absent at invocation time is a skill-set packaging bug, not a researcher-fixable error. Specifically:

- `reference/bundle/CLAUDE.md` missing
- `reference/bundle/research-wiki.config.yaml` missing
- `reference/bundle/templates/<lang>/experiment.md` (or any of the four templates × two languages) missing

- **Action:** abort. Report the specific missing file. Suggest the researcher report to the skill-set maintainer or reinstall the skill bundle.
- **Critical:** do **not** fall back to generating the missing content from memory. That would silently introduce drift in the very documents the rest of the skill set treats as the source of truth (wiki-log expects the template structure as shipped; wiki-lint's frontmatter checks assume the schema in the reference CLAUDE.md; etc.).

### `reference/bundle/templates/<lang>/` does not exist for the requested `--language`

The skill set ships `en` and `ko`. If the researcher passes `--language fr`:

- **Action:** abort with a message listing available languages.
- **Recovery suggestion:** the researcher either picks a supported language or contributes templates for the new one to the skill set.

---

## Input validation failures

### `--seed-from` path does not exist

- **Action:** warn, then proceed without the seed reference. Note the missing path in the first log entry as `seed-from: (requested: <path>, not found)`.
- **Rationale:** `--seed-from` is purely informational (recorded in the log entry, not used to import content). A missing path is not blocking.

### `--language` value not recognized

- **Action:** abort with a list of recognized values (`ko`, `en`).

### `--deepscan-tool` value not recognized

- **Action:** abort with a list of recognized values (`understand-anything`, `none`).

### `--mode` value not recognized

- **Action:** abort with a list of recognized values (`new`, `adopt`).

---

## Confirmation failures

### Researcher declines confirmation (responds anything other than `y`)

- **Action:** abort without writing. No partial output.
- **Recovery:** researcher invokes again with corrected flags.

### Researcher confirms but then aborts mid-write

Same as the mid-run interrupt — idempotency carries the recovery.
