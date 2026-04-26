"""Verifies the two bundle copies are byte-identical.

The canonical bundle lives under `skills/wiki-init/reference/bundle/`
(referenced by `wiki-init/SKILL.md` + the Claude Code plugin layout).
The packaged copy lives under `src/researchwiki/_bundle/` and ships
inside the wheel so `pip install researchwiki` finds it via
`_find_bundle()`'s packaged-fallback (init.py).

If they drift, downstream behavior diverges depending on whether the
user installed editably or via wheel — same skill, two different
results. That's a P3 risk: the wiki-init output should be byte-stable
across install methods. So we enforce exact byte equality here.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _walk_files(root: Path) -> list[Path]:
    """Sorted list of files (relative paths) under `root`."""
    return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())


def test_bundle_copies_have_same_file_set():
    repo = _repo_root()
    canonical = repo / "skills" / "wiki-init" / "reference" / "bundle"
    packaged = repo / "src" / "researchwiki" / "_bundle"

    assert canonical.is_dir(), f"canonical bundle missing: {canonical}"
    assert packaged.is_dir(), (
        f"packaged bundle missing: {packaged}. "
        "Re-sync via: cp -r skills/wiki-init/reference/bundle/* src/researchwiki/_bundle/"
    )

    canon_files = _walk_files(canonical)
    pkg_files = _walk_files(packaged)
    assert canon_files == pkg_files, (
        f"file sets differ between bundle copies.\n"
        f"  only in canonical: {set(canon_files) - set(pkg_files)}\n"
        f"  only in packaged:  {set(pkg_files) - set(canon_files)}"
    )


def test_bundle_copies_byte_identical():
    repo = _repo_root()
    canonical = repo / "skills" / "wiki-init" / "reference" / "bundle"
    packaged = repo / "src" / "researchwiki" / "_bundle"

    for rel in _walk_files(canonical):
        a = (canonical / rel).read_bytes()
        b = (packaged / rel).read_bytes()
        assert a == b, (
            f"bundle file diverges between canonical and packaged: {rel}\n"
            f"  canonical bytes: {len(a)}, packaged bytes: {len(b)}"
        )
