"""wiki-lint — mechanical wiki health checks.

This package never modifies wiki page bodies or frontmatter (P3,
stricter than wiki-sync). Findings flow only into:

- `index/audits/lint_YYYYMMDD_HHMM.md` (immutable per-run report)
- `wiki/questions.md` (append) — findings requiring researcher decision
- `wiki/discrepancies.md` (append) — Check 7 confidence conflicts only

Each finding is the deterministic output of a check function; no LLM
judgment is involved in deciding whether something is a problem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warn", "info"]


@dataclass(frozen=True)
class Finding:
    severity: Severity
    category: str       # frontmatter | links | speculation | stale | contradictions | orphans
    page: str           # repo-relative POSIX path; for Check 7, "<path>:<symbol>" key
    message: str        # human-readable observable condition
    source_rule: str    # e.g., "CLAUDE.md §5", "ARCHITECTURE.md §2.5 / §1.4 P8"
    line: int | None = None


@dataclass
class PageDoc:
    """One wiki page loaded into memory, shared across all checks."""

    path: str           # repo-relative POSIX path
    frontmatter: dict   # parsed YAML; {} if absent or malformed
    body: str           # everything after the frontmatter delimiter
    raw_text: str       # full file contents (for line-numbered findings)
    parse_error: str | None = None  # populated if frontmatter failed to parse


from researchwiki.lint.runner import LintResult, run_lint  # noqa: E402

__all__ = ["Finding", "LintResult", "PageDoc", "Severity", "run_lint"]
