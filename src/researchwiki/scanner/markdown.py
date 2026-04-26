"""Markdown ATX heading scanner.

Skips:
- YAML frontmatter at the top of the file (between leading `---` lines).
- Headings inside fenced code blocks (``` ... ``` or ~~~ ... ~~~).

Each heading becomes one Symbol with `kind='md-heading'`. The `parent`
field is unused in v0.1; nested heading hierarchy is not tracked.
"""

from __future__ import annotations

import re

from researchwiki.scanner.base import ScanError, Symbol

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^(```|~~~)")


def scan(path: str, source: str) -> tuple[list[Symbol], list[ScanError]]:
    lines = source.splitlines()
    i = 0
    n = len(lines)

    # Skip frontmatter (--- ... ---) at file start.
    if i < n and lines[i].strip() == "---":
        end = _find_frontmatter_end(lines, i + 1)
        if end is not None:
            i = end + 1

    symbols: list[Symbol] = []
    in_fence: str | None = None

    while i < n:
        line = lines[i]

        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if in_fence is None:
                in_fence = marker
            elif marker == in_fence:
                in_fence = None
            i += 1
            continue

        if in_fence is None:
            m = _ATX_HEADING.match(line)
            if m:
                hashes, text = m.group(1), m.group(2).strip()
                depth = len(hashes)
                symbols.append(Symbol(
                    path=path,
                    name=text,
                    kind="md-heading",
                    signature=f"{'#' * depth} {text}",
                    line=i + 1,
                    extra={"depth": str(depth)},
                ))
        i += 1

    return symbols, []


def _find_frontmatter_end(lines: list[str], start: int) -> int | None:
    """Return the index of the closing `---` line of a frontmatter block,
    or None if no closing delimiter is found within a reasonable window.
    """
    for j in range(start, min(len(lines), start + 200)):
        if lines[j].strip() == "---":
            return j
    return None
