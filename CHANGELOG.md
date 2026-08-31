# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Hide projects you never want to see.** Every folder Claude Code has ever run in shows
  up in the project list, including one-off experiments and folders that no longer exist
  as work. A project can now be hidden from the TUI project menu and the GUI sidebar —
  from `Hide / restore projects` in the main menu, or the `Hide` button on a project page.
  It is a view flag (`project_defaults[<enc>].hidden`), so nothing on disk moves: the
  sessions stay resumable and restoring costs one click. The TUI says how many rows are
  filtered; the GUI grows a `Show N hidden projects` button while any are.
- `claudectl --help` (and `-h`, `help`, `--version`). A pip install used to answer the
  most obvious command by opening the full-screen terminal UI. The help text covers every
  subcommand, what the tool does and where its state lives, and a test enumerates the
  dispatch table so it cannot fall behind it.

### Fixed

- `load_settings()` copied the defaults shallowly, so every load of a settings file that
  named no `project_defaults` handed back the same dict — and each writer of one mutates
  it in place. In a long-lived process (the GUI, a long TUI run) one project's pins leaked
  into the next load.

## [1.7.0] - 2026-08-28

### Added

- **What you provision now reaches every account, not just the default one.** Hooks,
  plugins, marketplaces, user agents and the global `CLAUDE.md` were all written into
  whichever config directory happened to be active when the module was imported — in
  practice the default account. Measured across five configured logins, the default had
  18 hooks, 3 marketplaces, 3 plugins and a global `CLAUDE.md`; the other four had none of
  it. The status line was the only feature that ever reached all of them, because it was
  the only one with a real fan-out; that fan-out is now the rule rather than the exception.
- `claudectl sync-accounts` levels every account up to the union of them all, on the
  command line, on the GUI's Accounts page and in the TUI accounts menu. It shows the
  per-account diff **before** writing anything, only ever adds (an account keeps whatever
  the others lack, because nothing can tell a deliberate choice from a gap), routes every
  plugin install through the same review gate a single-account install uses, and reports
  nothing to do when re-run.
- The Plugins page says which accounts have each plugin and marketplace, and offers to
  install one into the accounts that do not. Adding a marketplace registers it everywhere;
  removing acts only on the account on screen.
- **Nineteen functions that existed only in the terminal UI now have a surface in the
  GUI**: the editor / `claude.exe` / config-dir paths and the headless budget cap; disabled
  hooks, an enable/disable control and an *Edit settings.json* button; the per-prompt
  recall hook, path-scoped rules and the recall budget, which the GUI had been printing
  read-only; the global `CLAUDE.md` viewer and editor; `claude mcp get` detail and MCP tool
  docs, which the analyze job used to write into a file the GUI could not open; env vars
  and headers when adding an MCP server; the one-key project setup the terminal offers as
  `!`; the architecture stats card, which revives an endpoint that had no consumer at all;
  tools and model when creating an agent; copying a skill into your library; and a Help
  page generated from the navigation and the terminal's own key table instead of retyped.
- Cross-project conventions, `loop.md` at both project and account scope, Claude Code's own
  per-project record and output-style previews — four endpoints that had no control in
  either surface — are reachable.

### Fixed

- `claude plugin …` and `claude mcp …` ran with no environment, so they acted on whatever
  account the process inherited while every reader resolved the configured one: with
  claudectl switched to another account, the Plugins page listed that account's plugins and
  *Install* wrote into the default. Both now name an account explicitly.
- `mcp.update_global_claude_md_mcp` and the conventions sync wrote a file Claude Code reads
  every session with a plain `open(..., 'w')`. A write that dies partway broke the whole
  session, not just claudectl. Both are atomic now.
- A hook disabled in the terminal vanished from the GUI, which then offered its template as
  uninstalled and created an enabled duplicate beside the disabled one.
- The job list on the dashboard raised as soon as any job had said anything: every producer
  appends a `{ok, text}` record and the reader indexed it as a string.
- The per-project recall toggle promised a hook that only one account had installed.

### Changed

- The GUI's accepted-settings list is derived from the settings registry minus an explicit
  internal set, rather than being a sixth hand-maintained copy that had already fallen
  behind it; the terminal's settings rows are named after the settings they write, so the
  two screens can be compared by a test instead of by hand.
- New parity gates, each watched failing under mutation: every route the SPA never calls
  must carry a written reason, a POST route must be reached with `post(`, a value rendered
  as on/off must be one the page can send back, the main menu's rows must name a GUI
  counterpart, and the account fan-out helper must have callers. The browser smoke tool
  walks the page and tab lists derived from the app instead of a hardcoded subset, and its
  floor rose from 40 checks to 85.

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
