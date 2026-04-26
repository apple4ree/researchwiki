"""Extension → scanner dispatch.

Wiki-internal `.md` files (under `paths.wiki`) are NOT scanned for
headings — they belong to the interpretation layer and are read
separately by the orchestrator's frontmatter pass. Non-wiki `.md`
files (READMEs, docs, etc.) are scanned for headings.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from researchwiki.scanner import json_scanner, markdown, python
from researchwiki.scanner.base import ScanError, Symbol

# (extension lowercase) → scan function
_DISPATCH = {
    ".py": python.scan,
    ".json": json_scanner.scan,
    ".md": markdown.scan,
}


def supported_extensions() -> set[str]:
    return set(_DISPATCH)


def is_supported(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in _DISPATCH


def scan_file(
    path: str,
    source: str,
    *,
    wiki_root: str = "wiki/",
) -> tuple[list[Symbol], list[ScanError]]:
    """Scan one file, dispatching by extension.

    Wiki-internal Markdown files (path begins with `wiki_root`) are not
    scanned — they return empty symbol/error lists so the orchestrator
    can short-circuit them and route to the frontmatter pass instead.
    """
    suffix = PurePosixPath(path).suffix.lower()
    fn = _DISPATCH.get(suffix)
    if fn is None:
        return [], []

    if suffix == ".md" and _is_under(path, wiki_root):
        return [], []

    return fn(path, source)


def _is_under(path: str, root: str) -> bool:
    """Check whether `path` is inside `root` (POSIX-style)."""
    p = PurePosixPath(path)
    r = PurePosixPath(root.rstrip("/") + "/")
    try:
        p.relative_to(r)
        return True
    except ValueError:
        return False
