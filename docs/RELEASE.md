# Release procedure

> Internal — for the project author. End users do not need this file.

## Distribution model

This project distributes **via Git only.** End users install through
the plugin's `bin/wiki` bootstrap wrapper, which runs:

```
pip install git+https://github.com/apple4ree/researchwiki.git
```

There is no PyPI publication step. That decision deliberately
trades the slightly nicer `pip install researchwiki` UX for:

- No license decision pressure (PyPI implicitly recommends one).
- No PyPI account / token / name reservation.
- No version-bump / publish workflow — every push to `main` is
  effectively the latest "release."
- No build / wheel / twine gymnastics in CI.

The `bin/wiki` bootstrap masks the verbosity of the git URL — users
see only `/plugin install researchwiki@researchwiki-plugins`, and
the install happens once on first slash-command invocation.

## "Release" = `git push origin main`

For non-trivial changes worth signaling to users, also tag:

```bash
git tag v0.1.1
git push origin v0.1.1
```

The tag has no semantic effect on the bootstrap (it pulls `main`),
but it gives users a stable reference point and makes
`git log --tags --oneline` useful.

If a user wants to pin to a specific commit / tag, they can override
the bootstrap by setting `WIKI_NO_BOOTSTRAP=1` and installing manually:

```bash
pip install git+https://github.com/apple4ree/researchwiki.git@v0.1.1
```

## Forcing users to upgrade

The bootstrap installs once and then short-circuits via the import
check. To pull the latest commit, users set `WIKI_UPGRADE=1` for one
invocation:

```bash
WIKI_UPGRADE=1 wiki --help
```

This re-runs `pip install --upgrade git+https://...` and writes a
single line to stderr noting the upgrade. There's no auto-upgrade —
users opt in.

## Versioning

Single source of truth: `[project] version` in `pyproject.toml`.
Mirror that to:

- `.claude-plugin/plugin.json` `version`
- `.claude-plugin/marketplace.json` top-level `version`
- `.claude-plugin/marketplace.json` `plugins[].version`

Use semver: `MAJOR.MINOR.PATCH`. Pre-1.0 the API may change between
minor versions. The version influences nothing operationally (no PyPI
publish), but it's what `wiki --version` would report (TODO: implement)
and what users compare in changelogs.

## Bundle synchronization

`src/researchwiki/_bundle/` is a byte-identical copy of
`skills/wiki-init/reference/bundle/`. Any change to the canonical
location must be propagated; `tests/test_bundle_sync.py` enforces
this on every test run.

To re-sync after editing the canonical bundle:

```bash
rm -rf src/researchwiki/_bundle
cp -r skills/wiki-init/reference/bundle src/researchwiki/_bundle
python -m pytest tests/test_bundle_sync.py
```

## Marketplace updates

Updating the published `marketplace.json` doesn't require any release
ceremony — just `git push`. Claude Code re-reads marketplaces on
restart and picks up the changes.

If the plugin's slash-command surface changes (new skill, removed
skill, new SKILL.md frontmatter), bump `version` in both
`plugin.json` and `marketplace.json` so users running
`/plugin marketplace list` see that an update is available.

## (Optional) Future PyPI publication

Should we later decide to publish to PyPI, the steps are:

1. Resolve `license` in `pyproject.toml` (currently `text = "TBD"`).
2. Add a top-level `LICENSE` file.
3. `python -m build`.
4. `python -m twine upload --repository testpypi dist/*` (verify on TestPyPI first).
5. `python -m twine upload dist/*` (real PyPI).
6. Update `bin/wiki` to try PyPI first, GitHub source as fallback.
7. Update README / docs to advertise `pip install researchwiki`.

Until then, GitHub is the canonical distribution.
