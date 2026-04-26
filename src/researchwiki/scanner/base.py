"""Symbol dataclass and scan-error type used by every per-extension scanner.

A `Symbol` is the unit recorded in `index/signatures.json`. Every scanner
returns a list of these (plus optionally a list of `ScanError` for files
that could not be parsed).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

SymbolKind = Literal[
    "class",
    "function",
    "method",
    "json-key",
    "md-heading",
]


@dataclass(frozen=True)
class Symbol:
    path: str
    """Repo-relative POSIX path of the file the symbol is defined in."""

    name: str
    """The symbol's name. For nested symbols (methods, JSON keys, headings),
    the name is the leaf — `parent` carries the qualifier."""

    kind: SymbolKind
    """What kind of symbol this is. Drives downstream rendering and lint
    checks."""

    signature: str
    """A short, human-readable signature line. For Python: the def line
    re-stringified. For JSON: a value-type summary. For Markdown: the
    heading text with leading `#`s stripped."""

    line: int
    """1-based line number where the symbol is defined. 0 if unknown
    (e.g., for JSON top-level keys when we did not track positions)."""

    confidence: Literal["verified", "inferred", "dynamic"] = "verified"
    """How confident the scanner is about this binding. AST-extracted
    Python symbols are `verified`. Heuristic body link rot mentions (out
    of scope for v0.1) would be `inferred`."""

    parent: str | None = None
    """Qualifier for nested symbols. For Python methods: the enclosing
    class name. For Markdown subheadings: not used in v0.1. For JSON
    nested keys: not used in v0.1 (only top-level keys are extracted)."""

    extra: dict[str, str] = field(default_factory=dict)
    """Per-kind extra metadata. Kept open for future scanners without
    forcing schema migrations on the dataclass."""

    def to_json(self) -> dict:
        d = asdict(self)
        # Drop empty optional fields so signatures.json stays concise.
        if d["parent"] is None:
            d.pop("parent")
        if not d["extra"]:
            d.pop("extra")
        return d


@dataclass(frozen=True)
class ScanError:
    path: str
    """Repo-relative POSIX path of the file that failed to scan."""

    line: int | None
    """1-based line number where the failure was detected, if applicable.
    None when the failure is file-level (e.g., file unreadable)."""

    message: str
    """Short human-readable description of the failure."""

    def to_json(self) -> dict:
        d = asdict(self)
        if d["line"] is None:
            d.pop("line")
        return d
