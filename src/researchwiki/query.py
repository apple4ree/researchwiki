"""wiki-query — BM25 lexical search over wiki contents.

Read-only. Returns ranked page paths with extractive snippets to stdout.
Pages with unresolved `stale: true` flags are prefixed with a `⚠ stale`
badge. Meta pages are skipped by default.

Tokenizer: whitespace + identifier split (snake_case / camelCase /
kebab-case / dots / slashes), with the original chunk also kept as a
token to support exact-path queries (e.g., `src/trainer.py`). Korean
text is preserved as whitespace-separated tokens; ko-morphology is
deferred to v1.x.

Stdlib only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from researchwiki.lint.runner import _split_frontmatter

# BM25 tuning params (standard defaults).
BM25_K1 = 1.5
BM25_B = 0.75

DEFAULT_TOP = 10
DEFAULT_SNIPPET_CONTEXT_LINES = 2

META_PAGE_NAMES = frozenset({"index.md", "log.md", "questions.md", "discrepancies.md"})

# Identifier-shape boundaries: split on these AND on camelCase transitions.
_BOUNDARY_RE = re.compile(r"[\s/._\-]+")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


# ---------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Tokenize for BM25 indexing/querying.

    Returns lowercased tokens. For each whitespace-separated chunk:
    - The chunk itself (e.g., `src/trainer.py`) is kept as a token, so
      the researcher can search for exact paths.
    - The chunk is also split on identifier delimiters and camelCase
      boundaries (e.g., `RotaryEmbedding` → `rotary`, `embedding`).
    Non-alphanumeric leading/trailing characters are stripped from each
    sub-token.
    """
    out: list[str] = []
    for chunk in text.split():
        chunk = chunk.strip().strip(".,;:?!()[]{}\"'、。")
        if not chunk:
            continue
        lowered = chunk.lower()
        out.append(lowered)
        # Split on identifier delimiters.
        for piece in _BOUNDARY_RE.split(chunk):
            if not piece:
                continue
            # Camel-case split.
            for sub in _CAMEL_RE.split(piece):
                sub_clean = sub.strip().strip(".,;:?!()[]{}\"'").lower()
                if sub_clean and sub_clean != lowered:
                    out.append(sub_clean)
    return out


# ---------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------


@dataclass
class Doc:
    path: str           # repo-relative POSIX path
    raw_text: str       # full file content (for snippet extraction)
    body: str           # body only (what the researcher reads)
    frontmatter: dict
    tokens: list[str] = field(default_factory=list)
    token_freq: dict[str, int] = field(default_factory=dict)
    length: int = 0


@dataclass
class BM25Index:
    docs: list[Doc]
    df: dict[str, int]    # term → number of docs containing it
    avgdl: float
    n_docs: int

    def idf(self, term: str) -> float:
        n = self.n_docs
        df = self.df.get(term, 0)
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)


def build_index(docs: list[Doc]) -> BM25Index:
    df: dict[str, int] = {}
    total_len = 0
    for doc in docs:
        for term in set(doc.token_freq):
            df[term] = df.get(term, 0) + 1
        total_len += doc.length
    avgdl = (total_len / len(docs)) if docs else 0.0
    return BM25Index(docs=docs, df=df, avgdl=avgdl, n_docs=len(docs))


def score_doc(query_terms: list[str], doc: Doc, index: BM25Index) -> float:
    score = 0.0
    for term in query_terms:
        tf = doc.token_freq.get(term, 0)
        if tf == 0:
            continue
        idf = index.idf(term)
        denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * doc.length / index.avgdl)
        if denom == 0:
            continue
        score += idf * (tf * (BM25_K1 + 1)) / denom
    return score


# ---------------------------------------------------------------------
# Page loading
# ---------------------------------------------------------------------


def load_pages(
    wiki_dir: Path,
    repo_root: Path,
    *,
    scope: str = "all",
    include_meta: bool = False,
    frontmatter_only: bool = False,
) -> list[Doc]:
    """Walk wiki/, return Doc list with tokens precomputed.

    Pages are filtered:
    - Meta pages excluded unless `include_meta=True`.
    - `scope` ∈ {"all", "concepts", "papers", "experiments", "decisions"}.
    """
    docs: list[Doc] = []
    scope_dirs = {
        "all": None,  # no filter
        "concepts": "concepts",
        "papers": "papers",
        "experiments": "experiments",
        "decisions": "decisions",
    }
    if scope not in scope_dirs:
        raise ValueError(f"unknown scope: {scope!r} (valid: {sorted(scope_dirs)})")
    subdir_filter = scope_dirs[scope]

    for md in sorted(wiki_dir.rglob("*.md")):
        rel = md.resolve().relative_to(repo_root.resolve()).as_posix()
        # Meta-page filter.
        if not include_meta and _is_meta_page(rel, "wiki/"):
            continue
        if subdir_filter and not rel.startswith(f"wiki/{subdir_filter}/"):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm, body, _err = _split_frontmatter(text)
        # The corpus is frontmatter + body unless --frontmatter-only.
        # Rendering frontmatter as text: use yaml dump to get a uniform shape.
        import yaml as _yaml
        fm_text = _yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) if fm else ""
        corpus = fm_text if frontmatter_only else (fm_text + "\n" + body)
        tokens = tokenize(corpus)
        freq: dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        docs.append(Doc(
            path=rel,
            raw_text=text,
            body=body,
            frontmatter=fm,
            tokens=tokens,
            token_freq=freq,
            length=len(tokens),
        ))
    return docs


def _is_meta_page(path: str, wiki_root: str) -> bool:
    wiki_root = wiki_root.rstrip("/") + "/"
    if not path.startswith(wiki_root):
        return False
    rest = path[len(wiki_root):]
    if "/" in rest:
        return False
    return rest in META_PAGE_NAMES


# ---------------------------------------------------------------------
# Stale badge
# ---------------------------------------------------------------------


def stale_badge(frontmatter: dict, today: date | None = None) -> str | None:
    """Return a `⚠ stale: N refs unaddressed for Md` string, or None
    if the page has no unresolved stale refs."""
    refs = frontmatter.get("refs")
    if not isinstance(refs, dict):
        return None
    code = refs.get("code")
    if not isinstance(code, list):
        return None
    today = today or datetime.now().date()
    stale_count = 0
    oldest_age_days: int | None = None
    for r in code:
        if not isinstance(r, dict):
            continue
        if not r.get("stale"):
            continue
        stale_count += 1
        detected = r.get("stale_detected")
        if detected is None:
            continue
        try:
            d = _coerce_date(detected)
            age = (today - d).days
            if oldest_age_days is None or age > oldest_age_days:
                oldest_age_days = age
        except ValueError:
            continue
    if stale_count == 0:
        return None
    if oldest_age_days is None:
        return f"⚠ stale: {stale_count} ref(s) unaddressed"
    return f"⚠ stale: {stale_count} ref(s) unaddressed for {oldest_age_days}d"


def _coerce_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"unrecognized date value: {value!r}")


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------


@dataclass
class QueryResult:
    rank: int
    score: float
    path: str
    snippet: str
    badge: str | None  # stale badge if any


def search(
    query: str,
    docs: list[Doc],
    *,
    top: int = DEFAULT_TOP,
    snippet_context_lines: int = DEFAULT_SNIPPET_CONTEXT_LINES,
    stale_warnings: bool = True,
    today: date | None = None,
) -> list[QueryResult]:
    if not query.strip():
        raise ValueError("query is empty")
    query_terms = tokenize(query)
    if not query_terms:
        return []
    index = build_index(docs)

    scored: list[tuple[float, Doc]] = []
    for doc in docs:
        s = score_doc(query_terms, doc, index)
        if s > 0:
            scored.append((s, doc))
    scored.sort(key=lambda x: (-x[0], x[1].path))

    out: list[QueryResult] = []
    for i, (score, doc) in enumerate(scored[:top], start=1):
        snippet = _extract_snippet(doc.body, query_terms, snippet_context_lines)
        badge = stale_badge(doc.frontmatter, today=today) if stale_warnings else None
        out.append(QueryResult(
            rank=i,
            score=round(score, 2),
            path=doc.path,
            snippet=snippet,
            badge=badge,
        ))
    return out


def _extract_snippet(body: str, query_terms: list[str], context_lines: int) -> str:
    """Find the first body line containing any query term and return
    ±context_lines around it. Verbatim spans only — never paraphrased.
    """
    lines = body.splitlines()
    if not lines:
        return ""
    lower_lines = [l.lower() for l in lines]
    query_set = set(query_terms)

    best_line: int | None = None
    for i, ll in enumerate(lower_lines):
        # Cheap match: any token from any line equals any query term.
        line_tokens = set(tokenize(ll))
        if line_tokens & query_set:
            best_line = i
            break

    if best_line is None:
        return ""

    start = max(0, best_line - context_lines)
    end = min(len(lines), best_line + context_lines + 1)
    span = lines[start:end]
    snippet = "\n   ".join(s for s in span if s.strip())
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(lines) else ""
    return f"{prefix}around line {best_line + 1}:\n   {snippet}\n   {suffix}".rstrip()


# ---------------------------------------------------------------------
# Stdout formatting
# ---------------------------------------------------------------------


def format_results(results: list[QueryResult]) -> str:
    if not results:
        return "0 results.\n"
    lines: list[str] = []
    for r in results:
        badge_part = f" [{r.badge}]" if r.badge else ""
        prefix = "⚠ " if r.badge else "  "
        lines.append(f"{r.rank}. {prefix}{r.path}{badge_part}    score {r.score:.1f}")
        if r.snippet:
            lines.append(f"   ...{r.snippet}\n")
    return "\n".join(lines) + "\n"
