"""YAML frontmatter parser used by the wiki-side passes of `wiki-sync`.

We support both *reading* frontmatter (for the reverse-refs build and
the stale-link check) and *writing back* a single specific kind of
edit: marking individual `refs.code` entries `stale: true` with a
`stale_detected:` date.

The writer preserves the rest of the file byte-for-byte; only the
frontmatter block is re-emitted, with the key/value additions applied.
This keeps the wiki-page body untouched (P3) and minimizes
git-diff noise on stale-link runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

import yaml


@dataclass
class FrontmatterDoc:
    raw_text: str
    """Original full file content."""

    frontmatter: dict
    """Parsed frontmatter block (or empty dict if none)."""

    has_frontmatter: bool
    """True if the file had a `---` … `---` block at the top."""

    body_offset: int
    """Byte offset where the body starts (after closing `---\\n`).
    Equal to 0 when there is no frontmatter."""


def load(path: Path) -> FrontmatterDoc:
    text = path.read_text(encoding="utf-8")
    return parse(text)


def parse(text: str) -> FrontmatterDoc:
    if not text.startswith("---"):
        return FrontmatterDoc(raw_text=text, frontmatter={}, has_frontmatter=False, body_offset=0)

    # Find closing `---` after the first line.
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        return FrontmatterDoc(raw_text=text, frontmatter={}, has_frontmatter=False, body_offset=0)

    fm_lines: list[str] = []
    closing_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            closing_idx = i
            break
        fm_lines.append(lines[i])

    if closing_idx is None:
        # Unterminated frontmatter — treat as no frontmatter rather than guess.
        return FrontmatterDoc(raw_text=text, frontmatter={}, has_frontmatter=False, body_offset=0)

    fm_yaml = "".join(fm_lines)
    try:
        data = yaml.safe_load(fm_yaml) or {}
    except yaml.YAMLError:
        # Malformed YAML — return empty dict; the orchestrator records the
        # parse error in `## Scan errors` and skips this page from the
        # stale-link pass.
        data = {}

    body_offset = sum(len(l) for l in lines[: closing_idx + 1])
    return FrontmatterDoc(
        raw_text=text,
        frontmatter=data if isinstance(data, dict) else {},
        has_frontmatter=True,
        body_offset=body_offset,
    )


def code_refs(doc: FrontmatterDoc) -> list[dict]:
    """Return the `refs.code` list as parsed from frontmatter, or `[]`."""
    refs = doc.frontmatter.get("refs")
    if not isinstance(refs, dict):
        return []
    code = refs.get("code")
    if not isinstance(code, list):
        return []
    return [r for r in code if isinstance(r, dict)]


def set_body_stale_mentions(
    path: Path,
    *,
    mentions: list[dict],
) -> int:
    """Replace the page's `body_stale_mentions:` frontmatter field with
    `mentions`. If `mentions` is empty, remove the field entirely.

    Each entry in `mentions` must be a dict with at least `line` and
    `token`; this function does not validate further. Idempotent —
    rewriting with the same content is a no-op (no disk write).

    Returns the number of entries written. Preserves body byte-for-byte.
    """
    doc = load(path)
    if not doc.has_frontmatter:
        return 0

    existing = doc.frontmatter.get("body_stale_mentions") or []
    # Idempotency: bail if nothing changed.
    if existing == mentions:
        return len(mentions) if mentions else 0

    if mentions:
        doc.frontmatter["body_stale_mentions"] = mentions
    else:
        doc.frontmatter.pop("body_stale_mentions", None)

    new_yaml = yaml.safe_dump(
        doc.frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body = doc.raw_text[doc.body_offset:]
    new_text = f"---\n{new_yaml}---\n{body}"
    path.write_text(new_text, encoding="utf-8")
    return len(mentions)


def clear_stale_flags(
    path: Path,
    *,
    stale_keys: set[tuple[str, str]],
) -> int:
    """Remove the `stale: true` and `stale_detected:` keys from every
    `refs.code` entry whose `(path, symbol)` is in `stale_keys`.

    Returns the count of entries cleared. Preserves body. Idempotent.
    """
    doc = load(path)
    if not doc.has_frontmatter:
        return 0

    refs = doc.frontmatter.get("refs")
    if not isinstance(refs, dict):
        return 0
    code = refs.get("code")
    if not isinstance(code, list):
        return 0

    cleared = 0
    for entry in code:
        if not isinstance(entry, dict):
            continue
        key = (str(entry.get("path", "")), str(entry.get("symbol", "")))
        if key in stale_keys and entry.get("stale"):
            entry.pop("stale", None)
            entry.pop("stale_detected", None)
            cleared += 1

    if cleared == 0:
        return 0

    new_yaml = yaml.safe_dump(
        doc.frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body = doc.raw_text[doc.body_offset:]
    new_text = f"---\n{new_yaml}---\n{body}"
    path.write_text(new_text, encoding="utf-8")
    return cleared


def mark_refs_stale(
    path: Path,
    *,
    stale_keys: set[tuple[str, str]],
    detected: _date,
) -> int:
    """Mark every `refs.code` entry in `path`'s frontmatter whose
    `(path, symbol)` pair is in `stale_keys` as `stale: true` with
    `stale_detected: <detected>`. Idempotent — already-stale entries
    are not rewritten with a new date.

    Returns the count of refs newly marked.
    """
    doc = load(path)
    if not doc.has_frontmatter:
        return 0

    refs = doc.frontmatter.get("refs")
    if not isinstance(refs, dict):
        return 0

    code = refs.get("code")
    if not isinstance(code, list):
        return 0

    changed = 0
    for entry in code:
        if not isinstance(entry, dict):
            continue
        key = (str(entry.get("path", "")), str(entry.get("symbol", "")))
        if key in stale_keys and not entry.get("stale"):
            entry["stale"] = True
            entry["stale_detected"] = detected.isoformat()
            changed += 1

    if changed == 0:
        return 0

    new_yaml = yaml.safe_dump(
        doc.frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body = doc.raw_text[doc.body_offset:]
    new_text = f"---\n{new_yaml}---\n{body}"
    path.write_text(new_text, encoding="utf-8")
    return changed
