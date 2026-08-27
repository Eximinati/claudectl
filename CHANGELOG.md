# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

No release has been tagged yet, and the package is not on PyPI. Everything below is the
work leading to the first tagged release; `pyproject.toml` currently reads `1.6.0`.

## [Unreleased]

### Fixed

- The launch picker's effort slider pointed at the wrong label. `EFFORTS` had grown a
  seventh entry (`ultracode`) but the tick row was six labels typed into the markup, so
  the thumb at *xhigh* — 4/6 of the track — sat under HIGH, and `ultracode` was a stop
  with no label at all. The row is generated from the same list that sizes the slider,
  and each label is placed on its own stop rather than spread with `space-between`, which
  aligns label boxes and drifts every centre off its tick. `tools/shot_gui.py` now
  measures thumb-against-label for every stop.

### Added

- The sessions screen's 29 keys are described in one place instead of three. The action
  table, the `/` palette and the help screen had drifted apart — the palette was missing
  code review (`R`) and the help screen was missing `R`, plan→execute (`X`) and context
  injection (`K`), so code review had no discoverable entry point anywhere in the product.
  Both discovery surfaces are now generated from the table, and a test walks the key
  handlers in the source and fails when one of them has no row.
- The launch picker reads the model list from Anthropic instead of a hand-edited table, so
  a model released this week is selectable without a claudectl release. It uses the login
  Claude Code already holds — no API key — and refreshes once a day on a background thread.
  Facts (context window, supported efforts, release date) come from the API; cost rank,
  capability rank and the "best for" prose stay curated and are inherited by family, so a
  new generation appears with sensible columns rather than blanks. Every failure — no
  network, logged out, `auto_update: off` — falls back to the list shipped with this
  version, never to an empty picker, and a model you have pinned that Anthropic has retired
  keeps its place in the picker with a warning instead of being silently reset to *default*.
- claudectl reports its own version against PyPI and can update itself. A banner says when a
  newer release exists, the Updates screen and the Plugins page offer the upgrade, and
  `Settings → Updates` chooses between being told, installing on quit, and never checking.
  The upgrade runs in its own window after claudectl exits, because pip cannot rewrite the
  console script of the process running from it — and a git checkout is told to `git pull`
  rather than having a release installed over the top of it.
- Claude Code plugin distribution — `claudectl` installs as a plugin, with its bundled
  skills generated from the packaged templates and validated in CI.
- Multi-repo worktrees board and repo discovery, including submodule and linked-worktree
  classification read from the `gitdir:` pointer rather than a subprocess.
- Model failover proxy with TUI and GUI settings, so a dead model is retried instead of
  hanging the session.
- Desktop GUI overhaul: dashboard home, always-on account usage, a single 3D background
  stage, chassis skins and worlds, and an instrument dashboard.
- OmniRoute-aware dashboard and usage views, including free-tier session tagging.
- Resumable saved plans in Plan → Execute.
- Status line, installable per account.
- macOS and Linux support alongside Windows.

### Changed

- TUI/GUI parity is enforced as a CI gate rather than reviewed by hand; the API reference
  in `docs/api.md` is generated from the live route tables and checked for staleness.
- Per-turn work moved off the hot path — the status line dispatches before the TUI is
  imported, and hooks no longer re-stream whole transcripts on every turn.
- Duplicated primitives consolidated into single implementations for transcript reading,
  process control, JSON storage and session paths.
- Default models updated to Opus 5.
- README rewritten around real screenshots.

### Fixed

- Status line resolves the active account and project rather than the checkout it was
  installed from, and reports why an installed status line is not showing.
- Account-scoped settings writes no longer bind the config directory at import time, so
  every account is written correctly.
- Both local HTTP servers authenticate requests, with a host allowlist, browser
  fetch-metadata rejection and a per-run secret.
- State writes are atomic, and a file that exists but will not parse is quarantined
  instead of silently erased.
- Malformed requests return 400 instead of 500, and `cfgdir` is validated against known
  accounts.
- Session paths are resolved from the transcript's recorded `cwd` rather than decoded from
  the encoded folder name, which had dropped UNC-path projects entirely.
- Packaging: the skills templates glob now matches, so the wheel ships them; a CI job
  installs the built wheel and reads the data files back out of site-packages.
