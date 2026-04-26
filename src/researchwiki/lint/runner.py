"""Top-level orchestrator for `wiki-lint`.

Loads wiki pages, dispatches to all 8 checks, writes the audit report,
and appends to `wiki/questions.md` and `wiki/discrepancies.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from researchwiki.lint import Finding, PageDoc
from researchwiki.lint.checks import (
    check_authored_by_enum,
    check_confidence_conflicts,
    check_frontmatter_schema,
    check_intra_wiki_links,
    check_orphans,
    check_refs_code_paths,
    check_speculation_density,
    check_stale_age,
    escalate_to_error,
)
from researchwiki.lint.report import (
    append_discrepancies,
    append_questions,
    write_audit_report,
)

DEFAULT_SPECULATION_THRESHOLD = 0.30
DEFAULT_STALE_AGE_DAYS = 7
DEFAULT_STUB_GRACE_DAYS = 30


@dataclass
class LintResult:
    findings: list[Finding]
    pages_scanned: int
    report_path: Path | None  # None when --no-write
    questions_appended: int
    discrepancies_appended: int
    exit_code: int  # 0 = success, 1 = strict + findings present


_SCOPE_TO_CHECK = {
    "frontmatter": ("check_frontmatter_schema", "check_authored_by_enum"),
    "links": ("check_intra_wiki_links", "check_refs_code_paths"),
    "speculation": ("check_speculation_density",),
    "stale": ("check_stale_age",),
    "contradictions": ("check_confidence_conflicts",),
    "orphans": ("check_orphans",),
}


def run_lint(
    repo_root: Path,
    *,
    scope: list[str] | None = None,
    strict: bool = False,
    no_write: bool = False,
    report_path: Path | None = None,
    today: date | None = None,
    speculation_threshold: float = DEFAULT_SPECULATION_THRESHOLD,
    stale_age_days: int = DEFAULT_STALE_AGE_DAYS,
    stub_grace_days: int = DEFAULT_STUB_GRACE_DAYS,
) -> LintResult:
    """Run the wiki-lint check catalog and produce findings + report."""
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_root not found or not a directory: {repo_root}")

    wiki_dir = repo_root / "wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"`wiki/` does not exist under {repo_root}; run wiki-init first.")

    today = today or datetime.now().date()
    scope_set = _resolve_scope(scope)

    pages = _load_pages(wiki_dir, repo_root)
    findings: list[Finding] = []

    if "frontmatter" in scope_set:
        findings.extend(check_frontmatter_schema(pages, wiki_root="wiki/"))
        findings.extend(check_authored_by_enum(pages))
    if "links" in scope_set:
        findings.extend(check_intra_wiki_links(pages, wiki_root="wiki/"))
        findings.extend(check_refs_code_paths(pages, repo_root=repo_root))
    if "speculation" in scope_set:
        findings.extend(check_speculation_density(pages, threshold=speculation_threshold, wiki_root="wiki/"))
    if "stale" in scope_set:
        findings.extend(check_stale_age(pages, threshold_days=stale_age_days, today=today))
    if "contradictions" in scope_set:
        findings.extend(check_confidence_conflicts(pages))
    if "orphans" in scope_set:
        findings.extend(check_orphans(pages, wiki_root="wiki/", grace_days=stub_grace_days, today=today))

    if strict:
        findings = escalate_to_error(findings)

    config_summary = {
        "lint.speculation_threshold": speculation_threshold,
        "lint.stale_age_days": stale_age_days,
        "lint.stub_grace_period_days": stub_grace_days,
        "scope": ",".join(sorted(scope_set)),
    }

    questions_appended = 0
    discrepancies_appended = 0
    written_report_path: Path | None = None

    if not no_write:
        if report_path is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M")
            report_path = repo_root / "index" / "audits" / f"lint_{stamp}.md"
        write_audit_report(
            report_path=report_path,
            findings=findings,
            pages_scanned=len(pages),
            config_summary=config_summary,
            strict=strict,
        )
        written_report_path = report_path

        questions_appended = append_questions(wiki_dir / "questions.md", findings)
        discrepancies_appended = append_discrepancies(wiki_dir / "discrepancies.md", findings)

    has_errors = any(f.severity == "error" for f in findings)
    exit_code = 1 if (strict and has_errors) else 0

    return LintResult(
        findings=findings,
        pages_scanned=len(pages),
        report_path=written_report_path,
        questions_appended=questions_appended,
        discrepancies_appended=discrepancies_appended,
        exit_code=exit_code,
    )


# ---------------------------------------------------------------------
# Page loading
# ---------------------------------------------------------------------


def _load_pages(wiki_dir: Path, repo_root: Path) -> list[PageDoc]:
    pages: list[PageDoc] = []
    for md in sorted(wiki_dir.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = md.resolve().relative_to(repo_root.resolve()).as_posix()
        frontmatter, body, error = _split_frontmatter(text)
        pages.append(PageDoc(
            path=rel,
            frontmatter=frontmatter,
            body=body,
            raw_text=text,
            parse_error=error,
        ))
    return pages


def _split_frontmatter(text: str) -> tuple[dict, str, str | None]:
    if not text.startswith("---"):
        return {}, text, None
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        return {}, text, None
    fm_lines: list[str] = []
    closing = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            closing = i
            break
        fm_lines.append(lines[i])
    if closing is None:
        return {}, text, None
    fm_yaml = "".join(fm_lines)
    try:
        data = yaml.safe_load(fm_yaml) or {}
        if not isinstance(data, dict):
            return {}, "".join(lines[closing + 1:]), "frontmatter is not a mapping"
        return data, "".join(lines[closing + 1:]), None
    except yaml.YAMLError as e:
        return {}, "".join(lines[closing + 1:]), f"YAML parse error: {e.__class__.__name__}"


def _resolve_scope(scope: list[str] | None) -> set[str]:
    if not scope or "all" in scope:
        return set(_SCOPE_TO_CHECK)
    invalid = set(scope) - set(_SCOPE_TO_CHECK)
    if invalid:
        raise ValueError(f"unknown scope categories: {sorted(invalid)}")
    return set(scope)
