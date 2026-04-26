# `wiki-deepscan` — Worked Examples

> Supplementary material for `wiki-deepscan`. Not loaded at LLM runtime.

---

## Example 1 — Happy path: weekend refresh creates 3 stubs and updates 12 pages

**Setup.** Target repo `/home/researcher/attention-study/`. Last deepscan 7 days ago at commit `bf3ee41`. 18 commits since. Understand-Anything 0.4.2 installed.

**Invocation.**

```
> wiki-deepscan
```

**Confirmation.**

```
wiki-deepscan: Understand-Anything 0.4.2 detected.
  Scope: . (full repo)
  Last scan: 2026-04-20 at bf3ee41 (7 days, 18 commits ago).
  Mode: --incremental=true. Expected full-rescan of changed modules only.
  Estimated duration: ~3–5 min.

  New stubs will be seeded for components with ≥3 inbound edges (threshold
  from research-wiki.config.yaml → deepscan.stub_edge_threshold). Preliminary
  estimate: 3 candidate components.

  Proceed? [y/N] y
```

**Execution.**

```
Running understand-anything --incremental --from deep/last-scan.yaml ...

[tool output streamed — abridged]
  Scanning changed modules: 8 files
  Unchanged graph regions reused: 394 nodes, 959 edges
  Building updated call graph ...
  Classifying layers ...
Done. 3m 12s.

Parsing graph output ...
  Total nodes: 412 (+47, -12, *23 since 2026-04-20)
  Total edges: 1087 (+128, -35)

Stub seeding pass:
  Candidates with ≥3 inbound edges and no existing wiki page:
    - src/data/loader.py:DataLoader           (18 inbound) → seed
    - src/config.py:ConfigLoader              (11 inbound) → seed
    - src/trainer.py:CheckpointManager        (7 inbound)  → seed
  Below threshold (skipped):
    - src/utils/telemetry.py:Telemetry        (2 inbound)
    - src/cli/main.py:CliEntry                (1 inbound)

Cross-check against existing wiki:
  12 existing pages match graph nodes; adding new verified refs:
    wiki/concepts/trainer.md         (+2 refs: save_checkpoint, load_checkpoint)
    wiki/concepts/attention.md       (+1 ref: RotaryEmbedding)
    ...
  1 frontmatter vs graph discrepancy:
    wiki/concepts/auth-flow.md frontmatter points to src/auth/login.ts;
    graph shows src/auth/session.ts as the actual definition.
    → logging to wiki/discrepancies.md (not auto-correcting)

Naming conflicts: 0

Writing ...
  ✓ deep/knowledge-graph.json   (412 nodes, 1087 edges)
  ✓ deep/last-scan.yaml
  ✓ wiki/concepts/data-loader.md        (new stub, authored_by: llm)
  ✓ wiki/concepts/config-loader.md      (new stub, authored_by: llm)
  ✓ wiki/concepts/checkpoint-manager.md (new stub, authored_by: llm)
  ✓ wiki/concepts/trainer.md            (frontmatter: +2 refs.code)
  ✓ wiki/concepts/attention.md          (frontmatter: +1 ref.code)
  ... (10 more frontmatter updates)
  ✓ wiki/discrepancies.md               (1 note appended)
  ✓ deep/deepscan-report-2026-04-27.md  (full report)
```

**New stub contents** (for `wiki/concepts/data-loader.md`):

```markdown
---
schema_version: 1
type: concept
created: 2026-04-27
updated: 2026-04-27
tags: [auto-seeded]
refs:
  code:
    - path: src/data/loader.py
      symbol: DataLoader
      confidence: verified
    - path: src/data/loader.py
      symbol: DataLoader.__iter__
      confidence: verified
    - path: src/data/loader.py
      symbol: DataLoader.shuffle
      confidence: verified
  papers: []
  concepts: []
  experiments: []
authored_by: llm
source_sessions: [2026-04-27-deepscan-1]
---

# DataLoader

## Structural facts (auto-generated)

This component lives at `src/data/loader.py`. It exposes the following public
symbols:
- `DataLoader` (class)
- `DataLoader.__iter__` (method)
- `DataLoader.shuffle` (method)

According to the code graph, it is called by (18 inbound edges):
- `src/trainer.py` at lines 67, 104, 182
- `src/experiments/run.py` at lines 31, 54
- `src/evaluation/evaluate.py` at lines 22, 89
- (12 more — see deep/knowledge-graph.json node id 0x4a2)

It depends on:
- `src/data/dataset.py:Dataset`
- `torch.utils.data.DataLoader` (external)

## Notes from researcher

*Empty — add your interpretation here.*

## Open questions for researcher

- What problem does this component solve?
- What alternatives were considered?
- What are its failure modes?
- How does shuffle behavior differ from torch.utils.data.DataLoader?
```

---

## Example 2 — Ambiguity: incremental scan detects a partial rename

After a refactor that renamed `Trainer.forward_v1` to `Trainer.forward`, the incremental scan sees the old name disappear and the new name appear. Whether this is a rename or a delete+add is not fully determinable from the graph alone.

```
wiki-deepscan: Running understand-anything --incremental ...

  Graph delta observed:
    src/trainer.py:Trainer.forward_v1 → removed
    src/trainer.py:Trainer.forward    → added
  Rename heuristic: same file, adjacent line range, 89% body similarity.
    → annotated as rename candidate; CONFIDENCE MARKED `inferred` rather than
      `verified` for any ref that would previously have pointed to
      Trainer.forward_v1.

Cross-check with existing wiki:
  wiki/experiments/exp-2026-04-19.md frontmatter points to forward_v1.
    Action: DO NOT auto-edit the frontmatter's `confidence: verified` field.
    wiki-sync is expected to have already flagged this as stale. If so, it is
    already `stale: true` and awaits researcher action.
    wiki-deepscan appends a note to wiki/questions.md ONLY if not already
    flagged by wiki-sync.

Writing ...
  - wiki/experiments/exp-2026-04-19.md: no change (stale flag already present
    from last wiki-sync run)
  + wiki/questions.md: 0 notes appended (dedup against existing wiki-sync note)

Full report: deep/deepscan-report-2026-04-27.md
```

The skill does not decide whether forward_v1 was renamed or replaced. It cites evidence (heuristic + similarity score) and leaves the decision to the researcher.

---

## Example 3 — Refusal: Understand-Anything not installed

```
> wiki-deepscan

wiki-deepscan: Understand-Anything not found.
  Checked $PATH for `understand-anything` → not found.
  Checked configured binary path in research-wiki.config.yaml
    (deepscan.tool_path: null)

This skill requires Understand-Anything. It does not fall back to another tool.

Install instructions (from upstream):
  https://github.com/Lum1104/Understand-Anything#installation

After installing, either:
  (a) ensure `understand-anything` is on your $PATH, or
  (b) set `deepscan.tool_path: /path/to/binary` in research-wiki.config.yaml.

Alternatives:
  - If you don't want to install Understand-Anything and only need code
    signatures for daily work, `wiki-sync` provides that via the Index Layer.
    The Deep Layer (deep/) stays empty until you run wiki-deepscan.

Aborting. No files written.
```

No partial output. `deep/` state preserved from previous runs (or stays empty if never run).

---

## Example 4 — Recovery: scan times out on a large module

The repo has a 40k-line auto-generated binding module that causes Understand-Anything to time out after 10 minutes (configured limit).

```
wiki-deepscan: Running understand-anything ...

  [progress streamed]
  Scanned: src/, wiki/, raw/ — 98 modules in 2m 40s.
  Scanning src/bindings/_generated.cpp (40,287 lines) ...
  [10m elapsed]
  TIMEOUT. Tool exit code 124.

Partial output detected in /tmp/ua-run-xyz/partial-graph.json.
  Nodes: 387 (missing ~25 from timed-out module)
  Edges: 1003 (missing ~80)

Decision: retain previous deep/knowledge-graph.json. Do NOT overwrite with
incomplete output.

Writing ...
  - deep/knowledge-graph.json      (unchanged; last successful scan preserved)
  - deep/last-scan.yaml            (unchanged)
  + deep/deepscan-report-2026-04-27.md  (timeout report)
  + wiki/questions.md              (1 note appended)

Final report:

  Scan incomplete after 10m (timeout).
  Partial results not applied. Previous deep/ state preserved.

  Timed-out module: src/bindings/_generated.cpp (40,287 lines).

  Suggested remediation:
    (a) Add to deepscan.ignore list in research-wiki.config.yaml if this file
        is auto-generated and not worth analyzing.
    (b) Increase deepscan.timeout from 600s if you want to wait it out.
    (c) Use --scope to restrict this run:
          > wiki-deepscan --scope src/ --exclude 'src/bindings/*'
```

The researcher adds the generated file to the ignore list and re-runs — success in 3m.
