# Release procedure

> Internal — for the project author. End users do not need this file.

## Versioning

Single source of truth: `[project] version` in `pyproject.toml`.
Mirror that to `version` in:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (top-level `version` and the entry's `version`)

The three should always agree. (Future: a small `tools/sync-versions.py` could
enforce this — for now, manual.)

Use semver: `MAJOR.MINOR.PATCH`. Pre-1.0 the API may change between minor versions.

## PyPI publish (first time)

Prerequisites:

- A PyPI account (https://pypi.org/account/register/) and an API token
  with scope `Project: researchwiki` (after the first publish reserves
  the name; the very first upload uses a user-scoped token).
- `pip install --upgrade build twine` (already in `[project.optional-dependencies] dev`).
- A resolved `LICENSE` file. `pyproject.toml` currently has
  `license = { text = "TBD" }` — PyPI accepts this but releases without
  a real license signal "all rights reserved" which discourages adoption.
  Pick a license (MIT / Apache-2.0 / BSD-3-Clause are common defaults
  for tooling) and update both `pyproject.toml` and a top-level `LICENSE`
  file before release.

Build and upload:

```bash
# Clean prior builds
rm -rf dist/ build/

# Verify tests + bundle sync first
python -m pytest

# Build sdist + wheel
python -m build

# Inspect what's in the wheel (sanity)
python -m zipfile -l dist/researchwiki-*.whl | head -30

# (Recommended) upload to TestPyPI first
python -m twine upload --repository testpypi dist/*

# Smoke-test the TestPyPI install in a fresh venv
python -m venv /tmp/rw-test && /tmp/rw-test/bin/pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    researchwiki
/tmp/rw-test/bin/wiki --help

# Publish to real PyPI
python -m twine upload dist/*
```

After upload, verify:

```bash
pip install researchwiki    # in any clean venv
wiki --help
```

## Subsequent releases

1. Bump `version` in `pyproject.toml`, `.claude-plugin/plugin.json`,
   `.claude-plugin/marketplace.json` (×2).
2. Update `## Decisions log` in `ARCHITECTURE.md` with the change rationale.
3. `python -m pytest` — must be green.
4. `python -m build`.
5. `git tag v0.1.1 && git push origin v0.1.1`.
6. `python -m twine upload dist/*`.

## Bundle synchronization

`src/researchwiki/_bundle/` is a byte-identical copy of
`skills/wiki-init/reference/bundle/`. Any change to the canonical
location must be propagated; `tests/test_bundle_sync.py` enforces
this.

To re-sync after editing the canonical bundle:

```bash
rm -rf src/researchwiki/_bundle
cp -r skills/wiki-init/reference/bundle src/researchwiki/_bundle
python -m pytest tests/test_bundle_sync.py
```

## Marketplace updates

Updating the published `marketplace.json` doesn't require a PyPI
release — just a git push. Claude Code re-reads marketplaces on
restart and picks up the changes.

If the plugin's slash-command surface changes (new skill, removed
skill, new SKILL.md frontmatter), bump both the plugin's `version`
in `plugin.json` and the marketplace's `version` so users can see
that an update is available.
