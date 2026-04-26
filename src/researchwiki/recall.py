"""wiki-recall — surface stale-but-relevant wiki pages.

Read-only. Computes weighted overlap between (i) refs declared by
recent `wiki/log.md` entries and (ii) refs in stale-page frontmatter.
Body prose is not parsed (boundary against wiki-query).

`updated:` from frontmatter — not git mtime — measures staleness.
Skill-meta log entries (`from wiki-sync`, `from wiki-lint`, etc.) are
filtered out of the recent-activity corpus by header pattern.

Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from researchwiki.lint.runner import _split_frontmatter

DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_STALE_SINCE_DAYS = 60
DEFAULT_TOP = 10

DEFAULT_REF_WEIGHTS: dict[str, float] = {
    "code": 2.0,
    "concepts": 1.5,
    "papers": 1.0,
    "experiments": 1.0,
}

# `## [2026-04-26 10:30] <verb> ...` — the verb is the first token after the
# date bracket. Headers come in two shapes:
#   - pipe-separated: `log | experiment | exp-001`, `amend | ...`, `init | ...`
#   - free-form:      `from wiki-sync`, `from wiki-lint`, ...
# We capture the verb and leave parsing of the rest to the caller.
_LOG_HEADER_RE = re.compile(
    r"^##\s+\[(?P<date>\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?\]\s+"
    r"(?P<verb>\S+)\s*(?P<rest>.*?)\s*$",
)
_LOG_LINK_RE = re.compile(r"→\s*(wiki/\S+\.md)")

# Header verbs that count as researcher activity. Everything else (e.g.
# `from`, `init`) is treated as skill-meta and filtered out.
RESEARCHER_VERBS = frozenset({"log", "amend"})


@dataclass(frozen=True)
class LogEntry:
    date: date
    verb: str           # "log" / "amend" / "from" / "init"
    title: str | None
    page_path: str | None  # the wiki/... target the entry points at


@dataclass
class RecallScoreEntry:
    page_path: str
    score: float
    updated: date | None
    days_since_updated: int | None
    overlaps: list[str] = field(default_factory=list)  # human-readable overlap lines


@dataclass
class RecallResult:
    results: list[RecallScoreEntry]
    log_entries_in_window: int
    pages_considered: int
    pages_with_overlaps: int


def run_recall(
    repo_root: Path,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    stale_since_days: int = DEFAULT_STALE_SINCE_DAYS,
    top: int = DEFAULT_TOP,
    scope: str = "all",
    include_stubs: bool = False,
    today: date | None = None,
    ref_weights: dict[str, float] | None = None,
) -> RecallResult:
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_root not found: {repo_root}")

    wiki_dir = repo_root / "wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"`wiki/` does not exist under {repo_root}; run wiki-init first.")

    log_md = wiki_dir / "log.md"
    if not log_md.exists():
        raise FileNotFoundError("wiki/log.md is empty or missing.")

    today = today or datetime.now().date()
    weights = ref_weights or DEFAULT_REF_WEIGHTS

    # Phase 1: parse log.md, filter by window + verb.
    log_entries = parse_log_entries(log_md.read_text(encoding="utf-8"))
    cutoff = today - timedelta(days=lookback_days)
    recent = [
        e for e in log_entries
        if e.verb in RESEARCHER_VERBS and e.date >= cutoff
    ]

    # Phase 2: gather refs from each recent entry's linked page.
    recent_refs: dict[str, set[tuple[str, str | None]]] = {
        kind: set() for kind in DEFAULT_REF_WEIGHTS
    }
    # Also remember which log entry contributed which ref (for evidence text).
    ref_to_entries: dict[tuple[str, str, str | None], list[LogEntry]] = {}

    for entry in recent:
        if not entry.page_path:
            continue
        page_file = repo_root / entry.page_path
        if not page_file.exists():
            continue
        fm, _body, _err = _split_frontmatter(page_file.read_text(encoding="utf-8"))
        for kind in DEFAULT_REF_WEIGHTS:
            for ref_key in _refs_for_kind(fm, kind):
                recent_refs[kind].add(ref_key)
                ref_to_entries.setdefault((kind, ref_key[0], ref_key[1]), []).append(entry)

    # Phase 3: walk stale candidates.
    candidates = _stale_pages(
        wiki_dir=wiki_dir,
        repo_root=repo_root,
        today=today,
        stale_since_days=stale_since_days,
        scope=scope,
        include_stubs=include_stubs,
    )

    pages_considered = len(candidates)
    scored: list[RecallScoreEntry] = []
    for page_path, fm, updated in candidates:
        score = 0.0
        overlap_lines: list[str] = []
        for kind in DEFAULT_REF_WEIGHTS:
            page_refs = _refs_for_kind(fm, kind)
            for ref_key in page_refs:
                if ref_key in recent_refs[kind]:
                    score += weights.get(kind, 1.0)
                    contributing = ref_to_entries.get((kind, ref_key[0], ref_key[1]), [])
                    if contributing:
                        ev = contributing[-1]  # most recent
                        days_ago = (today - ev.date).days
                        ref_str = _format_ref_key(kind, ref_key)
                        overlap_lines.append(
                            f"shared refs.{kind:<11s} {ref_str:<40s} "
                            f"(logged {days_ago}d ago in {ev.title or ev.page_path or '?'})"
                        )
        if score > 0:
            days_since = (today - updated).days if updated else None
            scored.append(RecallScoreEntry(
                page_path=page_path,
                score=score,
                updated=updated,
                days_since_updated=days_since,
                overlaps=overlap_lines,
            ))

    scored.sort(key=lambda r: (-r.score, -(r.days_since_updated or 0), r.page_path))
    top_results = scored[:top]

    return RecallResult(
        results=top_results,
        log_entries_in_window=len(recent),
        pages_considered=pages_considered,
        pages_with_overlaps=len(scored),
    )


# ---------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------


def parse_log_entries(text: str) -> list[LogEntry]:
    """Parse `wiki/log.md` into a list of LogEntry. Verb classification:
    `log` / `amend` are researcher activity; everything else is skill-meta.
    """
    entries: list[LogEntry] = []
    current_match = None
    current_link: str | None = None

    def flush():
        if current_match is None:
            return
        try:
            d = date.fromisoformat(current_match.group("date"))
        except ValueError:
            return
        rest = current_match.group("rest") or ""
        title: str | None = None
        if rest.startswith("|"):
            # Pipe-separated form: `| <type> | <title>`. Take the last
            # pipe segment as the title (skip the type).
            parts = [p.strip() for p in rest.lstrip("|").split("|")]
            if parts:
                title = parts[-1] or None
        elif rest:
            # Free-form (e.g., `from wiki-sync`): use the rest as the title.
            title = rest
        entries.append(LogEntry(
            date=d,
            verb=current_match.group("verb"),
            title=title,
            page_path=current_link,
        ))

    for line in text.splitlines():
        m = _LOG_HEADER_RE.match(line)
        if m:
            # End of previous entry; record it.
            flush()
            current_match = m
            current_link = None
            continue
        if current_match is not None:
            link_match = _LOG_LINK_RE.search(line)
            if link_match and current_link is None:
                current_link = link_match.group(1)

    flush()
    return entries


# ---------------------------------------------------------------------
# Page selection helpers
# ---------------------------------------------------------------------


def _stale_pages(
    *,
    wiki_dir: Path,
    repo_root: Path,
    today: date,
    stale_since_days: int,
    scope: str,
    include_stubs: bool,
) -> list[tuple[str, dict, date | None]]:
    """Return [(rel_path, frontmatter, updated_date)] for non-meta pages
    older than `stale_since_days` (or with no `updated:` field — treated as
    very old). Stubs are filtered unless `include_stubs=True`."""
    out: list[tuple[str, dict, date | None]] = []
    cutoff = today - timedelta(days=stale_since_days)
    scope_dirs = {
        "all": None,
        "concepts": "concepts",
        "papers": "papers",
        "experiments": "experiments",
        "decisions": "decisions",
    }
    if scope not in scope_dirs:
        raise ValueError(f"unknown scope: {scope!r}")
    subdir = scope_dirs[scope]

    for md in sorted(wiki_dir.rglob("*.md")):
        rel = md.resolve().relative_to(repo_root.resolve()).as_posix()
        if _is_meta_page(rel, "wiki/"):
            continue
        if subdir and not rel.startswith(f"wiki/{subdir}/"):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, body, _err = _split_frontmatter(text)
        # Stub exclusion (default).
        if not include_stubs and _is_stub(fm, body):
            continue
        updated = _parse_updated(fm.get("updated"))
        if updated is not None and updated > cutoff:
            continue  # not stale enough
        out.append((rel, fm, updated))
    return out


def _is_meta_page(path: str, wiki_root: str) -> bool:
    wiki_root = wiki_root.rstrip("/") + "/"
    if not path.startswith(wiki_root):
        return False
    rest = path[len(wiki_root):]
    if "/" in rest:
        return False
    return rest in {"index.md", "log.md", "questions.md", "discrepancies.md"}


def _is_stub(frontmatter: dict, body: str) -> bool:
    if frontmatter.get("seeded_by"):
        # Strict stub indicator from wiki-log / wiki-deepscan.
        body_text = re.sub(r"^#.*$", "", body, flags=re.MULTILINE).strip()
        # Strip italic placeholder line(s).
        body_text = re.sub(r"^\*[^*]+\*\s*$", "", body_text, flags=re.MULTILINE).strip()
        # If body has no real content beyond the structural-facts template, treat as stub.
        return "Add interpretation here" in body or len(body_text) < 120
    if frontmatter.get("authored_by") == "llm":
        # wiki-deepscan stubs.
        return True
    return False


def _parse_updated(value) -> date | None:
    if value is None:
        return None
    try:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
    except ValueError:
        return None
    return None


# ---------------------------------------------------------------------
# Refs helpers
# ---------------------------------------------------------------------


def _refs_for_kind(frontmatter: dict, kind: str) -> set[tuple[str, str | None]]:
    """Return a set of (path/slug, symbol-or-None) tuples for the given
    refs.<kind> block. For `code`, both fields populated. For
    concepts/papers/experiments, the slug is in the first slot and the
    second slot is None."""
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return set()
    items = refs.get(kind)
    if not isinstance(items, list):
        return set()
    out: set[tuple[str, str | None]] = set()
    if kind == "code":
        for r in items:
            if isinstance(r, dict):
                p = r.get("path")
                s = r.get("symbol")
                if isinstance(p, str) and isinstance(s, str):
                    out.add((p, s))
    else:
        for r in items:
            if isinstance(r, str):
                out.add((r, None))
            elif isinstance(r, dict):
                # Allow {"id": "..."} form.
                rid = r.get("id")
                if isinstance(rid, str):
                    out.add((rid, None))
    return out


def _format_ref_key(kind: str, ref_key: tuple[str, str | None]) -> str:
    if kind == "code":
        return f"{ref_key[0]}:{ref_key[1]}"
    return ref_key[0]


# ---------------------------------------------------------------------
# Stdout formatting
# ---------------------------------------------------------------------


def format_results(result: RecallResult, *, lookback_days: int, stale_since_days: int) -> str:
    if not result.results:
        return (
            "0 stale-but-relevant pages found.\n\n"
            f"Window: --lookback {lookback_days} days, --stale-since {stale_since_days} days\n"
            f"Recent log entries scanned: {result.log_entries_in_window}   "
            f"|   Stale pages considered: {result.pages_considered}   "
            f"|   Pages with overlaps: 0\n"
        )

    lines: list[str] = []
    for i, r in enumerate(result.results, start=1):
        updated_str = (
            f"updated {r.updated.isoformat()}, {r.days_since_updated}d ago"
            if r.updated else "updated unknown"
        )
        lines.append(f"{i}. {r.page_path}    score {r.score:.1f}  ({updated_str})")
        lines.append("   Overlaps with recent activity:")
        for ov in r.overlaps:
            lines.append(f"     - {ov}")
        lines.append("")
    lines.append(
        f"Window: --lookback {lookback_days}d, --stale-since {stale_since_days}d   "
        f"|   Log entries scanned: {result.log_entries_in_window}   "
        f"|   Stale pages considered: {result.pages_considered}   "
        f"|   Pages with overlaps: {result.pages_with_overlaps}"
    )
    return "\n".join(lines) + "\n"
