"""wiki-fix-stale — researcher-initiated body remediation for stale refs.

The *one* skill that legitimately edits wiki page bodies after creation,
under strict P3 carve-out: researcher-initiated invocation + per-occurrence
approval + only four pre-defined mechanical transformations.

Walks pages with `stale: true` frontmatter refs and/or
`body_stale_mentions:` entries. For each occurrence in the body, the
researcher chooses one of:

  1. Replace symbol — researcher supplies new identifier; literal swap.
  2. Wrap with `[deprecated YYYY-MM-DD]` — prepend tag to the line.
  3. Delete the line containing the symbol.
  4. Skip — leave as-is; flag remains for next run.

The four transformations are *mechanical* — the skill never composes
prose, paraphrases the surrounding text, or proposes wording.

After all occurrences in a page are addressed (no skips), and
`--auto-clear-flags` is on (default), `stale: true` flags and
`body_stale_mentions:` entries are removed from frontmatter. A session
record is appended to `wiki/log.md`.

The interactive prompt is dependency-injected via `prompt_fn` so tests
can script responses without monkey-patching `input()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Literal

import yaml

from researchwiki import frontmatter as fm

PromptFn = Callable[[str], str]
DisplayFn = Callable[[str], None]

DEFAULT_PROMPT_FN: PromptFn = input


def _default_display(message: str) -> None:
    """Default display callable — prints to stdout. Tests inject a no-op
    or a list-collector to suppress stdout while checking the call sequence."""
    print(message)


# ---------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------


@dataclass
class Occurrence:
    page_path: Path        # absolute filesystem path
    page_rel: str          # repo-relative POSIX path
    symbol: str            # token to act on
    line: int              # 1-based line in body; 0 if frontmatter-only and not in body
    line_text: str         # the body line containing the symbol (or "" for fm-only)
    source: Literal["frontmatter", "body-mention"]


@dataclass
class PageState:
    page_path: Path
    page_rel: str
    frontmatter: dict
    body: str
    raw_text: str
    body_offset: int
    occurrences: list[Occurrence]
    flagged_keys: set[tuple[str, str]] = field(default_factory=set)
    body_mention_entries: list[dict] = field(default_factory=list)
    stale_detected: date | None = None


@dataclass
class StaleFix:
    occurrence_index: int
    action: Literal["replace", "wrap", "delete", "skip", "clear-flag-only"]
    new_symbol: str | None = None  # for replace


@dataclass
class FixStaleResult:
    pages_walked: int = 0
    pages_fully_cleared: int = 0
    pages_partial: int = 0
    pages_discarded: int = 0
    body_edits_applied: int = 0
    stale_flags_cleared: int = 0
    body_mentions_resolved: int = 0
    log_record_appended: bool = False


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------


def run_fix_stale(
    repo_root: Path,
    *,
    prompt_fn: PromptFn = DEFAULT_PROMPT_FN,
    display_fn: DisplayFn = _default_display,
    auto_clear_flags: bool = True,
    include_body_mentions: bool = True,
    page_filter: str | None = None,
    today: date | None = None,
) -> FixStaleResult:
    """Walk pages with unresolved stale refs; apply researcher-approved
    body edits; clear flags on full resolution.

    `prompt_fn(message: str) -> str` returns the researcher's response
    to each decision point. `display_fn(message: str) -> None` is used
    for purely informational output. Default `display_fn` prints to
    stdout; default `prompt_fn` calls `input()`. Tests inject scripted
    versions.
    """
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_root not found: {repo_root}")

    wiki_dir = repo_root / "wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"`wiki/` does not exist under {repo_root}; run wiki-init first.")

    today = today or datetime.now().date()
    pages = _load_stale_pages(
        wiki_dir=wiki_dir,
        repo_root=repo_root,
        include_body_mentions=include_body_mentions,
        page_filter=page_filter,
    )

    if not pages:
        display_fn("No stale flags to fix.")
        return FixStaleResult()

    # Sort oldest-first by stale_detected (None → epoch).
    pages.sort(key=lambda p: p.stale_detected or date(1970, 1, 1))

    total_occ = sum(len(p.occurrences) for p in pages)
    fm_occ = sum(1 for p in pages for o in p.occurrences if o.source == "frontmatter")
    body_occ = total_occ - fm_occ
    display_fn(
        f"wiki-fix-stale: {len(pages)} page(s) with unresolved stale refs.\n"
        f"  Total occurrences: {fm_occ} frontmatter ref(s) "
        f"+ {body_occ} body mention(s) [unverified]\n"
        f"  Walking pages oldest-first."
    )
    response = prompt_fn("Continue? [y/N]").strip().lower()
    if response not in ("y", "yes"):
        return FixStaleResult()

    result = FixStaleResult()
    today_iso = today.isoformat()

    for idx, page in enumerate(pages, start=1):
        result.pages_walked += 1
        outcome = _walk_page(
            page=page,
            page_index=idx,
            page_count=len(pages),
            prompt_fn=prompt_fn,
            display_fn=display_fn,
            today_iso=today_iso,
            auto_clear_flags=auto_clear_flags,
        )
        result.body_edits_applied += outcome["body_edits"]
        result.stale_flags_cleared += outcome["flags_cleared"]
        result.body_mentions_resolved += outcome["mentions_cleared"]
        if outcome["status"] == "fully-cleared":
            result.pages_fully_cleared += 1
        elif outcome["status"] == "partial":
            result.pages_partial += 1
        elif outcome["status"] == "discarded":
            result.pages_discarded += 1

    if result.body_edits_applied or result.stale_flags_cleared or result.body_mentions_resolved:
        _append_session_record(wiki_dir / "log.md", result, today)
        result.log_record_appended = True

    return result


# ---------------------------------------------------------------------
# Page loading
# ---------------------------------------------------------------------


def _load_stale_pages(
    *,
    wiki_dir: Path,
    repo_root: Path,
    include_body_mentions: bool,
    page_filter: str | None,
) -> list[PageState]:
    pages: list[PageState] = []
    for md in sorted(wiki_dir.rglob("*.md")):
        try:
            doc = fm.load(md)
        except (OSError, UnicodeDecodeError):
            continue
        rel = md.resolve().relative_to(repo_root.resolve()).as_posix()
        if page_filter and rel != page_filter:
            continue

        flagged_keys: set[tuple[str, str]] = set()
        oldest: date | None = None
        for entry in fm.code_refs(doc):
            if entry.get("stale"):
                p = str(entry.get("path", ""))
                s = str(entry.get("symbol", ""))
                if p and s:
                    flagged_keys.add((p, s))
                detected = entry.get("stale_detected")
                if detected:
                    try:
                        d = _coerce_date(detected)
                        if oldest is None or d < oldest:
                            oldest = d
                    except ValueError:
                        pass

        body_mentions: list[dict] = []
        if include_body_mentions:
            raw_mentions = doc.frontmatter.get("body_stale_mentions") or []
            if isinstance(raw_mentions, list):
                body_mentions = [m for m in raw_mentions if isinstance(m, dict)]

        if not flagged_keys and not body_mentions:
            continue

        body = doc.raw_text[doc.body_offset:]
        body_lines = body.splitlines()

        # Build occurrence list — frontmatter-driven first (every body match of
        # each stale symbol), then body_stale_mentions entries that aren't
        # already covered.
        occurrences: list[Occurrence] = []
        seen_lines: set[tuple[int, str]] = set()

        for (_path, symbol) in flagged_keys:
            matched_lines = [
                (i + 1, line) for i, line in enumerate(body_lines) if symbol in line
            ]
            if not matched_lines:
                # Symbol mentioned in frontmatter but not in body — special case.
                occurrences.append(Occurrence(
                    page_path=md, page_rel=rel,
                    symbol=symbol, line=0, line_text="",
                    source="frontmatter",
                ))
                continue
            for line_no, line in matched_lines:
                key = (line_no, symbol)
                if key in seen_lines:
                    continue
                seen_lines.add(key)
                occurrences.append(Occurrence(
                    page_path=md, page_rel=rel,
                    symbol=symbol, line=line_no, line_text=line,
                    source="frontmatter",
                ))

        for entry in body_mentions:
            line_no = int(entry.get("line", 0)) or 0
            token = str(entry.get("token", "")).strip()
            if not token or line_no <= 0 or line_no > len(body_lines):
                continue
            key = (line_no, token)
            if key in seen_lines:
                continue
            seen_lines.add(key)
            occurrences.append(Occurrence(
                page_path=md, page_rel=rel,
                symbol=token, line=line_no,
                line_text=body_lines[line_no - 1],
                source="body-mention",
            ))

        # Stable sort by line, then symbol.
        occurrences.sort(key=lambda o: (o.line, o.symbol))

        pages.append(PageState(
            page_path=md, page_rel=rel,
            frontmatter=doc.frontmatter, body=body,
            raw_text=doc.raw_text, body_offset=doc.body_offset,
            occurrences=occurrences,
            flagged_keys=flagged_keys,
            body_mention_entries=body_mentions,
            stale_detected=oldest,
        ))

    return pages


# ---------------------------------------------------------------------
# Per-page interaction
# ---------------------------------------------------------------------


def _walk_page(
    *,
    page: PageState,
    page_index: int,
    page_count: int,
    prompt_fn: PromptFn,
    display_fn: DisplayFn,
    today_iso: str,
    auto_clear_flags: bool,
) -> dict:
    age_str = ""
    if page.stale_detected:
        try:
            age = (date.fromisoformat(today_iso) - page.stale_detected).days
            age_str = f"  (oldest flag: {age}d ago)"
        except ValueError:
            pass

    display_fn(
        f"\n────────────────────────────────────────────────────────────\n"
        f"[Page {page_index}/{page_count}]  {page.page_rel}{age_str}\n"
        f"  Frontmatter stale: {len(page.flagged_keys)} ref(s)\n"
        f"  Body mentions [unverified]: {len(page.body_mention_entries)}"
    )

    fixes: list[StaleFix] = []
    for i, occ in enumerate(page.occurrences):
        fix = _walk_occurrence(
            occ=occ, occ_index=i, occ_total=len(page.occurrences),
            prompt_fn=prompt_fn, display_fn=display_fn, today_iso=today_iso,
        )
        fixes.append(fix)

    # Show diff preview.
    display_fn("\n" + _render_diff_preview(page, fixes, today_iso, auto_clear_flags))
    response = prompt_fn("Apply? [y/N/edit]").strip().lower()

    if response == "edit":
        # MVP: edit re-walks all occurrences; partial revision is out of scope.
        fixes = []
        for i, occ in enumerate(page.occurrences):
            fix = _walk_occurrence(
                occ=occ, occ_index=i, occ_total=len(page.occurrences),
                prompt_fn=prompt_fn, display_fn=display_fn, today_iso=today_iso,
            )
            fixes.append(fix)
        display_fn("\n" + _render_diff_preview(page, fixes, today_iso, auto_clear_flags))
        response = prompt_fn("Apply? [y/N]").strip().lower()

    if response not in ("y", "yes"):
        return {"status": "discarded", "body_edits": 0, "flags_cleared": 0, "mentions_cleared": 0}

    body_edits, flags_cleared, mentions_cleared = _apply_fixes(
        page, fixes, today_iso, auto_clear_flags,
    )
    skipped = sum(1 for f in fixes if f.action == "skip")
    status = "fully-cleared" if skipped == 0 else "partial"
    return {
        "status": status,
        "body_edits": body_edits,
        "flags_cleared": flags_cleared,
        "mentions_cleared": mentions_cleared,
    }


def _walk_occurrence(
    *,
    occ: Occurrence,
    occ_index: int,
    occ_total: int,
    prompt_fn: PromptFn,
    display_fn: DisplayFn,
    today_iso: str,
) -> StaleFix:
    label = "frontmatter ref" if occ.source == "frontmatter" else "body mention [unverified]"

    if occ.line == 0:
        # Frontmatter ref but symbol not found in body — special case.
        display_fn(
            f"\nOccurrence {occ_index + 1}/{occ_total} ({label})\n"
            f"  Symbol: {occ.symbol}\n"
            f"  Body grep: 0 occurrences.\n"
            f"  This page references the symbol only in frontmatter.\n\n"
            f"  Action?\n"
            f"    (1) Clear the frontmatter flag (no body edits)\n"
            f"    (2) Skip and leave the flag"
        )
        choice = prompt_fn("Choice:").strip()
        if choice == "1":
            return StaleFix(occurrence_index=occ_index, action="clear-flag-only")
        return StaleFix(occurrence_index=occ_index, action="skip")

    display_fn(
        f"\nOccurrence {occ_index + 1}/{occ_total} ({label})\n"
        f"  Symbol: {occ.symbol}\n"
        f"  Line {occ.line} — context:\n"
        f"     > {occ.line_text}"
    )
    choice = prompt_fn("Action?  (1) replace  (2) wrap-deprecated  (3) delete  (4) skip").strip()

    if choice == "1":
        new_name = _prompt_new_symbol(prompt_fn, display_fn)
        if new_name is None:
            return StaleFix(occurrence_index=occ_index, action="skip")
        return StaleFix(occurrence_index=occ_index, action="replace", new_symbol=new_name)
    if choice == "2":
        return StaleFix(occurrence_index=occ_index, action="wrap")
    if choice == "3":
        return StaleFix(occurrence_index=occ_index, action="delete")
    return StaleFix(occurrence_index=occ_index, action="skip")


_VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _prompt_new_symbol(prompt_fn: PromptFn, display_fn: DisplayFn) -> str | None:
    for _ in range(3):
        name = prompt_fn("  New symbol name?").strip()
        if not name:
            return None
        if _VALID_IDENTIFIER_RE.match(name):
            return name
        display_fn(f"  ✗ `{name}` is not a valid identifier. Try again.")
    return None


# ---------------------------------------------------------------------
# Diff rendering and application
# ---------------------------------------------------------------------


def _render_diff_preview(
    page: PageState,
    fixes: list[StaleFix],
    today_iso: str,
    auto_clear_flags: bool,
) -> str:
    lines = ["Page diff (in-memory; not yet written):\n"]
    any_action = False
    for fix in fixes:
        occ = page.occurrences[fix.occurrence_index]
        if fix.action == "skip":
            continue
        any_action = True
        if fix.action == "replace":
            lines.append(f"  Line {occ.line}: s/{occ.symbol}/{fix.new_symbol}/")
        elif fix.action == "wrap":
            lines.append(f"  Line {occ.line}: prepend [deprecated {today_iso}]")
        elif fix.action == "delete":
            lines.append(f"  Line {occ.line}: ⌫ delete (\"{occ.line_text[:80]}\")")
        elif fix.action == "clear-flag-only":
            lines.append(f"  Frontmatter: clear stale flag for {occ.symbol} (no body edit)")

    skipped = sum(1 for f in fixes if f.action == "skip")
    if not any_action:
        lines.append("  (all skipped — no edits to apply)")

    if auto_clear_flags and skipped == 0 and any_action:
        lines.append("\nFrontmatter flag clearance:")
        lines.append("  All addressed → stale flags + body_stale_mentions will be removed.")
    elif skipped > 0:
        lines.append(f"\n  ({skipped} skipped — flag retained on this page.)")

    return "\n".join(lines)


def _apply_fixes(
    page: PageState,
    fixes: list[StaleFix],
    today_iso: str,
    auto_clear_flags: bool,
) -> tuple[int, int, int]:
    """Apply non-skip fixes to the page on disk. Returns
    (body_edits_applied, flags_cleared, body_mentions_cleared).
    """
    body_lines = page.body.splitlines(keepends=False)
    keep_line: list[bool] = [True] * len(body_lines)

    body_edits = 0

    # Sort by line descending so deletes don't shift earlier indices we still need.
    actionable = sorted(
        [f for f in fixes if f.action not in ("skip", "clear-flag-only")],
        key=lambda f: -page.occurrences[f.occurrence_index].line,
    )
    for fix in actionable:
        occ = page.occurrences[fix.occurrence_index]
        if occ.line == 0 or occ.line > len(body_lines):
            continue
        idx = occ.line - 1

        if fix.action == "replace":
            assert fix.new_symbol is not None
            body_lines[idx] = body_lines[idx].replace(occ.symbol, fix.new_symbol)
            body_edits += 1
        elif fix.action == "wrap":
            tag = f"[deprecated {today_iso}] "
            if not body_lines[idx].lstrip().startswith("[deprecated "):
                body_lines[idx] = tag + body_lines[idx]
                body_edits += 1
        elif fix.action == "delete":
            keep_line[idx] = False
            body_edits += 1

    # Clear-flag-only counts as a body action only via flag clearance later.
    new_body_lines = [body_lines[i] for i in range(len(body_lines)) if keep_line[i]]
    new_body = "\n".join(new_body_lines)
    if page.body.endswith("\n") and not new_body.endswith("\n"):
        new_body += "\n"

    # Determine if page is fully cleared (no skips and no clear-flag-only stragglers).
    skipped = sum(1 for f in fixes if f.action == "skip")
    fully_cleared = (skipped == 0)

    flags_cleared = 0
    mentions_cleared = 0

    # Always write body if it changed.
    body_changed = new_body != page.body
    if body_changed:
        new_text = page.raw_text[:page.body_offset] + new_body
        page.page_path.write_text(new_text, encoding="utf-8")

    # Frontmatter clearance.
    if auto_clear_flags and fully_cleared:
        # Clear all addressed flags.
        flags_cleared = fm.clear_stale_flags(
            page.page_path,
            stale_keys=page.flagged_keys,
        )
        mentions_cleared = fm.set_body_stale_mentions(page.page_path, mentions=[])
        # set_body_stale_mentions returns the new count; we want the cleared count.
        mentions_cleared = len(page.body_mention_entries) if mentions_cleared == 0 else 0
    elif any(f.action == "clear-flag-only" for f in fixes):
        # Even on partial pages, allow explicit clear-flag-only requests.
        keys_to_clear = {
            (path, occ.symbol)
            for f in fixes if f.action == "clear-flag-only"
            for occ in [page.occurrences[f.occurrence_index]]
            for path, sym in page.flagged_keys
            if sym == occ.symbol
        }
        if keys_to_clear:
            flags_cleared = fm.clear_stale_flags(
                page.page_path,
                stale_keys=keys_to_clear,
            )

    return body_edits, flags_cleared, mentions_cleared


# ---------------------------------------------------------------------
# Session record
# ---------------------------------------------------------------------


def _append_session_record(log_md: Path, result: FixStaleResult, today: date) -> None:
    log_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    record = (
        f"\n## [{timestamp}] from wiki-fix-stale\n"
        f"\n"
        f"Stale-fix session resolved.\n"
        f"- Pages walked:        {result.pages_walked}\n"
        f"- Pages fully cleared: {result.pages_fully_cleared}\n"
        f"- Pages partially handled: {result.pages_partial}\n"
        f"- Pages discarded:     {result.pages_discarded}\n"
        f"- Body edits applied:  {result.body_edits_applied}\n"
        f"- Stale flags cleared: {result.stale_flags_cleared}\n"
        f"- Body mentions resolved: {result.body_mentions_resolved}\n"
    )
    existing = log_md.read_text(encoding="utf-8") if log_md.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    log_md.write_text(existing + record, encoding="utf-8")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _coerce_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"unrecognized date value: {value!r}")
