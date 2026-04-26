"""Sync orchestrator — `wiki-sync` v0.2.

Walks the repository, dispatches files to per-extension scanners,
builds `signatures.json` + `reverse_refs.json` + a per-run snapshot
markdown file, runs the stale-link pass against `wiki/` frontmatter,
and appends new stale-ref questions to `wiki/questions.md`.

v0.2 features:
- `--scan-body` body link rot scan that records `body_stale_mentions:`
  in frontmatter for body tokens missing from the index.
- Rename heuristic — pairs added × removed symbols by file + line
  proximity + `difflib.SequenceMatcher` signature similarity. Output
  in snapshot's "Possible renames (heuristic, [unverified])" section.
- End-of-run nag — surface unresolved `stale: true` flags older than
  `sync.nag_after_days` (default 7). Suppress via `--no-nag`.

Still pending (v1.x):
- Tree-sitter scanners for non-Python languages.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from researchwiki import frontmatter as fm
from researchwiki.scanner import ScanError, Symbol, scan_file
from researchwiki.scanner.registry import is_supported

DEFAULT_RENAME_SIMILARITY = 0.80
DEFAULT_RENAME_LINE_WINDOW = 10
DEFAULT_NAG_AFTER_DAYS = 7

# Body link rot tokenizer (heuristic). Three patterns, OR'd:
#   1. Multi-cap PascalCase identifier (e.g., OldAttention, MultiHeadAttention).
#      Matches any name with at least two distinct capital letters separated by
#      lowercase — distinguishes code symbols from common English words like
#      "Use", "Set", "Hello" which have only a single capital.
#   2. Dotted PascalCase (e.g., Trainer.train_one_epoch) — clear method-access
#      signal even when the class name on its own is a single-cap word.
#   3. Anything followed by `(` — clear call signal, covers snake_case +
#      single-cap PascalCase function calls.
# Word boundary on the left prevents matching `mySomething` mid-word.
_BODY_TOKEN_RE = re.compile(
    r"(?<!\w)"
    r"(?:"
    r"[A-Z][a-z0-9_]*[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]+)*"
    r"|"
    r"[A-Z][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]+"
    r"|"
    r"[A-Za-z_][A-Za-z0-9_]+\("
    r")"
)

# Always-skip directory names.
DEFAULT_IGNORE_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "index",   # wiki-sync's own outputs
    "deep",    # wiki-deepscan's outputs
})

DEFAULT_IGNORE_FILES = frozenset({".DS_Store"})


@dataclass(frozen=True)
class RenameCandidate:
    """A heuristic match between a removed and an added symbol that may
    represent a rename. Always tagged `[unverified]`; the researcher
    decides whether the rename is real."""
    removed: Symbol
    added: Symbol
    similarity: float


@dataclass
class SyncResult:
    snapshot_path: Path
    signatures_path: Path
    reverse_refs_path: Path
    symbols_added: int
    symbols_removed: int
    stale_flagged: int
    questions_appended: int
    scan_errors: list[ScanError]
    body_mentions_recorded: int = 0
    pages_with_body_mentions: int = 0
    rename_candidates: list[RenameCandidate] = field(default_factory=list)
    nag_message: str | None = None


@dataclass
class SyncPaths:
    repo_root: Path
    wiki: Path
    index: Path
    raw: Path

    @classmethod
    def default(cls, repo_root: Path) -> "SyncPaths":
        return cls(
            repo_root=repo_root,
            wiki=repo_root / "wiki",
            index=repo_root / "index",
            raw=repo_root / "raw",
        )


def run_sync(
    repo_root: Path,
    *,
    no_stale_check: bool = False,
    scan_body: bool = False,
    no_nag: bool = False,
    nag_after_days: int = DEFAULT_NAG_AFTER_DAYS,
    rename_heuristic: bool = True,
    rename_similarity: float = DEFAULT_RENAME_SIMILARITY,
    rename_line_window: int = DEFAULT_RENAME_LINE_WINDOW,
    today: date | None = None,
) -> SyncResult:
    """End-to-end sync. Writes outputs under `<repo_root>/index/`.

    `scan_body=True` enables the optional body link rot pass that records
    `body_stale_mentions:` in frontmatter for prose tokens missing from
    the index. Heuristic; the entries carry `[unverified]` semantic for
    downstream consumers.

    Returns a `SyncResult` summarizing what changed and what failed.
    Raises `FileNotFoundError` if `repo_root` does not exist.
    """
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_root not found or not a directory: {repo_root}")

    paths = SyncPaths.default(repo_root)
    paths.index.mkdir(parents=True, exist_ok=True)
    (paths.index / "snapshots").mkdir(exist_ok=True)
    (paths.index / "audits").mkdir(exist_ok=True)

    # Phase 1 — scan source files for symbols.
    current_symbols, scan_errors = _scan_repo(paths)

    # Phase 2 — diff against previous signatures.json.
    previous_symbols = _load_previous_signatures(paths.index / "signatures.json")
    added, removed = _symbol_diff(previous_symbols, current_symbols)

    # Phase 2b — rename heuristic over the diff.
    rename_candidates: list[RenameCandidate] = []
    if rename_heuristic:
        rename_candidates = _detect_rename_candidates(
            added=added, removed=removed,
            line_window=rename_line_window,
            threshold=rename_similarity,
        )

    # Phase 3 — build reverse_refs from wiki/ frontmatter.
    reverse_refs, declared_refs = _build_reverse_refs(paths)

    # Phase 4 — stale-link pass (frontmatter refs).
    stale_flagged = 0
    questions_appended = 0
    if not no_stale_check and paths.wiki.exists():
        stale_flagged, questions_appended = _stale_link_pass(
            paths=paths,
            current_symbols=current_symbols,
            declared_refs=declared_refs,
            today=today or datetime.now().date(),
        )

    # Phase 4b — optional body link rot pass.
    body_mentions_recorded = 0
    pages_with_body_mentions = 0
    if scan_body and not no_stale_check and paths.wiki.exists():
        body_mentions_recorded, pages_with_body_mentions = _body_link_rot_pass(
            paths=paths,
            current_symbols=current_symbols,
            today=today or datetime.now().date(),
        )

    # Phase 5 — write outputs.
    signatures_path = _write_signatures(paths.index, current_symbols)
    reverse_refs_path = _write_reverse_refs(paths.index, reverse_refs)
    snapshot_path = _write_snapshot(
        paths=paths,
        current_symbols=current_symbols,
        added=added,
        removed=removed,
        scan_errors=scan_errors,
        rename_candidates=rename_candidates,
    )

    # Phase 6 — end-of-run nag for old unresolved stale flags.
    nag_message: str | None = None
    if not no_nag and not no_stale_check and paths.wiki.exists() and nag_after_days > 0:
        nag_message = _compute_nag_message(
            wiki_dir=paths.wiki,
            nag_after_days=nag_after_days,
            today=today or datetime.now().date(),
        )

    return SyncResult(
        snapshot_path=snapshot_path,
        signatures_path=signatures_path,
        reverse_refs_path=reverse_refs_path,
        symbols_added=len(added),
        symbols_removed=len(removed),
        stale_flagged=stale_flagged,
        questions_appended=questions_appended,
        scan_errors=scan_errors,
        body_mentions_recorded=body_mentions_recorded,
        pages_with_body_mentions=pages_with_body_mentions,
        rename_candidates=rename_candidates,
        nag_message=nag_message,
    )


# ---------- Phase 1: scan ----------


def _scan_repo(paths: SyncPaths) -> tuple[list[Symbol], list[ScanError]]:
    symbols: list[Symbol] = []
    errors: list[ScanError] = []

    wiki_relative = _relative_posix(paths.wiki, paths.repo_root) + "/"

    for file_path in _walk_repo(paths.repo_root):
        rel_posix = _relative_posix(file_path, paths.repo_root)
        if not is_supported(rel_posix):
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(ScanError(path=rel_posix, line=None, message=f"read failed: {e}"))
            continue

        file_syms, file_errs = scan_file(rel_posix, source, wiki_root=wiki_relative)
        symbols.extend(file_syms)
        errors.extend(file_errs)

    return symbols, errors


def _walk_repo(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place so os.walk skips them.
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
        for name in filenames:
            if name in DEFAULT_IGNORE_FILES:
                continue
            yield Path(dirpath) / name


# ---------- Phase 2: diff ----------


def _symbol_key(sym: Symbol) -> tuple[str, str, str | None, str]:
    return (sym.path, sym.name, sym.parent, sym.kind)


def _load_previous_signatures(path: Path) -> list[Symbol]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    syms: list[Symbol] = []
    for d in data.get("symbols", []):
        try:
            syms.append(Symbol(
                path=d["path"],
                name=d["name"],
                kind=d["kind"],
                signature=d.get("signature", ""),
                line=d.get("line", 0),
                confidence=d.get("confidence", "verified"),
                parent=d.get("parent"),
                extra=d.get("extra", {}) or {},
            ))
        except (KeyError, TypeError):
            continue
    return syms


def _symbol_diff(
    previous: list[Symbol],
    current: list[Symbol],
) -> tuple[list[Symbol], list[Symbol]]:
    prev_keys = {_symbol_key(s) for s in previous}
    curr_keys = {_symbol_key(s) for s in current}
    added = [s for s in current if _symbol_key(s) not in prev_keys]
    removed = [s for s in previous if _symbol_key(s) not in curr_keys]
    return added, removed


def _detect_rename_candidates(
    *,
    added: list[Symbol],
    removed: list[Symbol],
    line_window: int,
    threshold: float,
) -> list[RenameCandidate]:
    """Pair removed × added symbols heuristically.

    Match criteria (all must hold):
    - Same `path`.
    - `|added.line - removed.line| <= line_window`.
    - `difflib.SequenceMatcher(None, removed.signature, added.signature).ratio() >= threshold`.

    A removed symbol may match multiple added symbols and vice versa —
    the heuristic surfaces every plausible candidate; the researcher
    decides. Each candidate is implicitly `[unverified]`.
    """
    candidates: list[RenameCandidate] = []
    for r in removed:
        for a in added:
            if r.path != a.path:
                continue
            if abs(a.line - r.line) > line_window:
                continue
            ratio = difflib.SequenceMatcher(None, r.signature, a.signature).ratio()
            if ratio < threshold:
                continue
            candidates.append(RenameCandidate(removed=r, added=a, similarity=ratio))
    # Stable sort: highest similarity first, then by path.
    candidates.sort(key=lambda c: (-c.similarity, c.removed.path, c.removed.name))
    return candidates


def _compute_nag_message(
    *,
    wiki_dir: Path,
    nag_after_days: int,
    today: date,
) -> str | None:
    """Count unresolved `stale: true` refs whose `stale_detected:` is
    older than `nag_after_days`, and return a one-line reminder. None
    if nothing qualifies."""
    cutoff = today - timedelta(days=nag_after_days)
    old_count = 0
    for md in wiki_dir.rglob("*.md"):
        try:
            doc = fm.load(md)
        except (OSError, UnicodeDecodeError):
            continue
        for ref in fm.code_refs(doc):
            if not ref.get("stale"):
                continue
            detected = ref.get("stale_detected")
            if detected is None:
                old_count += 1
                continue
            try:
                d = _coerce_date(detected)
            except ValueError:
                continue
            if d <= cutoff:
                old_count += 1

    if old_count == 0:
        return None
    return (
        f"⚠ stale 플래그 {old_count}개, {nag_after_days}일 이상 미해결. "
        f"`wiki-fix-stale`로 처리하시겠어요?"
    )


def _coerce_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"unrecognized date value: {value!r}")


# ---------- Phase 3: reverse refs ----------


def _build_reverse_refs(
    paths: SyncPaths,
) -> tuple[dict, list[tuple[str, str, str]]]:
    """Walk `wiki/**/*.md` and gather declared `refs.code`.

    Returns (reverse_refs_dict, declared_refs_list).
    `declared_refs_list` is `[(referencing_page, ref_path, ref_symbol), ...]` —
    used by the stale-link pass to know which page declared which ref.
    """
    reverse: dict[str, dict[str, list[str]]] = {}  # path -> {page: [symbols...]}
    declared: list[tuple[str, str, str]] = []

    if not paths.wiki.exists():
        return _format_reverse_refs(reverse), declared

    for md in sorted(paths.wiki.rglob("*.md")):
        rel_page = _relative_posix(md, paths.repo_root)
        try:
            doc = fm.load(md)
        except (OSError, UnicodeDecodeError):
            continue
        for ref in fm.code_refs(doc):
            ref_path = str(ref.get("path", "")).strip()
            ref_symbol = str(ref.get("symbol", "")).strip()
            if not ref_path or not ref_symbol:
                continue
            reverse.setdefault(ref_path, {}).setdefault(rel_page, []).append(ref_symbol)
            declared.append((rel_page, ref_path, ref_symbol))

    return _format_reverse_refs(reverse), declared


def _format_reverse_refs(reverse: dict) -> dict:
    """Convert internal nested dict to the JSON shape declared in the SPEC."""
    by_path: dict[str, list[dict]] = {}
    for ref_path, page_map in sorted(reverse.items()):
        by_path[ref_path] = [
            {"page": page, "symbols": symbols}
            for page, symbols in sorted(page_map.items())
        ]
    pages_with_refs = len({page for page_map in reverse.values() for page in page_map})
    return {
        "by_path": by_path,
        "stats": {
            "pages_with_refs": pages_with_refs,
            "distinct_paths_referenced": len(reverse),
        },
    }


# ---------- Phase 4: stale-link pass ----------


def _stale_link_pass(
    *,
    paths: SyncPaths,
    current_symbols: list[Symbol],
    declared_refs: list[tuple[str, str, str]],
    today: date,
) -> tuple[int, int]:
    """Mark any declared `refs.code` whose (path, symbol) is missing from
    current_symbols as `stale: true` in frontmatter, and append a note
    to `wiki/questions.md` for each *newly* stale ref.

    Returns (stale_flagged, questions_appended).
    """
    current_keys = {(s.path, s.name) for s in current_symbols}
    # method names also matter — wiki refs might use "Trainer.train_one_epoch"
    for s in current_symbols:
        if s.parent:
            current_keys.add((s.path, f"{s.parent}.{s.name}"))

    # Group declared refs by referencing page.
    by_page: dict[str, list[tuple[str, str]]] = {}
    for page, ref_path, ref_symbol in declared_refs:
        by_page.setdefault(page, []).append((ref_path, ref_symbol))

    stale_flagged_total = 0
    new_questions: list[str] = []

    for page, refs in by_page.items():
        page_path = paths.repo_root / page
        if not page_path.exists():
            continue

        # Determine which of the declared refs are stale (missing from current_symbols).
        stale_for_page: set[tuple[str, str]] = set()
        for ref_path, ref_symbol in refs:
            if (ref_path, ref_symbol) not in current_keys:
                stale_for_page.add((ref_path, ref_symbol))

        if not stale_for_page:
            continue

        # Read current frontmatter to skip already-marked-stale entries
        # (idempotency: don't re-emit questions on every sync).
        doc = fm.load(page_path)
        already_stale: set[tuple[str, str]] = set()
        for entry in fm.code_refs(doc):
            if entry.get("stale"):
                already_stale.add((str(entry.get("path", "")), str(entry.get("symbol", ""))))

        new_stale = stale_for_page - already_stale

        # Apply frontmatter edits (idempotent).
        flagged_now = fm.mark_refs_stale(page_path, stale_keys=stale_for_page, detected=today)
        stale_flagged_total += flagged_now

        # Build question entries only for newly stale refs.
        for ref_path, ref_symbol in sorted(new_stale):
            new_questions.append(
                f"**Stale ref:** `{page}` references "
                f"`{ref_path}:{ref_symbol}`, which no longer exists in the index.\n\n"
                f"**Action needed:** researcher to decide — update body to new symbol, "
                f"remove the ref, or accept that the page documents deprecated code."
            )

    questions_appended = 0
    if new_questions:
        questions_appended = _append_questions(paths.wiki / "questions.md", new_questions, today)

    return stale_flagged_total, questions_appended


def _body_link_rot_pass(
    *,
    paths: SyncPaths,
    current_symbols: list[Symbol],
    today: date,
) -> tuple[int, int]:
    """For each non-meta wiki page, scan body prose for identifier-shape
    tokens that are NOT in `current_symbols` and record them as
    `body_stale_mentions:` frontmatter entries.

    Heuristic — false positives possible (English nouns matching
    PascalCase, `.cpp` filenames, etc.). Implicit `[unverified]`
    semantic for downstream consumers (`wiki-fix-stale`, `wiki-lint`).

    Idempotent — re-running with the same state produces no disk writes.
    Body never modified.

    Returns (total_mentions_recorded, pages_with_mentions).
    """
    today_iso = today.isoformat()

    # Build a flat set of symbol names + dotted forms for methods.
    symbol_names: set[str] = set()
    for s in current_symbols:
        symbol_names.add(s.name)
        if s.parent:
            symbol_names.add(f"{s.parent}.{s.name}")
        # Strip parens that the regex may have included on snake_case.
    # The body_stale_mentions logic treats `Trainer.train_one_epoch` as one token
    # but `train_one_epoch(` (snake-case-with-paren) as another. Both must match
    # against the flat symbol set (after stripping the trailing `(`).

    META_PAGES = {"index.md", "log.md", "questions.md", "discrepancies.md"}
    total_mentions = 0
    pages_touched = 0

    for md in sorted(paths.wiki.rglob("*.md")):
        rel = _relative_posix(md, paths.repo_root)
        # Skip meta pages.
        rest = rel[len("wiki/"):] if rel.startswith("wiki/") else rel
        if "/" not in rest and rest in META_PAGES:
            continue

        try:
            doc = fm.load(md)
        except (OSError, UnicodeDecodeError):
            continue
        body = doc.raw_text[doc.body_offset:]

        mentions = _scan_body_for_stale_tokens(body, symbol_names, today_iso)
        # Idempotency: skip disk writes when the field would be unchanged.
        n = fm.set_body_stale_mentions(md, mentions=mentions)
        if mentions:
            pages_touched += 1
            total_mentions += len(mentions)

    return total_mentions, pages_touched


def _scan_body_for_stale_tokens(
    body: str,
    symbol_names: set[str],
    detected: str,
) -> list[dict]:
    """Tokenize `body` with the body link rot regex; for each unique
    `(line, token)` whose token is missing from `symbol_names`, return
    a `body_stale_mentions:` entry.

    Skips lines inside fenced code blocks (``` ... ``` or ~~~ ... ~~~).
    """
    out: list[dict] = []
    seen: set[tuple[int, str]] = set()
    in_fence = False
    fence_marker: str | None = None

    for line_no, line in enumerate(body.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence, fence_marker = False, None
            continue
        if in_fence:
            continue

        for match in _BODY_TOKEN_RE.finditer(line):
            raw_token = match.group(0)
            # Strip trailing `(` that the snake_case alternative may include.
            token = raw_token.rstrip("(")
            if not token:
                continue
            if token in symbol_names:
                continue
            # Also check the bare last component (Trainer.train_one_epoch → train_one_epoch).
            if "." in token and token.rsplit(".", 1)[-1] in symbol_names:
                continue
            key = (line_no, token)
            if key in seen:
                continue
            seen.add(key)
            out.append({"line": line_no, "token": token, "detected": detected})

    return out


def _append_questions(questions_md: Path, entries: list[str], today) -> int:
    if not entries:
        return 0
    questions_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = [f"\n## [{timestamp}] from wiki-sync\n"]
    for entry in entries:
        block.append(entry + "\n")
    existing = questions_md.read_text(encoding="utf-8") if questions_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    questions_md.write_text(existing + "\n".join(block), encoding="utf-8")
    return len(entries)


# ---------- Phase 5: write outputs ----------


def _write_signatures(index_dir: Path, symbols: list[Symbol]) -> Path:
    path = index_dir / "signatures.json"
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "symbols": [s.to_json() for s in symbols],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_reverse_refs(index_dir: Path, reverse: dict) -> Path:
    path = index_dir / "reverse_refs.json"
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **reverse,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_snapshot(
    *,
    paths: SyncPaths,
    current_symbols: list[Symbol],
    added: list[Symbol],
    removed: list[Symbol],
    scan_errors: list[ScanError],
    rename_candidates: list[RenameCandidate] | None = None,
) -> Path:
    now = datetime.now()
    name = f"sync_{now.strftime('%Y%m%d_%H%M')}.md"
    snapshot_path = paths.index / "snapshots" / name

    # Find previous snapshot for the diff section pointer.
    prev = _previous_snapshot(paths.index / "snapshots", current=name)
    prev_pointer = f"index/snapshots/{prev}" if prev else "(none — first run)"

    # File tree (depth-limited).
    tree_text = _render_file_tree(paths.repo_root, max_depth=3)

    # Language breakdown.
    lang_text = _render_language_breakdown(paths.repo_root)

    # Module list (top-level symbols by file).
    modules_text = _render_modules(current_symbols)

    # Active experiments.
    exp_text = _render_active_experiments(paths.raw)

    # Changes section.
    changes_text = _render_changes(added, removed)

    # Possible renames (heuristic).
    renames_text = _render_renames(rename_candidates or [])

    # Scan errors.
    errors_text = _render_scan_errors(scan_errors)

    body = (
        f"# Sync snapshot — {now.strftime('%Y-%m-%d %H:%M')} ({_tz_label(now)})\n"
        f"_Generated by wiki-sync. Immutable once written._\n\n"
        f"## Repository\n"
        f"- Root: {paths.repo_root}\n"
        f"- Scope: all\n"
        f"- Previous snapshot: {prev_pointer}\n\n"
        f"## File tree (depth-limited)\n"
        f"```\n{tree_text}```\n\n"
        f"## Language breakdown\n{lang_text}\n"
        f"## Modules\n{modules_text}\n"
        f"## Active experiments\n{exp_text}\n"
        f"## Changes since previous snapshot\n{changes_text}\n"
        f"## Possible renames (heuristic, [unverified])\n{renames_text}\n"
        f"## Scan errors\n{errors_text}\n"
    )
    snapshot_path.write_text(body, encoding="utf-8")
    return snapshot_path


def _render_renames(candidates: list[RenameCandidate]) -> str:
    if not candidates:
        return "(none)\n"
    lines: list[str] = []
    for c in candidates:
        old_qualified = f"{c.removed.parent}.{c.removed.name}" if c.removed.parent else c.removed.name
        new_qualified = f"{c.added.parent}.{c.added.name}" if c.added.parent else c.added.name
        lines.append(
            f"- `{c.removed.path}:{old_qualified}` → `{c.added.path}:{new_qualified}`\n"
            f"  Evidence: same file, line {c.removed.line} → {c.added.line}, "
            f"signature similarity {c.similarity:.2f}.\n"
            f"  Alternative reading: `{old_qualified}` deleted, `{new_qualified}` added independently."
        )
    return "\n".join(lines) + "\n"


def _previous_snapshot(snapshots_dir: Path, *, current: str) -> str | None:
    if not snapshots_dir.exists():
        return None
    candidates = sorted(p.name for p in snapshots_dir.iterdir() if p.name.startswith("sync_") and p.name.endswith(".md"))
    candidates = [c for c in candidates if c != current]
    return candidates[-1] if candidates else None


def _render_file_tree(root: Path, *, max_depth: int) -> str:
    lines: list[str] = []
    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        children = sorted([p for p in d.iterdir() if p.name not in DEFAULT_IGNORE_DIRS and p.name not in DEFAULT_IGNORE_FILES])
        for child in children:
            indent = "  " * depth
            if child.is_dir():
                lines.append(f"{indent}{child.name}/")
                walk(child, depth + 1)
            else:
                lines.append(f"{indent}{child.name}")
    walk(root, 0)
    return "\n".join(lines) + "\n" if lines else "(empty)\n"


def _render_language_breakdown(root: Path) -> str:
    counts: dict[str, tuple[int, int]] = {}  # ext -> (files, lines)
    for f in _iter_supported_files(root):
        ext = f.suffix.lower()
        try:
            line_count = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
        except OSError:
            line_count = 0
        files, lines = counts.get(ext, (0, 0))
        counts[ext] = (files + 1, lines + line_count)
    if not counts:
        return "(no files indexed)\n"
    label = {".py": "Python", ".json": "JSON", ".md": "Markdown"}
    parts = []
    for ext in sorted(counts):
        f, l = counts[ext]
        parts.append(f"- {label.get(ext, ext)}: {f} files, {l} lines")
    return "\n".join(parts) + "\n"


def _iter_supported_files(root: Path):
    for path in _walk_repo(root):
        rel = _relative_posix(path, root)
        if is_supported(rel):
            yield path


def _render_modules(symbols: list[Symbol]) -> str:
    """Group top-level Python classes/functions per file."""
    by_file: dict[str, list[str]] = {}
    for s in symbols:
        if s.kind in ("class", "function") and s.path.endswith(".py"):
            by_file.setdefault(s.path, []).append(f"{s.kind} {s.name}")
    if not by_file:
        return "(no Python modules indexed)\n"
    parts = []
    for path in sorted(by_file):
        items = ", ".join(by_file[path])
        parts.append(f"- {path}        ({items})")
    return "\n".join(parts) + "\n"


def _render_active_experiments(raw: Path) -> str:
    exp_dir = raw / "experiments"
    if not exp_dir.exists():
        return "(none — `raw/experiments/` does not exist)\n"
    dirs = sorted(p.name for p in exp_dir.iterdir() if p.is_dir())
    if not dirs:
        return "(none — `raw/experiments/` is empty)\n"
    return "\n".join(f"- raw/experiments/{d}/" for d in dirs) + "\n"


def _render_changes(added: list[Symbol], removed: list[Symbol]) -> str:
    if not added and not removed:
        return "(no changes since previous snapshot)\n"
    parts: list[str] = []
    if added:
        parts.append("### Symbols added\n" + "\n".join(_format_symbol_line("+", s) for s in added))
    if removed:
        parts.append("### Symbols removed\n" + "\n".join(_format_symbol_line("-", s) for s in removed))
    return "\n".join(parts) + "\n"


def _format_symbol_line(prefix: str, s: Symbol) -> str:
    qualified = f"{s.parent}.{s.name}" if s.parent else s.name
    return f"{prefix} {s.path}:{qualified} ({s.kind})"


def _render_scan_errors(errors: list[ScanError]) -> str:
    if not errors:
        return "(none)\n"
    return "\n".join(f"- {e.path}{':' + str(e.line) if e.line else ''}: {e.message}" for e in errors) + "\n"


# ---------- Helpers ----------


def _relative_posix(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _tz_label(dt: datetime) -> str:
    tz = dt.astimezone().tzname()
    return tz or "local"
