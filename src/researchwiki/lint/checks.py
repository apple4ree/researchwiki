"""The 8 mechanical wiki-lint checks.

Each check is a pure function from workspace state to `list[Finding]`.
No I/O, no global state, no LLM judgment.

Adding a new check requires extending the catalog here AND in
`wiki-lint/SKILL.md`'s check-catalog table — wiki-lint does not run
ad-hoc checks.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from researchwiki.lint import Finding, PageDoc, Severity

# ---------------------------------------------------------------------
# Required-frontmatter schema (per CLAUDE.md §5).
# ---------------------------------------------------------------------

REQUIRED_FRONTMATTER_FIELDS = (
    "schema_version",
    "type",
    "created",
    "updated",
    "tags",
    "refs",
    "authored_by",
    "source_sessions",
)

VALID_AUTHORED_BY = ("human", "llm", "hybrid")

VALID_TYPES = ("concept", "paper", "experiment", "decision", "other")

# Meta files excluded from Check 8 (orphans).
META_PAGE_NAMES = frozenset({"index.md", "log.md", "questions.md", "discrepancies.md"})


# ---------------------------------------------------------------------
# Body link extraction (used by Check 3 and Check 8).
# ---------------------------------------------------------------------

# Markdown link pattern: [text](target). target captured.
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def extract_intra_wiki_link_targets(body: str, page_path: str, wiki_root: str) -> list[tuple[str, int]]:
    """Return [(target_path, line_no)] for body markdown links that point
    inside the wiki/ tree. Targets are normalized to repo-relative POSIX
    paths.

    Skips:
    - links inside fenced code blocks (``` ... ```)
    - non-wiki links (http://, mailto:, anchor-only #foo, etc.)
    """
    out: list[tuple[str, int]] = []
    in_fence = False
    fence_marker: str | None = None

    page_dir = page_path.rsplit("/", 1)[0] if "/" in page_path else ""
    wiki_root = wiki_root.rstrip("/") + "/"

    for line_no, line in enumerate(body.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif fence_marker == marker:
                in_fence, fence_marker = False, None
            continue
        if in_fence:
            continue

        for match in _MD_LINK_RE.finditer(line):
            target = match.group(1)
            normalized = _normalize_link_target(target, page_dir=page_dir, wiki_root=wiki_root)
            if normalized is not None:
                out.append((normalized, line_no))

    return out


# Wiki sub-directories that, when they appear as the first segment of a
# link target, indicate a wiki-root-relative path. Without this rule the
# link `[foo](concepts/foo.md)` from `wiki/concepts/main.md` would resolve
# to the (wrong) page-dir-relative path `wiki/concepts/concepts/foo.md`.
_WIKI_SUBDIRS = ("concepts", "papers", "experiments", "decisions", "notes")


def _normalize_link_target(target: str, *, page_dir: str, wiki_root: str) -> str | None:
    """Return the normalized repo-relative path if the link points inside
    `wiki_root`, else None.

    Resolution rules:
      1. Anchor and query strings are stripped first.
      2. URL schemes (http://, mailto:, etc.) → return None.
      3. Non-`.md` targets → return None.
      4. Target starting with `wiki/` → used as-is.
      5. Target starting with `/` → repo-root-absolute; lstrip the leading slash.
      6. Target starting with `./` or `../` → resolved relative to page_dir.
      7. Target whose first segment is a known wiki subdirectory
         (`concepts`, `papers`, `experiments`, `decisions`, `notes`) →
         resolved relative to wiki_root (Obsidian-style root-relative).
      8. Otherwise (bare filename or other path) → resolved relative to page_dir.
    """
    if "#" in target:
        target = target.split("#", 1)[0]
    if "?" in target:
        target = target.split("?", 1)[0]
    if not target:
        return None
    if target.startswith(("http://", "https://", "mailto:", "tel:")):
        return None
    if not target.endswith(".md"):
        return None

    if target.startswith(wiki_root):
        # Rule 4: already wiki-rooted.
        resolved = target
    elif target.startswith("/"):
        # Rule 5: repo-root-absolute.
        resolved = target.lstrip("/")
    elif target.startswith(("./", "../")):
        # Rule 6: explicitly page-dir-relative.
        base = page_dir + "/" if page_dir else ""
        resolved = base + target
    elif "/" in target and target.split("/", 1)[0] in _WIKI_SUBDIRS:
        # Rule 7: wiki-root-relative via known subdirectory prefix.
        resolved = wiki_root + target
    else:
        # Rule 8: bare filename → page-dir-relative.
        base = page_dir + "/" if page_dir else ""
        resolved = base + target

    # Collapse `./` and `../`.
    parts: list[str] = []
    for p in resolved.split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            if parts:
                parts.pop()
            continue
        parts.append(p)
    normalized = "/".join(parts)

    if not normalized.startswith(wiki_root):
        return None
    return normalized


# ---------------------------------------------------------------------
# Check 1 — frontmatter required fields.
# ---------------------------------------------------------------------


def check_frontmatter_schema(pages: list[PageDoc], *, wiki_root: str = "wiki/") -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        if _is_meta_page(page.path, wiki_root):
            # Meta pages (log.md / questions.md / discrepancies.md / index.md)
            # are LLM-owned append-only files per CLAUDE.md §3; they do not
            # carry the per-page provenance frontmatter that §5 requires.
            continue
        if page.parse_error:
            findings.append(Finding(
                severity="error",
                category="frontmatter",
                page=page.path,
                message=f"Frontmatter parse failed: {page.parse_error}",
                source_rule="CLAUDE.md §5",
            ))
            continue
        for field in REQUIRED_FRONTMATTER_FIELDS:
            if field not in page.frontmatter:
                findings.append(Finding(
                    severity="error",
                    category="frontmatter",
                    page=page.path,
                    message=f"Missing required field: `{field}`.",
                    source_rule="CLAUDE.md §5 (P7 — every claim has provenance).",
                ))
        # Type validity (when the field is present).
        if "type" in page.frontmatter:
            t = page.frontmatter["type"]
            if t not in VALID_TYPES:
                findings.append(Finding(
                    severity="error",
                    category="frontmatter",
                    page=page.path,
                    message=f"`type: {t}` is not one of {{{', '.join(VALID_TYPES)}}}.",
                    source_rule="CLAUDE.md §5",
                ))
    return findings


# ---------------------------------------------------------------------
# Check 2 — authored_by enum.
# ---------------------------------------------------------------------


def check_authored_by_enum(pages: list[PageDoc]) -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        if page.parse_error:
            continue
        ab = page.frontmatter.get("authored_by")
        if ab is not None and ab not in VALID_AUTHORED_BY:
            findings.append(Finding(
                severity="error",
                category="frontmatter",
                page=page.path,
                message=f"`authored_by: {ab}` is not one of {{{', '.join(VALID_AUTHORED_BY)}}}.",
                source_rule="CLAUDE.md §5, P7.",
            ))
    return findings


# ---------------------------------------------------------------------
# Check 3 — intra-wiki link existence.
# ---------------------------------------------------------------------


def check_intra_wiki_links(
    pages: list[PageDoc],
    *,
    wiki_root: str,
) -> list[Finding]:
    page_paths = {p.path for p in pages}
    findings: list[Finding] = []
    for page in pages:
        for target, line in extract_intra_wiki_link_targets(page.body, page.path, wiki_root):
            if target not in page_paths:
                findings.append(Finding(
                    severity="warn",
                    category="links",
                    page=page.path,
                    message=f"Broken intra-wiki link → `{target}`.",
                    source_rule="README skills table (\"broken links\").",
                    line=line,
                ))
    return findings


# ---------------------------------------------------------------------
# Check 4 — refs.code.path file existence (file-level only).
# ---------------------------------------------------------------------


def check_refs_code_paths(pages: list[PageDoc], *, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        refs = _code_refs(page.frontmatter)
        seen: set[str] = set()
        for ref in refs:
            ref_path = str(ref.get("path", "")).strip()
            if not ref_path or ref_path in seen:
                continue
            seen.add(ref_path)
            if not (repo_root / ref_path).exists():
                findings.append(Finding(
                    severity="warn",
                    category="links",
                    page=page.path,
                    message=f"`refs.code.path` does not exist: `{ref_path}`.",
                    source_rule="P1 — fact and interpretation are separate.",
                ))
    return findings


# ---------------------------------------------------------------------
# Check 5 — speculation density.
# ---------------------------------------------------------------------

# Sentence boundary heuristic: punctuation followed by whitespace or EOL.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Korean sentence-ender heuristic — covers "이다.", "있다.", "한다." etc. plus 다음, etc.
_SPECULATION_TAG = "[speculation]"


def check_speculation_density(
    pages: list[PageDoc],
    *,
    threshold: float,
    wiki_root: str = "wiki/",
) -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        # Meta pages (log / questions / discrepancies / index) are append-only
        # diaries — speculation density doesn't apply.
        if _is_meta_page(page.path, wiki_root):
            continue
        # Skip code fences when counting sentences.
        clean_body = _strip_fences(page.body)
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(clean_body) if s.strip()]
        if len(sentences) < 4:  # too short for a meaningful density signal
            continue
        tagged = sum(1 for s in sentences if _SPECULATION_TAG in s)
        density = tagged / len(sentences)
        if density > threshold:
            findings.append(Finding(
                severity="warn",
                category="speculation",
                page=page.path,
                message=(
                    f"Speculation density {density:.2f} exceeds threshold {threshold:.2f}. "
                    f"{tagged} of {len(sentences)} sentences tagged [speculation]."
                ),
                source_rule="ARCHITECTURE.md §2.5 / §1.4 P8.",
            ))
    return findings


def _strip_fences(body: str) -> str:
    out: list[str] = []
    in_fence = False
    marker: str | None = None
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            m = stripped[:3]
            if not in_fence:
                in_fence, marker = True, m
            elif marker == m:
                in_fence, marker = False, None
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------
# Check 6 — persistent stale-ref age.
# ---------------------------------------------------------------------


def check_stale_age(
    pages: list[PageDoc],
    *,
    threshold_days: int,
    today: date,
) -> list[Finding]:
    findings: list[Finding] = []
    for page in pages:
        for ref in _code_refs(page.frontmatter):
            if not ref.get("stale"):
                continue
            detected = ref.get("stale_detected")
            if detected is None:
                continue
            try:
                detected_date = _coerce_date(detected)
            except ValueError:
                continue
            age = (today - detected_date).days
            if age > threshold_days:
                ref_path = str(ref.get("path", "")).strip()
                ref_symbol = str(ref.get("symbol", "")).strip()
                findings.append(Finding(
                    severity="warn",
                    category="stale",
                    page=page.path,
                    message=(
                        f"Stale ref `{ref_path}:{ref_symbol}` flagged on {detected_date.isoformat()}, "
                        f"unaddressed for {age} days (threshold: {threshold_days})."
                    ),
                    source_rule="wiki-sync's stale-flag contract; lint.stale_age_days.",
                ))
    return findings


def _coerce_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"unrecognized date value: {value!r}")


# ---------------------------------------------------------------------
# Check 7 — cross-page confidence conflict.
# ---------------------------------------------------------------------


def check_confidence_conflicts(pages: list[PageDoc]) -> list[Finding]:
    """For each (path, symbol) referenced by two or more pages with
    distinct `confidence` values, emit one finding."""
    by_key: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for page in pages:
        for ref in _code_refs(page.frontmatter):
            ref_path = str(ref.get("path", "")).strip()
            ref_symbol = str(ref.get("symbol", "")).strip()
            confidence = str(ref.get("confidence", "")).strip()
            if not ref_path or not ref_symbol or not confidence:
                continue
            by_key.setdefault((ref_path, ref_symbol), []).append((page.path, confidence))

    findings: list[Finding] = []
    for (ref_path, ref_symbol), entries in sorted(by_key.items()):
        confidences = {c for _, c in entries}
        if len(confidences) <= 1:
            continue
        page_lines = "; ".join(f"{p} → confidence: {c}" for p, c in sorted(entries))
        findings.append(Finding(
            severity="warn",
            category="contradictions",
            page=f"{ref_path}:{ref_symbol}",  # symbol-keyed, not page-keyed
            message=(
                f"Two or more pages reference this symbol with conflicting confidence values "
                f"({', '.join(sorted(confidences))}): {page_lines}"
            ),
            source_rule="P7 — confidence is a property of the binding evidence, not the page that records it.",
        ))
    return findings


# ---------------------------------------------------------------------
# Check 8 — orphan pages.
# ---------------------------------------------------------------------


def check_orphans(
    pages: list[PageDoc],
    *,
    wiki_root: str,
    grace_days: int,
    today: date,
) -> list[Finding]:
    """A page is `info · orphan` if no other page references it.

    Inbound link sources counted:
    - Frontmatter `refs.{concepts, papers, experiments, decisions}` slugs.
    - Body markdown links resolving to the page's path.

    Excluded from the check:
    - Meta pages (index.md / log.md / questions.md / discrepancies.md at wiki/ root).
    - `seeded_by:` stubs whose `created:` is within `grace_days`.
    """
    page_paths = {p.path for p in pages}

    inbound: dict[str, int] = {p.path: 0 for p in pages}
    for page in pages:
        # Body links.
        for target, _line in extract_intra_wiki_link_targets(page.body, page.path, wiki_root):
            if target in inbound and target != page.path:
                inbound[target] += 1
        # Frontmatter slug refs → resolve to wiki/<kind>/<slug>.md.
        for kind, dirname in (("concepts", "concepts"), ("papers", "papers"),
                              ("experiments", "experiments"), ("decisions", "decisions")):
            slugs = _refs_slug_list(page.frontmatter, kind)
            for slug in slugs:
                resolved = f"{wiki_root.rstrip('/')}/{dirname}/{slug}.md"
                if resolved in inbound and resolved != page.path:
                    inbound[resolved] += 1

    findings: list[Finding] = []
    for page in pages:
        if _is_meta_page(page.path, wiki_root):
            continue
        if inbound.get(page.path, 0) > 0:
            continue
        # Stub grace-period: skip if seeded_by present and within grace window.
        if page.frontmatter.get("seeded_by"):
            created = page.frontmatter.get("created")
            try:
                created_date = _coerce_date(created)
                if (today - created_date).days <= grace_days:
                    continue
            except (TypeError, ValueError):
                pass  # malformed created → treat as old

        findings.append(Finding(
            severity="info",
            category="orphans",
            page=page.path,
            message="No inbound link from any other wiki page.",
            source_rule="README \"gaps\" — orphan-page heuristic.",
        ))
    return findings


def _is_meta_page(path: str, wiki_root: str) -> bool:
    wiki_root = wiki_root.rstrip("/") + "/"
    if not path.startswith(wiki_root):
        return False
    rest = path[len(wiki_root):]
    if "/" in rest:
        return False
    return rest in META_PAGE_NAMES


# ---------------------------------------------------------------------
# Frontmatter helpers.
# ---------------------------------------------------------------------


def _code_refs(frontmatter: dict) -> list[dict]:
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return []
    code = refs.get("code")
    if not isinstance(code, list):
        return []
    return [r for r in code if isinstance(r, dict)]


def _refs_slug_list(frontmatter: dict, kind: str) -> list[str]:
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return []
    items = refs.get(kind)
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict) and "id" in it and isinstance(it["id"], str):
            out.append(it["id"])
    return out


# ---------------------------------------------------------------------
# Severity escalation (used by --strict).
# ---------------------------------------------------------------------


def escalate_to_error(findings: list[Finding]) -> list[Finding]:
    return [
        Finding(
            severity="error",
            category=f.category,
            page=f.page,
            message=f.message,
            source_rule=f.source_rule,
            line=f.line,
        )
        for f in findings
    ]
