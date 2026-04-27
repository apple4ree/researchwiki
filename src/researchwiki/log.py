"""wiki-log — mechanical core for the LLM-essential journaling skill.

This module deliberately exposes ONLY the deterministic operations
wiki-log needs. The conversational/reasoning work (interviewing the
researcher, paraphrasing template guides into natural questions,
detecting P8 violations, extracting candidate identifiers/noun phrases,
choosing the summary line) lives in `skills/wiki-log/SKILL.md` and
its `reference/` materials and is performed by the LLM at runtime.

Surface (used via the `wiki-log` CLI by the LLM):

  inspect_template(...)         → template metadata + would-be path
  lookup_code_symbols(...)      → which tokens hit `index/signatures.json`
  find_pages(...)               → which slugs/IDs exist under wiki/<kind>/
  find_amend_target(...)        → most-recent same-type entry within window
  run_log(...)                  → atomic write of entry + log + index + back-refs

Inviolable:
- Never touches the body of an existing wiki page (P3). Edits are
  frontmatter-only on the back-ref targets.
- Never tags `authored_by: llm` (the human's intent is mandatory).
- Never invents speculation routes — the caller (LLM after researcher
  approval) supplies them in the payload.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

from researchwiki import frontmatter as fm

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

VALID_TYPES = ("experiment", "paper", "decision", "free")

SUBDIR_BY_TYPE = {
    "experiment": "experiments",
    "paper": "papers",
    "decision": "decisions",
    "free": "notes",
}

# Each type's index.md category heading (matches wiki-init's seed structure
# loosely; if the category is missing wiki-log will append it).
INDEX_CATEGORY_BY_TYPE = {
    "experiment": "Experiments",
    "paper": "Papers",
    "decision": "Decisions",
    "free": "Notes",
}

# Templates ship under target/templates/<name>.md after wiki-init.
TEMPLATE_FILE_BY_TYPE = {
    "experiment": "experiment.md",
    "paper": "paper_reading.md",
    "decision": "design_decision.md",
    "free": "free_form.md",
}

DEFAULT_AMEND_WINDOW_HOURS = 24

# Section header pattern: `## Title  [required]` or `## Title  [optional]`
_SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*(?:\[(?P<flag>required|optional)\])?\s*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------


@dataclass
class Section:
    title: str
    required: bool
    italic_guide: str
    example: str | None = None

    def to_json(self) -> dict:
        return {
            "title": self.title,
            "required": self.required,
            "italic_guide": self.italic_guide,
            "example": self.example,
        }


@dataclass
class TemplateMeta:
    type: str
    template_path: Path
    entry_frontmatter: dict
    template_directives: dict
    sections: list[Section]
    body_template: str

    def to_json(self) -> dict:
        return {
            "type": self.type,
            "template_path": str(self.template_path),
            "entry_frontmatter": self.entry_frontmatter,
            "template_directives": self.template_directives,
            "sections": [s.to_json() for s in self.sections],
        }


@dataclass
class InspectResult:
    template: TemplateMeta
    entry_path: Path
    today: str
    session_id: str
    git_ref: str | None
    placeholder_values: dict
    existing_peer_pages: list[str]
    signatures_available: bool
    collision: bool

    def to_json(self) -> dict:
        return {
            "template": self.template.to_json(),
            "entry_path": str(self.entry_path),
            "today": self.today,
            "session_id": self.session_id,
            "git_ref": self.git_ref,
            "placeholder_values": self.placeholder_values,
            "existing_peer_pages": self.existing_peer_pages,
            "signatures_available": self.signatures_available,
            "collision": self.collision,
        }


@dataclass
class CodeMatch:
    token: str
    matched: bool
    path: str | None = None
    symbol: str | None = None
    parent: str | None = None
    confidence: Literal["verified", "inferred"] | None = None
    line: int | None = None

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class PageMatch:
    id: str
    matched: bool
    path: str | None = None

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class AmendTarget:
    path: Path
    relative: str
    created: str
    age_hours: float
    body_preview: str

    def to_json(self) -> dict:
        return {
            "path": str(self.path),
            "relative": self.relative,
            "created": self.created,
            "age_hours": self.age_hours,
            "body_preview": self.body_preview,
        }


@dataclass
class StubSpec:
    slug: str
    from_phrase: str

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class QuestionSpec:
    question: str
    context: str

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class LogPayload:
    type: str
    title: str
    today: str
    session_id: str
    git_ref: str | None = None
    section_answers: dict[str, str] = field(default_factory=dict)
    approved_refs: dict = field(default_factory=lambda: {
        "code": [], "papers": [], "concepts": [], "experiments": [],
    })
    approved_stubs: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    summary_line: str = ""
    authored_by: Literal["human", "hybrid"] = "hybrid"
    extra_frontmatter: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "LogPayload":
        return cls(
            type=data["type"],
            title=data["title"],
            today=data["today"],
            session_id=data["session_id"],
            git_ref=data.get("git_ref"),
            section_answers=data.get("section_answers", {}),
            approved_refs=data.get("approved_refs", {
                "code": [], "papers": [], "concepts": [], "experiments": [],
            }),
            approved_stubs=data.get("approved_stubs", []),
            questions=data.get("questions", []),
            summary_line=data.get("summary_line", ""),
            authored_by=data.get("authored_by", "hybrid"),
            extra_frontmatter=data.get("extra_frontmatter", {}),
        )


@dataclass
class LogResult:
    entry_path: Path
    log_md_appended: bool
    index_md_updated: bool
    backrefs_added: int
    stubs_created: list[Path]
    questions_appended: int

    def to_json(self) -> dict:
        return {
            "entry_path": str(self.entry_path),
            "log_md_appended": self.log_md_appended,
            "index_md_updated": self.index_md_updated,
            "backrefs_added": self.backrefs_added,
            "stubs_created": [str(p) for p in self.stubs_created],
            "questions_appended": self.questions_appended,
        }


# ---------------------------------------------------------------------
# Conversation-as-source candidate validation
# ---------------------------------------------------------------------


@dataclass
class CandidateDraft:
    """LLM-produced draft entry extracted from conversation context.

    Section answers are the LLM's first-pass extraction; extracted_refs
    are *raw* tokens / phrases / IDs found in the prose, not yet
    confirmed against signatures.json or the wiki. Both go through
    `validate_candidate` to get a status the LLM uses to drive the
    batch UI ([a]uto-save / [r]eview / [f]ull / [d]rop).
    """

    type: str
    title: str
    today: str
    session_id: str
    section_answers: dict[str, str] = field(default_factory=dict)
    extracted_refs: dict = field(default_factory=lambda: {
        "code_tokens": [],
        "concepts_phrases": [],
        "experiments_ids": [],
        "papers_slugs": [],
    })
    git_ref: str | None = None
    summary_line: str = ""

    @classmethod
    def from_json(cls, data: dict) -> "CandidateDraft":
        return cls(
            type=data["type"],
            title=data["title"],
            today=data["today"],
            session_id=data["session_id"],
            section_answers=data.get("section_answers", {}),
            extracted_refs=data.get("extracted_refs", {
                "code_tokens": [], "concepts_phrases": [],
                "experiments_ids": [], "papers_slugs": [],
            }),
            git_ref=data.get("git_ref"),
            summary_line=data.get("summary_line", ""),
        )


@dataclass
class CandidateValidation:
    """Output of `validate_candidate` — annotates the draft for the LLM."""

    type: str
    title: str
    entry_path: str
    status: Literal["ok", "needs-review", "fatal"]
    issues: list[dict]
    ref_resolution: dict
    collision: bool

    def to_json(self) -> dict:
        return {
            "type": self.type,
            "title": self.title,
            "entry_path": self.entry_path,
            "status": self.status,
            "issues": self.issues,
            "ref_resolution": self.ref_resolution,
            "collision": self.collision,
        }


def validate_candidate(
    repo_root: Path, *, draft: CandidateDraft,
) -> CandidateValidation:
    """Validate an extracted candidate against the workspace.

    Checks (in order):
      1. Template parses; required-section completeness.
      2. P8 first-pass markers in section answers (regex-based; LLM refines).
      3. Ref resolution — code tokens against signatures.json, concept
         phrases against wiki/concepts/, experiment IDs against
         wiki/experiments/, paper slugs against wiki/papers/.
      4. Path collision against the would-be entry file.

    Returns a `CandidateValidation` with a high-level `status`:
      - `fatal`: cannot save (e.g., missing required section, collision).
      - `needs-review`: P8 markers present, or ambiguous/unresolved refs;
        the LLM should ask the researcher about flagged items only.
      - `ok`: clean — auto-save in the [a] tier is safe.
    """
    from researchwiki.p8 import scan_section_answers

    if draft.type not in VALID_TYPES:
        raise ValueError(f"unknown --type {draft.type!r}")
    repo_root = repo_root.resolve()
    today = date.fromisoformat(draft.today)

    template_path = _resolve_template_path(repo_root, draft.type)
    template = _parse_template(template_path, type=draft.type)

    issues: list[dict] = []

    # 1. Required-section completeness.
    for section in template.sections:
        if section.required:
            answer = (draft.section_answers.get(section.title) or "").strip()
            if not answer:
                issues.append({
                    "kind": "missing-required",
                    "severity": "fatal",
                    "section": section.title,
                })

    # 2. P8 markers.
    for m in scan_section_answers(draft.section_answers):
        issues.append({
            "kind": "p8-marker",
            "severity": "review",
            "section": m.section,
            "marker": m.marker,
            "marker_kind": m.kind,
            "span": [m.start, m.end],
        })

    # 3. Ref resolution.
    refs_in = draft.extracted_refs or {}
    code_tokens = refs_in.get("code_tokens") or []
    concept_phrases = refs_in.get("concepts_phrases") or []
    experiment_ids = refs_in.get("experiments_ids") or []
    paper_slugs = refs_in.get("papers_slugs") or []

    code_resolution: list[dict] = []
    if code_tokens:
        for cm in lookup_code_symbols(repo_root, tokens=code_tokens):
            code_resolution.append(cm.to_json())
            if not cm.matched:
                issues.append({
                    "kind": "ref-unresolved",
                    "severity": "review",
                    "ref_kind": "code",
                    "token": cm.token,
                })

    concept_resolution: list[dict] = []
    if concept_phrases:
        slugs = [_slugify_concept(p) for p in concept_phrases]
        page_matches = find_pages(repo_root, kind="concepts", ids=slugs)
        for phrase, pm in zip(concept_phrases, page_matches):
            concept_resolution.append({
                "phrase": phrase,
                "slug": pm.id,
                "matched": pm.matched,
                "path": pm.path,
                "stub_candidate": not pm.matched,
            })
            if not pm.matched:
                issues.append({
                    "kind": "stub-candidate",
                    "severity": "review",
                    "phrase": phrase,
                    "slug": pm.id,
                })

    experiment_resolution: list[dict] = []
    if experiment_ids:
        for pm in find_pages(repo_root, kind="experiments", ids=experiment_ids):
            experiment_resolution.append(pm.to_json())
            if not pm.matched:
                issues.append({
                    "kind": "ref-unresolved",
                    "severity": "review",
                    "ref_kind": "experiments",
                    "id": pm.id,
                })

    paper_resolution: list[dict] = []
    if paper_slugs:
        for pm in find_pages(repo_root, kind="papers", ids=paper_slugs):
            paper_resolution.append(pm.to_json())
            if not pm.matched:
                issues.append({
                    "kind": "ref-unresolved",
                    "severity": "review",
                    "ref_kind": "papers",
                    "slug": pm.id,
                })

    # 4. Collision.
    entry_path = _compute_entry_path(repo_root, type=draft.type,
                                     title=draft.title, today=today)
    collision = entry_path.exists()
    if collision:
        issues.append({
            "kind": "collision",
            "severity": "fatal",
            "entry_path": str(entry_path.relative_to(repo_root)),
        })

    # Roll up status.
    has_fatal = any(i["severity"] == "fatal" for i in issues)
    if has_fatal:
        status: Literal["ok", "needs-review", "fatal"] = "fatal"
    elif issues:
        status = "needs-review"
    else:
        status = "ok"

    return CandidateValidation(
        type=draft.type,
        title=draft.title,
        entry_path=str(entry_path.relative_to(repo_root)),
        status=status,
        issues=issues,
        ref_resolution={
            "code": code_resolution,
            "concepts": concept_resolution,
            "experiments": experiment_resolution,
            "papers": paper_resolution,
        },
        collision=collision,
    )


def _slugify_concept(phrase: str) -> str:
    """Turn a noun phrase into a slug per reference/auto-link-extraction.md §5.

    Lowercase, ASCII spaces → hyphens, strip leading articles, drop
    trailing 's' (heuristic). Korean characters are preserved as-is.
    """
    s = phrase.strip().lower()
    # Strip leading English articles only — Korean has none.
    for prefix in ("the ", "a ", "an "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    # Spaces / punctuation → hyphens; collapse runs.
    s = re.sub(r"[\s_/]+", "-", s)
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    # Trailing s heuristic — only for ASCII (avoid mangling Korean).
    if s.endswith("s") and s[-2:-1].isascii() and not s.endswith("ss"):
        s = s[:-1]
    return s


# ---------------------------------------------------------------------
# Public — inspect
# ---------------------------------------------------------------------


def inspect_template(
    repo_root: Path,
    *,
    type: str,
    title: str,
    today: date | None = None,
    session_id: str | None = None,
    git_ref: str | None = None,
) -> InspectResult:
    """Parse the relevant template, compute the would-be entry path,
    and report the surrounding workspace state the LLM needs to drive
    the conversation.

    Raises `ValueError` for unknown type; `FileNotFoundError` if the
    workspace lacks `templates/` or the specific template file.
    """
    if type not in VALID_TYPES:
        raise ValueError(f"unknown --type {type!r}; expected one of {VALID_TYPES}")
    repo_root = repo_root.resolve()
    today = today or datetime.now().date()
    session_id = session_id or _default_session_id(today)
    if git_ref is None:
        git_ref = _detect_git_ref(repo_root)

    template_path = _resolve_template_path(repo_root, type)
    template = _parse_template(template_path, type=type)

    entry_path = _compute_entry_path(repo_root, type=type, title=title, today=today)
    placeholders = _compute_placeholders(
        type=type, title=title, today=today, session_id=session_id, git_ref=git_ref,
    )

    peer_dir = entry_path.parent
    if peer_dir.exists():
        existing_peer_pages = sorted(
            p.relative_to(repo_root).as_posix()
            for p in peer_dir.glob("*.md")
        )
    else:
        existing_peer_pages = []

    signatures = repo_root / "index" / "signatures.json"
    return InspectResult(
        template=template,
        entry_path=entry_path,
        today=today.isoformat(),
        session_id=session_id,
        git_ref=git_ref,
        placeholder_values=placeholders,
        existing_peer_pages=existing_peer_pages,
        signatures_available=signatures.exists(),
        collision=entry_path.exists(),
    )


# ---------------------------------------------------------------------
# Public — lookups
# ---------------------------------------------------------------------


def lookup_code_symbols(repo_root: Path, *, tokens: list[str]) -> list[CodeMatch]:
    """For each token, return whether it uniquely matches an entry in
    `index/signatures.json`. Supports bare names (`train_one_epoch`),
    dotted names (`Trainer.train_one_epoch`), and bare file paths
    (`src/trainer.py`, returned as a path-only match).

    Tokens not in the index return `matched=False` — the LLM may then
    ask the researcher whether to record them as `confidence: inferred`.
    """
    repo_root = repo_root.resolve()
    sig_path = repo_root / "index" / "signatures.json"
    if not sig_path.exists():
        return [CodeMatch(token=t, matched=False) for t in tokens]

    try:
        data = json.loads(sig_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [CodeMatch(token=t, matched=False) for t in tokens]

    symbols = data.get("symbols", []) if isinstance(data, dict) else []

    by_name: dict[str, list[dict]] = {}
    by_dotted: dict[str, list[dict]] = {}
    paths_seen: set[str] = set()
    for s in symbols:
        if not isinstance(s, dict):
            continue
        name = s.get("name", "")
        parent = s.get("parent")
        if name:
            by_name.setdefault(name, []).append(s)
        if parent:
            by_dotted.setdefault(f"{parent}.{name}", []).append(s)
        path = s.get("path")
        if path:
            paths_seen.add(path)

    out: list[CodeMatch] = []
    for token in tokens:
        # Path-shape token (contains '/' or ends '.py'/'.md'/etc.).
        if "/" in token or token.endswith((".py", ".md", ".ts", ".js", ".tsx")):
            if token in paths_seen:
                out.append(CodeMatch(
                    token=token, matched=True, path=token,
                    confidence="verified",
                ))
                continue
            out.append(CodeMatch(token=token, matched=False))
            continue

        # Dotted name first (more specific).
        hits = by_dotted.get(token) or by_name.get(token)
        if not hits:
            out.append(CodeMatch(token=token, matched=False))
            continue
        if len(hits) > 1:
            # Ambiguous — leave it to the LLM/researcher to disambiguate.
            out.append(CodeMatch(token=token, matched=False))
            continue
        s = hits[0]
        out.append(CodeMatch(
            token=token,
            matched=True,
            path=s.get("path"),
            symbol=s.get("name"),
            parent=s.get("parent"),
            confidence="verified",
            line=s.get("line"),
        ))
    return out


def find_pages(
    repo_root: Path,
    *,
    kind: Literal["concepts", "papers", "experiments", "decisions"],
    ids: list[str],
) -> list[PageMatch]:
    """Exact-slug match against `wiki/<kind>/<id>.md`. The trailing
    `.md` is added if missing. The id may already include a date prefix
    for experiments (`exp-YYYY-MM-DD-foo`).
    """
    repo_root = repo_root.resolve()
    base = repo_root / "wiki" / kind
    out: list[PageMatch] = []
    for raw in ids:
        slug = raw if raw.endswith(".md") else f"{raw}.md"
        candidate = base / slug
        if candidate.is_file():
            out.append(PageMatch(
                id=raw,
                matched=True,
                path=candidate.relative_to(repo_root).as_posix(),
            ))
        else:
            out.append(PageMatch(id=raw, matched=False))
    return out


def find_amend_target(
    repo_root: Path,
    *,
    type: str,
    window_hours: int = DEFAULT_AMEND_WINDOW_HOURS,
    now: datetime | None = None,
) -> AmendTarget | None:
    """Return the most-recent same-`type` entry whose `created:` (or
    file mtime as fallback) is within `window_hours` of `now`. None if
    no matching entry exists or the most recent is past the window.
    """
    if type not in VALID_TYPES:
        raise ValueError(f"unknown --type {type!r}")
    repo_root = repo_root.resolve()
    now = now or datetime.now()
    subdir = repo_root / "wiki" / SUBDIR_BY_TYPE[type]
    if not subdir.is_dir():
        return None

    candidates: list[tuple[datetime, Path]] = []
    for md in subdir.glob("*.md"):
        when = _entry_timestamp(md)
        if when is None:
            continue
        candidates.append((when, md))
    if not candidates:
        return None

    candidates.sort(reverse=True)
    when, path = candidates[0]
    age = (now - when).total_seconds() / 3600.0
    if age > window_hours:
        return None

    body = _read_body(path)
    preview = "\n".join(body.splitlines()[:30])
    return AmendTarget(
        path=path,
        relative=path.relative_to(repo_root).as_posix(),
        created=when.isoformat(timespec="minutes"),
        age_hours=round(age, 2),
        body_preview=preview,
    )


# ---------------------------------------------------------------------
# Public — atomic write
# ---------------------------------------------------------------------


def run_log(repo_root: Path, *, payload: LogPayload) -> LogResult:
    """Atomic write phase. Performs:

      1. Compose entry frontmatter (template + substituted placeholders
         + approved refs + extra fields) and body (section answers in
         template order).
      2. Write entry file (refuses if path exists — caller must use
         `--amend` for in-place edits).
      3. Append a single block to `wiki/log.md`.
      4. Update `wiki/index.md` (insert link under the type's category
         heading; create the heading if missing).
      5. For approved refs whose template directive declares
         `link_bidirectional: true`, append a back-ref to the target
         page's frontmatter (frontmatter-only edit, P3-permitted).
      6. For each approved stub, create `wiki/concepts/<slug>.md` with
         frontmatter + the single-italicized-line body.
      7. Append each approved P8 question to `wiki/questions.md`.

    Validation:
      - `authored_by` must be `human` or `hybrid` (`llm` rejected).
      - Template's `[required]` sections must all have non-empty answers.
      - Path collision raises `FileExistsError`.
    """
    if payload.authored_by not in ("human", "hybrid"):
        raise ValueError(
            f"authored_by={payload.authored_by!r} forbidden — wiki-log entries require human intent"
        )
    if payload.type not in VALID_TYPES:
        raise ValueError(f"unknown --type {payload.type!r}")
    repo_root = repo_root.resolve()

    template_path = _resolve_template_path(repo_root, payload.type)
    template = _parse_template(template_path, type=payload.type)

    today_date = date.fromisoformat(payload.today)
    entry_path = _compute_entry_path(repo_root, type=payload.type,
                                     title=payload.title, today=today_date)
    if entry_path.exists():
        raise FileExistsError(
            f"target entry already exists: {entry_path}; use --amend or pick a new --title"
        )

    # Required-section validation.
    missing = []
    for section in template.sections:
        if section.required:
            answer = (payload.section_answers.get(section.title) or "").strip()
            if not answer:
                missing.append(section.title)
    if missing:
        raise ValueError(
            f"required section(s) blank: {missing}; "
            "abort with no output rather than write an incomplete entry"
        )

    placeholders = _compute_placeholders(
        type=payload.type, title=payload.title, today=today_date,
        session_id=payload.session_id, git_ref=payload.git_ref,
    )
    entry_frontmatter = _materialize_entry_frontmatter(
        template_frontmatter=template.entry_frontmatter,
        placeholders=placeholders,
        approved_refs=payload.approved_refs,
        authored_by=payload.authored_by,
        session_id=payload.session_id,
        extra=payload.extra_frontmatter,
    )

    body_text = _render_body(
        title=payload.title,
        sections=template.sections,
        answers=payload.section_answers,
    )

    entry_path.parent.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(
        _serialize_entry(entry_frontmatter, body_text),
        encoding="utf-8",
    )

    # log.md append
    log_md = repo_root / "wiki" / "log.md"
    when = datetime.now()
    _append_log_block(
        log_md,
        type=payload.type,
        title=payload.title,
        summary=(payload.summary_line or "").strip(),
        relative_path=entry_path.relative_to(repo_root).as_posix(),
        when=when,
    )

    # index.md update
    index_md = repo_root / "wiki" / "index.md"
    _insert_index_link(
        index_md,
        type=payload.type,
        title=payload.title,
        relative_path=entry_path.relative_to(repo_root).as_posix(),
    )

    # back-refs (frontmatter-only, P3-permitted)
    backrefs_added = _apply_backrefs(
        repo_root,
        new_entry_slug=_back_ref_slug(payload.type, payload.title, today_date),
        approved_refs=payload.approved_refs,
        directives=template.template_directives,
    )

    # stubs
    stubs_created = []
    for stub in payload.approved_stubs:
        spec = StubSpec(slug=stub["slug"], from_phrase=stub["from_phrase"])
        path = _create_concept_stub(
            repo_root,
            spec=spec,
            today=today_date,
            session_id=payload.session_id,
            from_entry=entry_path.relative_to(repo_root).as_posix(),
        )
        if path is not None:
            stubs_created.append(path)

    # questions
    questions_appended = 0
    if payload.questions:
        q_md = repo_root / "wiki" / "questions.md"
        questions_appended = _append_questions(
            q_md,
            entries=[QuestionSpec(question=q["question"], context=q["context"])
                     for q in payload.questions],
            source_entry=entry_path.relative_to(repo_root).as_posix(),
            when=when,
        )

    return LogResult(
        entry_path=entry_path,
        log_md_appended=True,
        index_md_updated=True,
        backrefs_added=backrefs_added,
        stubs_created=stubs_created,
        questions_appended=questions_appended,
    )


# ---------------------------------------------------------------------
# Internals — template parsing
# ---------------------------------------------------------------------


def _resolve_template_path(repo_root: Path, type: str) -> Path:
    name = TEMPLATE_FILE_BY_TYPE[type]
    candidate = repo_root / "templates" / name
    if not candidate.is_file():
        raise FileNotFoundError(
            f"template not found: {candidate}. Run `wiki-init` or restore the template."
        )
    return candidate


def _parse_template(path: Path, *, type: str) -> TemplateMeta:
    raw_text = path.read_text(encoding="utf-8")
    # Templates may start with an HTML comment (researcher-facing notes
    # about how the template is consumed). Strip leading comment blocks
    # and blank lines before handing the rest to the frontmatter parser.
    stripped = _strip_leading_comments(raw_text)
    # Bare `{{KEY}}` placeholders are valid template syntax but invalid
    # YAML (parsed as flow-style mappings). Quote them so YAML reads them
    # as strings; the substitution pass downstream restores the value.
    quoted = _PLACEHOLDER_RE.sub(r"'\g<0>'", stripped)
    doc = fm.parse(quoted)
    raw_fm = dict(doc.frontmatter) if doc.has_frontmatter else {}
    template_directives = raw_fm.pop("_template", {}) or {}
    if not isinstance(template_directives, dict):
        template_directives = {}

    # Body is taken from the un-quoted form so placeholder rendering
    # downstream (if any body-side substitution were ever added) sees
    # the original template syntax.
    body = stripped[fm.parse(stripped).body_offset:] if doc.has_frontmatter else stripped

    sections = _parse_sections(body)

    return TemplateMeta(
        type=type,
        template_path=path,
        entry_frontmatter=raw_fm,
        template_directives=template_directives,
        sections=sections,
        body_template=body,
    )


_PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")


def _strip_leading_comments(text: str) -> str:
    """Strip leading `<!-- ... -->` blocks and blank lines so the remaining
    text starts with the `---` frontmatter delimiter.
    """
    pos = 0
    n = len(text)
    while pos < n:
        # Skip blank lines.
        while pos < n and text[pos] in (" ", "\t"):
            pos += 1
        if pos < n and text[pos] == "\n":
            pos += 1
            continue
        # Skip an HTML comment block.
        if text.startswith("<!--", pos):
            end = text.find("-->", pos + 4)
            if end == -1:
                break
            pos = end + 3
            # Consume any trailing newline after the closing -->.
            if pos < n and text[pos] == "\n":
                pos += 1
            continue
        break
    return text[pos:]


def _parse_sections(body: str) -> list[Section]:
    """Walk the template body and pull out each `## Section [flag]` block.

    For each section: extract the italic guide (the first `*...*` block
    in the section body) and the first `<!-- example: ... -->` HTML
    comment if any.
    """
    sections: list[Section] = []
    lines = body.splitlines()

    current_title: str | None = None
    current_required: bool = False
    current_lines: list[str] = []

    def flush():
        if current_title is None:
            return
        guide, example = _extract_guide_and_example("\n".join(current_lines))
        sections.append(Section(
            title=current_title,
            required=current_required,
            italic_guide=guide,
            example=example,
        ))

    for raw_line in lines:
        m = _SECTION_RE.match(raw_line.rstrip())
        if m:
            flush()
            current_title = m.group("title").strip()
            current_required = (m.group("flag") == "required")
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(raw_line)

    flush()
    return sections


def _extract_guide_and_example(text: str) -> tuple[str, str | None]:
    """Heuristic: italic guide = the first contiguous italics block
    (paragraph wrapped in `*...*`). Example = the first HTML comment
    starting `<!-- ` (e.g., `<!-- 예: ... -->`).
    """
    guide_lines: list[str] = []
    in_italic = False
    found_any = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_italic and stripped.startswith("*") and not stripped.startswith("**"):
            in_italic = True
            found_any = True
            guide_lines.append(stripped.lstrip("*").rstrip())
            if stripped.endswith("*") and len(stripped) > 1 and not stripped.endswith("**"):
                in_italic = False
            continue
        if in_italic:
            guide_lines.append(stripped.rstrip("*"))
            if stripped.endswith("*") and not stripped.endswith("**"):
                in_italic = False
            continue
        if found_any:
            break

    guide = " ".join(g for g in guide_lines if g).strip()

    example_match = _HTML_COMMENT_RE.search(text)
    example = example_match.group(0) if example_match else None
    if example is not None:
        # Strip <!-- ... --> wrapper, leaving inner content.
        inner = example[4:-3].strip()
        # Drop a leading "예:" / "example:" label if present.
        for prefix in ("예:", "Example:", "example:", "예시:"):
            if inner.startswith(prefix):
                inner = inner[len(prefix):].strip()
                break
        example = inner or None

    return guide, example


# ---------------------------------------------------------------------
# Internals — paths & placeholders
# ---------------------------------------------------------------------


def _compute_entry_path(
    repo_root: Path, *, type: str, title: str, today: date,
) -> Path:
    subdir = SUBDIR_BY_TYPE[type]
    if type == "experiment":
        slug = f"exp-{today.isoformat()}-{title}"
    elif type == "free":
        slug = f"{today.isoformat()}-{title}"
    else:
        slug = title
    return repo_root / "wiki" / subdir / f"{slug}.md"


def _back_ref_slug(type: str, title: str, today: date) -> str:
    if type == "experiment":
        return f"exp-{today.isoformat()}-{title}"
    if type == "free":
        return f"{today.isoformat()}-{title}"
    return title


def _compute_placeholders(
    *, type: str, title: str, today: date, session_id: str, git_ref: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "DATE": today.isoformat(),
        "SESSION_ID": session_id,
        "GIT_REF": git_ref,
        "TITLE": title,
    }
    if type == "paper":
        out["PAPER_ID"] = title
    if type == "decision":
        out["DECISION_ID"] = title
    return out


def _default_session_id(today: date) -> str:
    # Match wiki-log examples: `2026-04-23-s3` (date + sequence). Without
    # a registry of past sessions, use a coarse `s1`. Callers (the CLI,
    # or later an LLM bridge) may override.
    return f"{today.isoformat()}-s1"


def _detect_git_ref(repo_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short=7", "HEAD"],
            capture_output=True, text=True, timeout=2.0,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
    return None


# ---------------------------------------------------------------------
# Internals — entry assembly
# ---------------------------------------------------------------------


def _materialize_entry_frontmatter(
    *,
    template_frontmatter: dict,
    placeholders: dict,
    approved_refs: dict,
    authored_by: str,
    session_id: str,
    extra: dict,
) -> dict:
    """Substitute `{{PLACEHOLDER}}` strings in the template frontmatter
    and overlay approved refs + provenance.
    """
    materialized = _substitute_strings(template_frontmatter, placeholders)
    if not isinstance(materialized, dict):
        materialized = {}

    # Approved refs override the template's empty-list placeholders.
    refs = materialized.setdefault("refs", {
        "code": [], "papers": [], "concepts": [], "experiments": [],
    })
    for kind in ("code", "papers", "concepts", "experiments"):
        approved = approved_refs.get(kind, [])
        if approved:
            refs[kind] = approved
        else:
            refs.setdefault(kind, [])

    materialized["authored_by"] = authored_by
    sessions = materialized.get("source_sessions") or []
    if not isinstance(sessions, list):
        sessions = []
    if session_id not in sessions:
        sessions.append(session_id)
    materialized["source_sessions"] = sessions

    # Extra template-specific fields (e.g., `year` for paper, `seed` /
    # `run_duration` for experiment) — write whatever the LLM gathered.
    for k, v in extra.items():
        materialized[k] = v

    return materialized


def _substitute_strings(value: Any, placeholders: dict) -> Any:
    """Recursive `{{KEY}}` substitution, preserving structure."""
    if isinstance(value, str):
        out = value
        for k, v in placeholders.items():
            token = "{{" + k + "}}"
            if token in out:
                out = out.replace(token, "" if v is None else str(v))
        # If the substituted string equals exactly an empty string and
        # the original was a single `{{NULL}}` placeholder, return None.
        return out if out else None if value.startswith("{{") and value.endswith("}}") else out
    if isinstance(value, list):
        return [_substitute_strings(v, placeholders) for v in value]
    if isinstance(value, dict):
        return {k: _substitute_strings(v, placeholders) for k, v in value.items()}
    return value


def _render_body(
    *, title: str, sections: list[Section], answers: dict[str, str],
) -> str:
    out: list[str] = [f"# {title}", ""]
    for sec in sections:
        ans = (answers.get(sec.title) or "").rstrip()
        if not ans and not sec.required:
            # Skip optional sections with no answer.
            continue
        out.append(f"## {sec.title}")
        out.append(ans)
        out.append("")
    # Trim trailing blanks.
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def _serialize_entry(frontmatter: dict, body: str) -> str:
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False,
    )
    return f"---\n{yaml_text}---\n\n{body}"


# ---------------------------------------------------------------------
# Internals — log.md / index.md
# ---------------------------------------------------------------------


def _append_log_block(
    log_md: Path, *, type: str, title: str, summary: str,
    relative_path: str, when: datetime,
) -> None:
    log_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = when.strftime("%Y-%m-%d %H:%M")
    block = (
        f"\n## [{timestamp}] log | {type} | {title}\n"
        f"\n{summary}\n"
        f"\n→ {relative_path}\n"
    )
    if log_md.exists():
        existing = log_md.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        log_md.write_text(existing + block, encoding="utf-8")
    else:
        log_md.write_text(
            "# wiki/log.md\n\nAppend-only research journal. wiki-log writes here.\n" + block,
            encoding="utf-8",
        )


def _insert_index_link(
    index_md: Path, *, type: str, title: str, relative_path: str,
) -> None:
    """Insert `- [title](relative-from-wiki)` under the type's category
    heading. Create the heading if missing. Idempotent.
    """
    category = INDEX_CATEGORY_BY_TYPE[type]
    rel_from_wiki = _strip_wiki_prefix(relative_path)
    line = f"- [{title}]({rel_from_wiki})"

    index_md.parent.mkdir(parents=True, exist_ok=True)
    if not index_md.exists():
        index_md.write_text(
            f"# wiki/index.md\n\n## {category}\n{line}\n",
            encoding="utf-8",
        )
        return

    text = index_md.read_text(encoding="utf-8")
    if line in text.splitlines():
        return  # idempotency

    heading = f"## {category}"
    if heading in text:
        # Insert immediately after the heading line.
        new_lines: list[str] = []
        inserted = False
        for raw in text.splitlines(keepends=False):
            new_lines.append(raw)
            if not inserted and raw.strip() == heading:
                new_lines.append(line)
                inserted = True
        new_text = "\n".join(new_lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
        index_md.write_text(new_text, encoding="utf-8")
        return

    # Heading missing — append both heading and line at end.
    if text and not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"
    index_md.write_text(text + f"## {category}\n{line}\n", encoding="utf-8")


def _strip_wiki_prefix(relative_path: str) -> str:
    return relative_path[len("wiki/"):] if relative_path.startswith("wiki/") else relative_path


# ---------------------------------------------------------------------
# Internals — back-refs
# ---------------------------------------------------------------------


def _apply_backrefs(
    repo_root: Path, *,
    new_entry_slug: str,
    approved_refs: dict,
    directives: dict,
) -> int:
    """For each approved ref of a kind whose template directive sets
    `link_bidirectional: true`, append the new entry's slug to the
    target page's `refs.<kind>` (or back-target equivalent).

    Returns count of pages whose frontmatter was extended.
    """
    auto_link = directives.get("auto_link", {}) if isinstance(directives, dict) else {}
    added = 0
    for kind in ("experiments", "concepts", "papers"):
        rule = auto_link.get(kind, {}) if isinstance(auto_link, dict) else {}
        if not (isinstance(rule, dict) and rule.get("link_bidirectional")):
            continue
        for ref in approved_refs.get(kind, []):
            ref_slug = ref if isinstance(ref, str) else ref.get("slug") or ref.get("id")
            if not ref_slug:
                continue
            target = repo_root / "wiki" / kind / f"{ref_slug}.md"
            if not target.is_file():
                continue
            if _append_backref(target, kind=_kind_to_singular_for_target(kind),
                               new_slug=new_entry_slug):
                added += 1
    return added


def _kind_to_singular_for_target(kind: str) -> str:
    # Back-ref's *bucket on the target page* mirrors the kind exactly:
    # an experiment-to-experiment link goes into target's refs.experiments.
    return kind


def _append_backref(target: Path, *, kind: str, new_slug: str) -> bool:
    doc = fm.load(target)
    if not doc.has_frontmatter:
        return False
    refs = doc.frontmatter.setdefault("refs", {
        "code": [], "papers": [], "concepts": [], "experiments": [],
    })
    if not isinstance(refs, dict):
        return False
    bucket = refs.setdefault(kind, [])
    if not isinstance(bucket, list):
        return False
    if new_slug in bucket:
        return False  # idempotent
    bucket.append(new_slug)

    new_yaml = yaml.safe_dump(
        doc.frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False,
    )
    body = doc.raw_text[doc.body_offset:]
    target.write_text(f"---\n{new_yaml}---\n{body}", encoding="utf-8")
    return True


# ---------------------------------------------------------------------
# Internals — concept stub
# ---------------------------------------------------------------------


def _create_concept_stub(
    repo_root: Path, *,
    spec: StubSpec,
    today: date,
    session_id: str,
    from_entry: str,
) -> Path | None:
    target = repo_root / "wiki" / "concepts" / f"{spec.slug}.md"
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    fm_data = {
        "schema_version": 1,
        "type": "concept",
        "created": today.isoformat(),
        "updated": today.isoformat(),
        "tags": [],
        "refs": {"code": [], "papers": [], "concepts": [], "experiments": []},
        "authored_by": "hybrid",
        "source_sessions": [session_id],
        "seeded_by": "wiki-log",
        "seed_context": {
            "from_entry": from_entry,
            "from_phrase": spec.from_phrase,
        },
    }
    yaml_text = yaml.safe_dump(
        fm_data, sort_keys=False, allow_unicode=True, default_flow_style=False,
    )
    body = "*Stub created by wiki-log. Add interpretation here.*\n"
    target.write_text(f"---\n{yaml_text}---\n\n{body}", encoding="utf-8")
    return target


# ---------------------------------------------------------------------
# Internals — questions.md
# ---------------------------------------------------------------------


def _append_questions(
    questions_md: Path, *, entries: list[QuestionSpec],
    source_entry: str, when: datetime,
) -> int:
    if not entries:
        return 0
    questions_md.parent.mkdir(parents=True, exist_ok=True)
    timestamp = when.strftime("%Y-%m-%d %H:%M")
    blocks: list[str] = []
    for q in entries:
        blocks.append(
            f"\n## [{timestamp}] from wiki-log ({source_entry})\n"
            f"\n**Question:** {q.question}\n"
            f"\n**Context:** {q.context}\n"
            f"\n**Status:** open\n"
        )
    if questions_md.exists():
        existing = questions_md.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        questions_md.write_text(existing + "\n".join(blocks), encoding="utf-8")
    else:
        questions_md.write_text(
            "# wiki/questions.md\n\nOpen questions (LLM-appended; researcher resolves).\n"
            + "\n".join(blocks),
            encoding="utf-8",
        )
    return len(entries)


# ---------------------------------------------------------------------
# Internals — misc helpers
# ---------------------------------------------------------------------


def _entry_timestamp(path: Path) -> datetime | None:
    """Prefer the `created:` frontmatter field; fall back to file mtime."""
    try:
        doc = fm.load(path)
    except (OSError, UnicodeDecodeError):
        return None
    created = doc.frontmatter.get("created") if doc.has_frontmatter else None
    if created:
        try:
            if isinstance(created, datetime):
                return created
            if isinstance(created, date):
                return datetime.combine(created, datetime.min.time())
            if isinstance(created, str):
                return datetime.fromisoformat(created)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


def _read_body(path: Path) -> str:
    try:
        doc = fm.load(path)
    except (OSError, UnicodeDecodeError):
        return ""
    return doc.raw_text[doc.body_offset:] if doc.has_frontmatter else doc.raw_text
