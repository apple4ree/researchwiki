"""wiki-deepscan — wrapper around an external knowledge-graph tool
(typically Understand-Anything).

Responsibilities (per `wiki-deepscan/SPEC.md`):

1. Run the external tool (or load a pre-built graph for tests).
2. Parse the knowledge graph.
3. Seed stub wiki pages for architecturally significant components
   that don't yet have one.
4. Append verified `refs.code` entries to existing wiki pages whose
   concept maps to a graph node with newly-revealed bindings.
5. Detect graph-vs-frontmatter discrepancies; log them to
   `wiki/discrepancies.md` (never auto-correct).
6. Detect naming conflicts (would-create-stub but path already taken
   with a different concept); log to `wiki/questions.md`.
7. Write `deep/knowledge-graph.json`, `deep/last-scan.yaml`, and a
   per-run report at `deep/deepscan-report-<date>.md`.

Body of existing wiki pages is never touched (P3). Stub bodies contain
only structural facts from the graph plus a fixed open-questions
template — never LLM-authored prose about purpose / quality / design (P8).

Tests do not require Understand-Anything; pass `--from-graph` (or use
the `from_graph` keyword) to load a pre-built JSON.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from researchwiki.lint.runner import _split_frontmatter

DEFAULT_STUB_EDGE_THRESHOLD = 3


# ---------------------------------------------------------------------
# Graph schema (parsed from the external tool's output).
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class GraphNode:
    path: str
    name: str
    kind: str
    symbols: tuple[str, ...]
    inbound_edges: int
    inbound_callers: tuple[dict, ...]
    outbound_dependencies: tuple[dict, ...]
    architecturally_significant: bool
    suggested_slug: str

    @classmethod
    def from_json(cls, data: dict) -> "GraphNode":
        return cls(
            path=str(data.get("path", "")),
            name=str(data.get("name", "")),
            kind=str(data.get("kind", "")),
            symbols=tuple(data.get("symbols", []) or []),
            inbound_edges=int(data.get("inbound_edges", 0)),
            inbound_callers=tuple(data.get("inbound_callers", []) or []),
            outbound_dependencies=tuple(data.get("outbound_dependencies", []) or []),
            architecturally_significant=bool(data.get("architecturally_significant", False)),
            suggested_slug=str(data.get("suggested_slug", "")),
        )


@dataclass(frozen=True)
class KnowledgeGraph:
    schema_version: int
    generated_at: str
    git_ref: str
    tool: str
    tool_version: str
    scope: str
    nodes: tuple[GraphNode, ...]
    edges_total: int

    @classmethod
    def from_json(cls, data: dict) -> "KnowledgeGraph":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            generated_at=str(data.get("generated_at", "")),
            git_ref=str(data.get("git_ref", "")),
            tool=str(data.get("tool", "understand-anything")),
            tool_version=str(data.get("tool_version", "")),
            scope=str(data.get("scope", ".")),
            nodes=tuple(GraphNode.from_json(n) for n in data.get("nodes", [])),
            edges_total=int(data.get("edges_total", 0)),
        )


# ---------------------------------------------------------------------
# Result + entry point
# ---------------------------------------------------------------------


@dataclass
class StubCreated:
    page_path: Path
    slug: str
    suggested_from: str  # original src path or symbol


@dataclass
class NamingConflict:
    target_path: Path
    existing_refs_paths: tuple[str, ...]
    incoming_path: str


@dataclass
class Discrepancy:
    page_path: Path
    symbol: str
    frontmatter_path: str
    graph_path: str


@dataclass
class FrontmatterRefAppend:
    page_path: Path
    added_refs: tuple[dict, ...]  # the new entries we appended


@dataclass
class DeepscanResult:
    graph_path: Path
    last_scan_path: Path
    report_path: Path
    stubs_created: list[StubCreated] = field(default_factory=list)
    naming_conflicts: list[NamingConflict] = field(default_factory=list)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    frontmatter_appends: list[FrontmatterRefAppend] = field(default_factory=list)


def run_deepscan(
    repo_root: Path,
    *,
    from_graph: Path | None = None,
    seed_wiki: bool = True,
    stub_edge_threshold: int = DEFAULT_STUB_EDGE_THRESHOLD,
    tool_path: str | None = None,
    scope: str = ".",
    incremental: bool = True,
) -> DeepscanResult:
    """Run wiki-deepscan against `repo_root`.

    If `from_graph` is provided, load the graph JSON from that path
    (skips the external tool invocation; used for testing). Otherwise,
    invoke the external tool — `tool_path` overrides $PATH lookup.

    Raises:
        FileNotFoundError: target repo missing or external tool absent.
    """
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_root not found: {repo_root}")

    deep_dir = repo_root / "deep"
    deep_dir.mkdir(exist_ok=True)
    wiki_dir = repo_root / "wiki"

    graph_output_path = deep_dir / "knowledge-graph.json"

    if from_graph is not None:
        # Test path / pre-built graph: copy into deep/.
        shutil.copy(from_graph, graph_output_path)
    else:
        _invoke_tool(
            tool_path=tool_path,
            output_path=graph_output_path,
            repo_root=repo_root,
            scope=scope,
            incremental=incremental,
            last_scan_path=deep_dir / "last-scan.yaml",
        )

    graph = KnowledgeGraph.from_json(json.loads(graph_output_path.read_text(encoding="utf-8")))

    # Phase 1: seed stubs and detect naming conflicts.
    stubs: list[StubCreated] = []
    conflicts: list[NamingConflict] = []
    appends: list[FrontmatterRefAppend] = []
    if seed_wiki and wiki_dir.exists():
        stubs, conflicts, appends = _process_graph(
            graph=graph,
            wiki_dir=wiki_dir,
            repo_root=repo_root,
            stub_edge_threshold=stub_edge_threshold,
        )

    # Phase 2: detect graph-vs-frontmatter discrepancies (against ALL existing pages).
    discrepancies: list[Discrepancy] = []
    if wiki_dir.exists():
        discrepancies = _detect_discrepancies(graph, wiki_dir, repo_root)

    # Phase 3: write deep/last-scan.yaml.
    last_scan_path = _write_last_scan(deep_dir, graph)

    # Phase 4: log conflicts to wiki/questions.md, discrepancies to wiki/discrepancies.md.
    if wiki_dir.exists():
        if conflicts:
            _append_naming_conflicts(wiki_dir / "questions.md", conflicts)
        if discrepancies:
            _append_discrepancies(wiki_dir / "discrepancies.md", discrepancies)

    # Phase 5: write per-run report.
    report_path = _write_report(
        deep_dir=deep_dir,
        graph=graph,
        stubs=stubs,
        conflicts=conflicts,
        discrepancies=discrepancies,
        appends=appends,
    )

    return DeepscanResult(
        graph_path=graph_output_path,
        last_scan_path=last_scan_path,
        report_path=report_path,
        stubs_created=stubs,
        naming_conflicts=conflicts,
        discrepancies=discrepancies,
        frontmatter_appends=appends,
    )


# ---------------------------------------------------------------------
# External tool invocation
# ---------------------------------------------------------------------


def _invoke_tool(
    *,
    tool_path: str | None,
    output_path: Path,
    repo_root: Path,
    scope: str,
    incremental: bool,
    last_scan_path: Path,
) -> None:
    binary = tool_path or shutil.which("understand-anything")
    if not binary:
        raise FileNotFoundError(
            "understand-anything binary not found. Install Understand-Anything "
            "(https://github.com/Lum1104/Understand-Anything) and either ensure "
            "it is on $PATH or set deepscan.tool_path in research-wiki.config.yaml. "
            "wiki-deepscan does not fall back to another tool."
        )

    # The exact UA CLI is upstream-defined; this is the assumed contract.
    # A researcher whose UA version uses different flags can wrap it in a
    # shell script and point `tool_path` at the wrapper.
    cmd = [binary, "scan", "--repo", str(repo_root), "--output", str(output_path)]
    if scope and scope != ".":
        cmd += ["--scope", scope]
    if incremental and last_scan_path.exists():
        cmd += ["--incremental", "--from", str(last_scan_path)]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"understand-anything failed (exit {e.returncode}):\n{e.stderr}"
        ) from e


# ---------------------------------------------------------------------
# Phase 1: stub seeding + naming-conflict detection + ref appends
# ---------------------------------------------------------------------


def _process_graph(
    *,
    graph: KnowledgeGraph,
    wiki_dir: Path,
    repo_root: Path,
    stub_edge_threshold: int,
) -> tuple[list[StubCreated], list[NamingConflict], list[FrontmatterRefAppend]]:
    stubs: list[StubCreated] = []
    conflicts: list[NamingConflict] = []
    appends: list[FrontmatterRefAppend] = []

    # Build an index of existing wiki pages → their refs.code paths.
    pages_by_path: dict[Path, dict] = {}
    for md in sorted(wiki_dir.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        frontmatter, _body, _err = _split_frontmatter(text)
        pages_by_path[md] = frontmatter

    for node in graph.nodes:
        if not node.architecturally_significant:
            continue
        if node.inbound_edges < stub_edge_threshold:
            continue
        slug = node.suggested_slug or _slugify(node.name)
        if not slug:
            continue
        target = wiki_dir / "concepts" / f"{slug}.md"

        if target.exists():
            # Either a same-concept page (append refs) or a name collision.
            existing_fm = pages_by_path.get(target, {})
            existing_paths = _existing_code_ref_paths(existing_fm)
            if node.path in existing_paths:
                # Same concept — append any new symbols not already declared.
                appended = _append_refs_to_existing(target, existing_fm, node)
                if appended:
                    appends.append(FrontmatterRefAppend(page_path=target, added_refs=appended))
            else:
                # Different concept lives at this slug.
                conflicts.append(NamingConflict(
                    target_path=target,
                    existing_refs_paths=tuple(sorted(existing_paths)),
                    incoming_path=node.path,
                ))
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_stub(node, slug), encoding="utf-8")
        stubs.append(StubCreated(page_path=target, slug=slug, suggested_from=node.path))

    return stubs, conflicts, appends


def _existing_code_ref_paths(frontmatter: dict) -> set[str]:
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return set()
    code = refs.get("code")
    if not isinstance(code, list):
        return set()
    out: set[str] = set()
    for r in code:
        if isinstance(r, dict):
            p = r.get("path")
            if isinstance(p, str):
                out.add(p)
    return out


def _existing_code_ref_keys(frontmatter: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return out
    code = refs.get("code")
    if not isinstance(code, list):
        return out
    for r in code:
        if isinstance(r, dict):
            p = r.get("path")
            s = r.get("symbol")
            if isinstance(p, str) and isinstance(s, str):
                out.add((p, s))
    return out


def _append_refs_to_existing(
    page_path: Path,
    existing_fm: dict,
    node: GraphNode,
) -> tuple[dict, ...]:
    """Append any symbols from `node` that the page's `refs.code` does
    not yet list. Frontmatter-only edit (P3-permitted)."""
    existing_keys = _existing_code_ref_keys(existing_fm)
    new_entries: list[dict] = []
    for symbol in node.symbols:
        key = (node.path, symbol)
        if key in existing_keys:
            continue
        new_entries.append({
            "path": node.path,
            "symbol": symbol,
            "confidence": "verified",
        })
    if not new_entries:
        return ()

    text = page_path.read_text(encoding="utf-8")
    fm, body, _err = _split_frontmatter(text)
    if not isinstance(fm.get("refs"), dict):
        fm["refs"] = {"code": [], "papers": [], "concepts": [], "experiments": []}
    if not isinstance(fm["refs"].get("code"), list):
        fm["refs"]["code"] = []
    fm["refs"]["code"].extend(new_entries)

    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    page_path.write_text(f"---\n{new_yaml}---\n{body}", encoding="utf-8")
    return tuple(new_entries)


# ---------------------------------------------------------------------
# Phase 2: graph-vs-frontmatter discrepancy detection
# ---------------------------------------------------------------------


def _detect_discrepancies(
    graph: KnowledgeGraph,
    wiki_dir: Path,
    repo_root: Path,
) -> list[Discrepancy]:
    """Find wiki pages whose `refs.code[].symbol` matches a symbol that
    the graph reports at a *different* path. The page's frontmatter is
    not auto-corrected — discrepancies are surfaced for the researcher.
    """
    # Index: symbol_name → list of (graph_node.path)
    symbol_to_paths: dict[str, set[str]] = {}
    for node in graph.nodes:
        for symbol in node.symbols:
            symbol_to_paths.setdefault(symbol, set()).add(node.path)
            # Also handle "Class.method" form vs "method" alone.
            if "." in symbol:
                _, last = symbol.rsplit(".", 1)
                symbol_to_paths.setdefault(last, set()).add(node.path)

    out: list[Discrepancy] = []
    for md in sorted(wiki_dir.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, _body, _err = _split_frontmatter(text)
        for path, symbol in _existing_code_ref_keys(fm):
            graph_paths = symbol_to_paths.get(symbol, set())
            if not graph_paths:
                continue  # symbol absent from graph — wiki-sync's stale-flag job, not ours
            if path in graph_paths:
                continue  # consistent
            for graph_path in sorted(graph_paths):
                out.append(Discrepancy(
                    page_path=md,
                    symbol=symbol,
                    frontmatter_path=path,
                    graph_path=graph_path,
                ))
    return out


# ---------------------------------------------------------------------
# Stub rendering (structural facts only — no purpose prose, P8)
# ---------------------------------------------------------------------


def _render_stub(node: GraphNode, slug: str) -> str:
    today = datetime.now().date().isoformat()
    fm = {
        "schema_version": 1,
        "type": "concept",
        "created": today,
        "updated": today,
        "tags": ["auto-seeded"],
        "refs": {
            "code": [
                {"path": node.path, "symbol": s, "confidence": "verified"}
                for s in node.symbols
            ],
            "papers": [],
            "concepts": [],
            "experiments": [],
        },
        "authored_by": "llm",
        "source_sessions": [f"deepscan-{datetime.now().strftime('%Y%m%d-%H%M')}"],
        "seeded_by": "wiki-deepscan",
        "seed_context": {
            "from_path": node.path,
            "inbound_edges": node.inbound_edges,
        },
    }
    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)

    # Body: structural facts only, no prose about purpose.
    callers_block = "\n".join(
        f"- `{c.get('path', '?')}` at line(s) {', '.join(str(l) for l in c.get('lines', []))}"
        for c in node.inbound_callers[:10]
    )
    if len(node.inbound_callers) > 10:
        callers_block += f"\n- ({len(node.inbound_callers) - 10} more — see deep/knowledge-graph.json)"
    if not callers_block.strip():
        callers_block = "(no inbound callers recorded by the graph)"

    deps_block = "\n".join(
        f"- `{d.get('path', '?')}`"
        + (f":`{d['symbol']}`" if d.get("symbol") else "")
        + (" *(external)*" if d.get("external") else "")
        for d in node.outbound_dependencies[:10]
    )
    if not deps_block.strip():
        deps_block = "(no outbound dependencies recorded by the graph)"

    symbols_block = "\n".join(f"- `{s}` ({node.kind if i == 0 else 'symbol'})"
                              for i, s in enumerate(node.symbols))
    if not symbols_block.strip():
        symbols_block = "(no symbols recorded by the graph)"

    body = (
        f"# {node.name}\n\n"
        f"## Structural facts (auto-generated)\n\n"
        f"This component lives at `{node.path}`. It exposes:\n\n"
        f"{symbols_block}\n\n"
        f"According to the code graph, it is called by ({node.inbound_edges} inbound edges):\n\n"
        f"{callers_block}\n\n"
        f"It depends on:\n\n"
        f"{deps_block}\n\n"
        f"## Notes from researcher\n\n"
        f"*Empty — add your interpretation here.*\n\n"
        f"## Open questions for researcher\n\n"
        f"- What problem does this component solve?\n"
        f"- What alternatives were considered?\n"
        f"- What are its failure modes?\n"
    )
    return f"---\n{fm_yaml}---\n\n{body}"


def _slugify(name: str) -> str:
    out: list[str] = []
    last_was_dash = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            last_was_dash = False
        elif not last_was_dash and out:
            out.append("-")
            last_was_dash = True
    while out and out[-1] == "-":
        out.pop()
    return "".join(out)


# ---------------------------------------------------------------------
# Phase 3: deep/last-scan.yaml + Phase 5: deepscan-report-<date>.md
# ---------------------------------------------------------------------


def _write_last_scan(deep_dir: Path, graph: KnowledgeGraph) -> Path:
    path = deep_dir / "last-scan.yaml"
    payload = {
        "scanned_at": graph.generated_at or datetime.now().astimezone().isoformat(),
        "git_ref": graph.git_ref,
        "scope": graph.scope,
        "tool": graph.tool,
        "tool_version": graph.tool_version,
        "nodes": len(graph.nodes),
        "edges": graph.edges_total,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _write_report(
    *,
    deep_dir: Path,
    graph: KnowledgeGraph,
    stubs: list[StubCreated],
    conflicts: list[NamingConflict],
    discrepancies: list[Discrepancy],
    appends: list[FrontmatterRefAppend],
) -> Path:
    now = datetime.now()
    name = f"deepscan-report-{now.strftime('%Y%m%d_%H%M')}.md"
    path = deep_dir / name

    stubs_block = "\n".join(
        f"- `{_rel(s.page_path, deep_dir.parent)}` (suggested from `{s.suggested_from}`)"
        for s in stubs
    ) if stubs else "(none)"

    conflicts_block = "\n".join(
        f"- `{_rel(c.target_path, deep_dir.parent)}` already exists with refs to "
        f"{', '.join(f'`{p}`' for p in c.existing_refs_paths)}; would not overwrite "
        f"with `{c.incoming_path}`."
        for c in conflicts
    ) if conflicts else "(none)"

    discrepancies_block = "\n".join(
        f"- `{_rel(d.page_path, deep_dir.parent)}` declares `{d.frontmatter_path}:{d.symbol}`; "
        f"graph reports symbol at `{d.graph_path}`."
        for d in discrepancies
    ) if discrepancies else "(none)"

    appends_block = "\n".join(
        f"- `{_rel(a.page_path, deep_dir.parent)}` (+{len(a.added_refs)} refs)"
        for a in appends
    ) if appends else "(none)"

    body = (
        f"# Deepscan report — {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"_Generated by wiki-deepscan._\n\n"
        f"## Graph summary\n"
        f"- Tool: {graph.tool} {graph.tool_version}\n"
        f"- Git ref: {graph.git_ref}\n"
        f"- Scope: {graph.scope}\n"
        f"- Nodes: {len(graph.nodes)}\n"
        f"- Edges: {graph.edges_total}\n\n"
        f"## New stubs created\n{stubs_block}\n\n"
        f"## Frontmatter ref appends to existing pages\n{appends_block}\n\n"
        f"## Naming conflicts (skipped, logged to wiki/questions.md)\n{conflicts_block}\n\n"
        f"## Graph vs frontmatter discrepancies (logged to wiki/discrepancies.md)\n{discrepancies_block}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------
# Phase 4: appends to questions.md / discrepancies.md
# ---------------------------------------------------------------------


def _append_naming_conflicts(questions_md: Path, conflicts: list[NamingConflict]) -> int:
    if not conflicts:
        return 0
    questions_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block_lines = [f"\n## [{timestamp}] from wiki-deepscan\n"]
    for c in conflicts:
        block_lines.append(
            f"**Naming conflict:** wiki-deepscan would create "
            f"`{c.target_path.relative_to(questions_md.parent.parent.parent) if False else c.target_path}` "
            f"for `{c.incoming_path}`, but a page already exists at that slug with refs to "
            f"{', '.join(f'`{p}`' for p in c.existing_refs_paths)}.\n\n"
            f"**Action needed:** rename one, merge, or accept as distinct concepts."
        )
    existing = questions_md.read_text(encoding="utf-8") if questions_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    questions_md.write_text(existing + "\n".join(block_lines) + "\n", encoding="utf-8")
    return len(conflicts)


def _append_discrepancies(discrepancies_md: Path, items: list[Discrepancy]) -> int:
    if not items:
        return 0
    discrepancies_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block_lines = [f"\n## [{timestamp}] from wiki-deepscan\n"]
    for d in items:
        block_lines.append(
            f"**Graph vs frontmatter mismatch:** `{d.page_path.name}` declares "
            f"`{d.frontmatter_path}:{d.symbol}`; the knowledge graph reports the same "
            f"symbol at `{d.graph_path}`.\n\n"
            f"**Action needed:** researcher to decide which is canonical."
        )
    existing = discrepancies_md.read_text(encoding="utf-8") if discrepancies_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    discrepancies_md.write_text(existing + "\n".join(block_lines) + "\n", encoding="utf-8")
    return len(items)
