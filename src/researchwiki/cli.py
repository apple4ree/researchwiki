"""CLI entry points for ResearchWiki tools.

Implemented (v0.1):
- `wiki-init`
- `wiki-log`     (5 subcommands; LLM-driven conversation, Python-driven I/O)
- `wiki-sync`
- `wiki-lint`
- `wiki-deepscan`
- `wiki-query`
- `wiki-recall`
- `wiki-fix-stale`
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from researchwiki.deepscan import run_deepscan
from researchwiki.fixstale import run_fix_stale
from researchwiki.init import run_init
from researchwiki.lint import run_lint
from researchwiki.log import (
    LogPayload,
    find_amend_target,
    find_pages,
    inspect_template,
    lookup_code_symbols,
    run_log,
)
from researchwiki.query import format_results as format_query_results
from researchwiki.query import load_pages, search
from researchwiki.recall import format_results as format_recall_results
from researchwiki.recall import run_recall
from researchwiki.sync import run_sync


def sync_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-sync",
        description="Regenerate the Index Layer and flag stale wiki refs.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the target ResearchWiki repository (default: cwd).",
    )
    parser.add_argument(
        "--no-stale-check",
        action="store_true",
        help="Skip the wiki-frontmatter stale-link pass; just regenerate index/.",
    )
    parser.add_argument(
        "--scan-body",
        action="store_true",
        help=(
            "Also scan wiki page bodies for identifier-shape tokens missing from "
            "the index (heuristic; records body_stale_mentions in frontmatter, "
            "implicitly [unverified] for downstream consumers)."
        ),
    )
    parser.add_argument(
        "--no-nag",
        action="store_true",
        help="Suppress the end-of-run reminder about old unresolved stale flags.",
    )
    parser.add_argument(
        "--nag-after-days",
        type=int,
        default=None,
        help="Override `sync.nag_after_days` (default 7). Set 0 to disable nagging.",
    )
    parser.add_argument(
        "--no-rename-heuristic",
        action="store_true",
        help="Disable the heuristic rename-detection pass on the symbol diff.",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-sync: repo not found: {repo}", file=sys.stderr)
        return 2

    kwargs = dict(
        no_stale_check=args.no_stale_check,
        scan_body=args.scan_body,
        no_nag=args.no_nag,
        rename_heuristic=not args.no_rename_heuristic,
    )
    if args.nag_after_days is not None:
        kwargs["nag_after_days"] = args.nag_after_days
    result = run_sync(repo, **kwargs)

    print(f"Snapshot written: {result.snapshot_path.relative_to(repo)}")
    print(f"Signatures: {result.signatures_path.relative_to(repo)}")
    print(f"Reverse refs: {result.reverse_refs_path.relative_to(repo)}")
    print(
        f"Symbols: +{result.symbols_added} -{result.symbols_removed} since last sync"
    )
    if result.stale_flagged:
        print(f"Stale wiki refs flagged: {result.stale_flagged}")
    if result.questions_appended:
        print(f"New questions appended to wiki/questions.md: {result.questions_appended}")
    if result.body_mentions_recorded:
        print(
            f"Body mentions recorded [unverified]: {result.body_mentions_recorded} "
            f"on {result.pages_with_body_mentions} page(s)"
        )
    if result.rename_candidates:
        print(f"Possible renames flagged [unverified]: {len(result.rename_candidates)} (see snapshot)")
    if result.scan_errors:
        print(f"Scan errors: {len(result.scan_errors)} (see snapshot)")
    if result.nag_message:
        print(result.nag_message)

    return 0


def lint_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-lint",
        description="Audit wiki health: 8 mechanical checks. Reports only; never modifies wiki.",
    )
    parser.add_argument("--repo", default=".", help="Path to the target ResearchWiki repository.")
    parser.add_argument(
        "--scope",
        default="all",
        help=(
            "Comma-separated check categories: "
            "all | frontmatter | links | speculation | stale | contradictions | orphans"
        ),
    )
    parser.add_argument("--strict", action="store_true", help="Escalate every finding to error severity.")
    parser.add_argument("--no-write", action="store_true", help="Dry-run; do not write audit report or appends.")
    parser.add_argument("--report-path", default=None, help="Override audit report destination.")
    parser.add_argument("--speculation-threshold", type=float, default=None)
    parser.add_argument("--stale-age-days", type=int, default=None)
    parser.add_argument("--stub-grace-days", type=int, default=None)
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-lint: repo not found: {repo}", file=sys.stderr)
        return 2

    scope = [s.strip() for s in args.scope.split(",") if s.strip()] if args.scope else None
    report_path = Path(args.report_path) if args.report_path else None

    kwargs = dict(
        scope=scope,
        strict=args.strict,
        no_write=args.no_write,
        report_path=report_path,
    )
    if args.speculation_threshold is not None:
        kwargs["speculation_threshold"] = args.speculation_threshold
    if args.stale_age_days is not None:
        kwargs["stale_age_days"] = args.stale_age_days
    if args.stub_grace_days is not None:
        kwargs["stub_grace_days"] = args.stub_grace_days

    try:
        result = run_lint(repo, **kwargs)
    except FileNotFoundError as e:
        print(f"wiki-lint: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"wiki-lint: {e}", file=sys.stderr)
        return 2

    counts = {"error": 0, "warn": 0, "info": 0}
    for f in result.findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    print(f"Lint audit complete. Pages scanned: {result.pages_scanned}")
    print(f"Findings: {counts['error']} error · {counts['warn']} warn · {counts['info']} info")
    if result.report_path:
        print(f"Full report: {result.report_path.relative_to(repo)}")
    if result.questions_appended:
        print(f"Appended {result.questions_appended} entries to wiki/questions.md")
    if result.discrepancies_appended:
        print(f"Appended {result.discrepancies_appended} entries to wiki/discrepancies.md")

    return result.exit_code


def deepscan_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-deepscan",
        description="Refresh the Deep Analysis Layer; seed wiki stubs for significant graph nodes.",
    )
    parser.add_argument("--repo", default=".", help="Path to the target ResearchWiki repository.")
    parser.add_argument("--from-graph", default=None,
                        help="Path to a pre-built knowledge-graph.json (skips invoking the external tool).")
    parser.add_argument("--no-seed-wiki", action="store_true",
                        help="Skip stub seeding and ref appends; just refresh deep/.")
    parser.add_argument("--stub-edge-threshold", type=int, default=None,
                        help="Inbound-edge threshold for stub seeding (default 3).")
    parser.add_argument("--scope", default=".", help="Glob/path to limit the scan.")
    parser.add_argument("--no-incremental", action="store_true", help="Disable --incremental hint to the external tool.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-deepscan: repo not found: {repo}", file=sys.stderr)
        return 2

    kwargs = dict(
        from_graph=Path(args.from_graph) if args.from_graph else None,
        seed_wiki=not args.no_seed_wiki,
        scope=args.scope,
        incremental=not args.no_incremental,
    )
    if args.stub_edge_threshold is not None:
        kwargs["stub_edge_threshold"] = args.stub_edge_threshold

    try:
        result = run_deepscan(repo, **kwargs)
    except FileNotFoundError as e:
        print(f"wiki-deepscan: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"wiki-deepscan: external tool failed: {e}", file=sys.stderr)
        return 1

    print(f"Knowledge graph: {result.graph_path.relative_to(repo)}")
    print(f"Last-scan: {result.last_scan_path.relative_to(repo)}")
    print(f"Stubs created: {len(result.stubs_created)}")
    print(f"Frontmatter ref appends: {len(result.frontmatter_appends)}")
    print(f"Naming conflicts: {len(result.naming_conflicts)}")
    print(f"Graph-vs-frontmatter discrepancies: {len(result.discrepancies)}")
    print(f"Report: {result.report_path.relative_to(repo)}")
    return 0


def query_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-query",
        description="Lexical search over wiki contents (BM25). Read-only.",
    )
    parser.add_argument("query", help="Query string. Quote if multi-word.")
    parser.add_argument("--repo", default=".", help="Path to the target ResearchWiki repository.")
    parser.add_argument("--top", type=int, default=10, help="Maximum number of results.")
    parser.add_argument("--scope", default="all",
                        choices=["all", "concepts", "papers", "experiments", "decisions"])
    parser.add_argument("--include-meta", action="store_true",
                        help="Also search wiki/{log,questions,discrepancies,index}.md")
    parser.add_argument("--frontmatter-only", action="store_true",
                        help="Restrict matching to frontmatter (refs, tags).")
    parser.add_argument("--no-stale-warnings", action="store_true",
                        help="Suppress the ⚠ stale: ... badge prefix.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-query: repo not found: {repo}", file=sys.stderr)
        return 2
    wiki = repo / "wiki"
    if not wiki.is_dir():
        print(f"wiki-query: `wiki/` does not exist under {repo}; run wiki-init first.", file=sys.stderr)
        return 2

    try:
        docs = load_pages(
            wiki, repo,
            scope=args.scope,
            include_meta=args.include_meta,
            frontmatter_only=args.frontmatter_only,
        )
    except ValueError as e:
        print(f"wiki-query: {e}", file=sys.stderr)
        return 2

    if not docs:
        print("wiki-query: no pages to search (empty wiki or all filtered out).", file=sys.stderr)
        return 1

    try:
        results = search(
            args.query, docs,
            top=args.top,
            stale_warnings=not args.no_stale_warnings,
        )
    except ValueError as e:
        print(f"wiki-query: {e}", file=sys.stderr)
        return 2

    print(format_query_results(results), end="")
    return 0 if results else 1


def recall_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-recall",
        description="Surface stale-but-relevant wiki pages relative to recent log activity.",
    )
    parser.add_argument("--repo", default=".", help="Path to the target ResearchWiki repository.")
    parser.add_argument("--lookback", type=int, default=30,
                        help="Days back in wiki/log.md to scan for recent activity.")
    parser.add_argument("--stale-since", type=int, default=60,
                        help="Minimum days since `updated:` to qualify as stale.")
    parser.add_argument("--top", type=int, default=10, help="Maximum number of results.")
    parser.add_argument("--scope", default="all",
                        choices=["all", "concepts", "papers", "experiments", "decisions"])
    parser.add_argument("--include-stubs", action="store_true",
                        help="Include `seeded_by:` / `authored_by: llm` empty-body stubs.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-recall: repo not found: {repo}", file=sys.stderr)
        return 2

    try:
        result = run_recall(
            repo,
            lookback_days=args.lookback,
            stale_since_days=args.stale_since,
            top=args.top,
            scope=args.scope,
            include_stubs=args.include_stubs,
        )
    except FileNotFoundError as e:
        print(f"wiki-recall: {e}", file=sys.stderr)
        return 1

    print(format_recall_results(result, lookback_days=args.lookback, stale_since_days=args.stale_since), end="")
    return 0 if result.results else 1


def fix_stale_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-fix-stale",
        description="Walk unresolved stale wiki refs interactively; apply per-occurrence-approved body edits.",
    )
    parser.add_argument("--repo", default=".", help="Path to the target ResearchWiki repository.")
    parser.add_argument("--page", default=None,
                        help="Restrict the run to a single page (repo-relative path, e.g. wiki/concepts/foo.md).")
    parser.add_argument("--no-auto-clear-flags", action="store_true",
                        help="Keep `stale: true` even after all occurrences on a page are addressed.")
    parser.add_argument("--no-body-mentions", action="store_true",
                        help="Skip walking `body_stale_mentions:` entries.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-fix-stale: repo not found: {repo}", file=sys.stderr)
        return 2

    def cli_display(message: str) -> None:
        print(message)

    def cli_prompt(message: str) -> str:
        print(message)
        return input("> ")

    try:
        result = run_fix_stale(
            repo,
            prompt_fn=cli_prompt,
            display_fn=cli_display,
            auto_clear_flags=not args.no_auto_clear_flags,
            include_body_mentions=not args.no_body_mentions,
            page_filter=args.page,
        )
    except FileNotFoundError as e:
        print(f"wiki-fix-stale: {e}", file=sys.stderr)
        return 2

    print()
    print(f"Pages walked:           {result.pages_walked}")
    print(f"Pages fully cleared:    {result.pages_fully_cleared}")
    print(f"Pages partially handled: {result.pages_partial}")
    print(f"Pages discarded:        {result.pages_discarded}")
    print(f"Body edits applied:     {result.body_edits_applied}")
    print(f"Stale flags cleared:    {result.stale_flags_cleared}")
    print(f"Body mentions resolved: {result.body_mentions_resolved}")
    if result.log_record_appended:
        print("Session recorded in wiki/log.md")
    return 0


def init_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-init",
        description="Bootstrap a repository into a ResearchWiki workspace. Idempotent.",
    )
    parser.add_argument("target", nargs="?", default=".",
                        help="Target repository path (default: cwd).")
    parser.add_argument("--mode", default="new", choices=["new", "adopt"],
                        help="`new` for a clean repo; `adopt` to wrap around existing content.")
    parser.add_argument("--language", default="ko",
                        help="Sets `language.default` in the initial config (and selects bundled templates).")
    parser.add_argument("--deepscan-tool", default="understand-anything",
                        choices=["understand-anything", "none"],
                        help="Sets `deepscan.tool` in the initial config.")
    parser.add_argument("--seed-from", default=None,
                        help="Optional path to existing notes; recorded in the first log entry only.")
    parser.add_argument("--bundle-path", default=None,
                        help="Override the wiki-init reference bundle location.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip confirmation prompt (useful for scripts).")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()

    def cli_display(message: str) -> None:
        print(message)

    def cli_prompt(message: str) -> str:
        print(message)
        return input("> ")

    try:
        result = run_init(
            target,
            mode=args.mode,
            language=args.language,
            deepscan_tool=args.deepscan_tool,
            seed_from=Path(args.seed_from) if args.seed_from else None,
            bundle_path=Path(args.bundle_path) if args.bundle_path else None,
            prompt_fn=cli_prompt,
            display_fn=cli_display,
            auto_confirm=args.yes,
        )
    except FileNotFoundError as e:
        print(f"wiki-init: {e}", file=sys.stderr)
        return 2

    if result.aborted:
        print(f"wiki-init: aborted ({result.abort_reason})", file=sys.stderr)
        return 1
    return 0


def log_main(argv: list[str] | None = None) -> int:
    """Toolkit CLI for the LLM-driven wiki-log skill.

    Subcommands (all emit JSON on stdout for LLM consumption):

      inspect           — parse template, compute would-be path, surface workspace state
      lookup-symbols    — which tokens hit index/signatures.json
      find-pages        — which slugs/IDs exist under wiki/<kind>/
      find-amend-target — most-recent same-type entry within window
      run               — atomic write phase from a single payload JSON

    The *conversation* (interview, P8 detection, identifier extraction,
    stub suggestion, summary writing) is the LLM's job per
    `skills/wiki-log/SKILL.md` — this CLI executes only the deterministic
    file-system operations.
    """
    parser = argparse.ArgumentParser(
        prog="wiki-log",
        description="wiki-log mechanical toolkit (LLM drives the conversation; this CLI does the I/O).",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_inspect = sub.add_parser("inspect", help="Parse template + compute would-be entry path.")
    p_inspect.add_argument("--repo", default=".", help="Workspace root (default: cwd).")
    p_inspect.add_argument("--type", required=True, choices=["experiment", "paper", "decision", "free"])
    p_inspect.add_argument("--title", required=True, help="Slug for filename + placeholder substitution.")
    p_inspect.add_argument("--today", default=None, help="ISO date override (default: today).")
    p_inspect.add_argument("--session-id", default=None, help="Override default session id.")
    p_inspect.add_argument("--git-ref", default=None, help="Override detected HEAD short-SHA.")

    p_lookup = sub.add_parser("lookup-symbols", help="Match tokens against index/signatures.json.")
    p_lookup.add_argument("--repo", default=".")
    p_lookup.add_argument("--tokens", default=None,
                          help="Comma-separated token list. Mutually exclusive with --tokens-file.")
    p_lookup.add_argument("--tokens-file", default=None,
                          help="Path to a file with one token per line.")

    p_find = sub.add_parser("find-pages", help="Exact-slug match against wiki/<kind>/.")
    p_find.add_argument("--repo", default=".")
    p_find.add_argument("--kind", required=True,
                        choices=["concepts", "papers", "experiments", "decisions"])
    p_find.add_argument("--ids", default=None, help="Comma-separated id list. Or use --ids-file.")
    p_find.add_argument("--ids-file", default=None, help="Path to a file with one id per line.")

    p_amend = sub.add_parser("find-amend-target", help="Find the most-recent same-type entry in window.")
    p_amend.add_argument("--repo", default=".")
    p_amend.add_argument("--type", required=True, choices=["experiment", "paper", "decision", "free"])
    p_amend.add_argument("--window-hours", type=int, default=24)

    p_run = sub.add_parser("run", help="Atomic write phase from payload JSON.")
    p_run.add_argument("--repo", default=".")
    p_run.add_argument("--payload", required=True, help="Path to payload JSON file (or '-' for stdin).")

    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"wiki-log: repo not found: {repo}", file=sys.stderr)
        return 2

    try:
        if args.subcommand == "inspect":
            today = _date.fromisoformat(args.today) if args.today else None
            result = inspect_template(
                repo, type=args.type, title=args.title,
                today=today, session_id=args.session_id, git_ref=args.git_ref,
            )
            json.dump(result.to_json(), sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.subcommand == "lookup-symbols":
            tokens = _read_tokens(args.tokens, args.tokens_file)
            results = lookup_code_symbols(repo, tokens=tokens)
            json.dump([m.to_json() for m in results], sys.stdout,
                      ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.subcommand == "find-pages":
            ids = _read_tokens(args.ids, args.ids_file)
            results = find_pages(repo, kind=args.kind, ids=ids)
            json.dump([p.to_json() for p in results], sys.stdout,
                      ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.subcommand == "find-amend-target":
            target = find_amend_target(
                repo, type=args.type, window_hours=args.window_hours,
            )
            payload_out = target.to_json() if target else None
            json.dump(payload_out, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0 if target else 1

        if args.subcommand == "run":
            if args.payload == "-":
                data = json.load(sys.stdin)
            else:
                data = json.loads(Path(args.payload).read_text(encoding="utf-8"))
            payload = LogPayload.from_json(data)
            result = run_log(repo, payload=payload)
            json.dump(result.to_json(), sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"wiki-log: {e}", file=sys.stderr)
        return 2

    return 2  # unreachable


def _read_tokens(inline: str | None, file: str | None) -> list[str]:
    if inline and file:
        raise ValueError("--tokens / --ids and --tokens-file / --ids-file are mutually exclusive")
    if file:
        text = Path(file).read_text(encoding="utf-8")
        return [t.strip() for t in text.splitlines() if t.strip()]
    if inline:
        return [t.strip() for t in inline.split(",") if t.strip()]
    return []


def main(argv: list[str] | None = None) -> int:
    """Top-level dispatcher for `python -m researchwiki <subcommand>`."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: python -m researchwiki <subcommand> [args...]", file=sys.stderr)
        print("subcommands:", file=sys.stderr)
        print("  init       Bootstrap a workspace (one-time)", file=sys.stderr)
        print("  log        Add a journal entry (LLM-driven; CLI does I/O)", file=sys.stderr)
        print("  sync       Regenerate the Index Layer", file=sys.stderr)
        print("  lint       Audit wiki health (8 mechanical checks)", file=sys.stderr)
        print("  deepscan   Refresh the Deep Analysis Layer + seed stubs", file=sys.stderr)
        print("  query      Lexical search (BM25)", file=sys.stderr)
        print("  recall     Surface stale-but-relevant pages", file=sys.stderr)
        print("  fix-stale  Walk unresolved stale refs interactively (P3 carve-out)", file=sys.stderr)
        return 2

    sub = argv[0]
    rest = argv[1:]
    if sub == "init":
        return init_main(rest)
    if sub == "log":
        return log_main(rest)
    if sub == "sync":
        return sync_main(rest)
    if sub == "lint":
        return lint_main(rest)
    if sub == "deepscan":
        return deepscan_main(rest)
    if sub == "query":
        return query_main(rest)
    if sub == "recall":
        return recall_main(rest)
    if sub == "fix-stale":
        return fix_stale_main(rest)

    print(f"unknown subcommand: {sub}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
