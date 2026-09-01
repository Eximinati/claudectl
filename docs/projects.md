---
description: >-
  Per-project health checks and auto-fixes, plus workspace status — the provenance and
  freshness manifest that says whether the context claudectl generated still matches the
  repo it came from.
---

# Projects

A project in claudectl is a folder Claude Code has a session for, and it carries state of
its own: generated context, a memory graph, launch defaults, health. This page is the two
screens that report on that state — the health card, and workspace status.

Both are behind `w` in the sessions menu, and on the project page in the
[desktop app](desktop.md).

## Health & auto-fixes

Launcher-side mitigations for the most common Claude Code problems (2026 field research):

- **Pre-launch health card** — CLAUDE.md over-budget (loads every session!), missing `--add-dir`/PATH entries, non-UTF-8 CLAUDE.md, stale memory, MCP failures, session-window burn ≥70% (suggests cheaper model/effort for routine work).
- **Context-loss insurance** — after every session a 5-line summary (goal + files touched) is appended to `.claudectl/session-log.md`, so the next session can recall what happened even after `/compact` wiped the context. Local, free.
- **Permission fatigue killer** — `P` in the workspace screen scans your history for repeatedly-used Bash commands and proposes `permissions.allow` rules for the project settings.json (diff-previewed, you approve).

Over-budget warnings on the health card are the summary; the itemised breakdown is the
[context weight audit](usage.md#context-weight-audit-w).

## Workspace status

claudectl tracks the **provenance and freshness** of the context it generates. After
scaffold, AI-analyze, or launch, it writes `<project>/.claudectl/workspace-manifest.json`
(falling back to the encoded `~/.claude/projects/<encoded>/.claudectl/` folder if the working
dir is read-only). The manifest is schema-versioned and forward-compatible — old files load,
unknown keys survive round-trips.

It records where generated context came from: repo HEAD, source-file hashes
(CLAUDE.md/README/configs), sessions analyzed (count + range), CLAUDE.md files, MCP server
snapshots + tool counts, and last-run timestamps for scaffold / AI-analyze / launch. Updated
automatically after those operations (best-effort — never blocks them).

View it from inside a repo:

```
$ claudectl workspace status
  Workspace Status
  ────────────────
  Repo HEAD         5f39fcb  (main)
  Sessions analyzed 20
  MCP servers       3
  CLAUDE.md status  🟢 Fresh
  MCP docs status   🟢 Fresh
  Repo changed      No
  Safe to launch    Yes

  Workspace freshness score: 96%  ▕███████████████████░▏
```

…or press `w` in the sessions menu for the same view as a TUI screen (`r` refreshes, ESC
exits). Indicators: 🟢 Fresh · 🟡 Stale · 🔴 Invalid. A component goes **stale** when the
repo HEAD moved, README/source hashes changed, or new sessions accrued since the memory was
generated; **invalid** means a missing-after-generation CLAUDE.md or a corrupt manifest.
`safe_to_launch` is false only when an invalid check is present. The freshness score is the
weighted fraction of applicable checks that are fresh. Viewing status is **read-only** — it
never rewrites the manifest.

**Change diffs** — when AI-regenerating CLAUDE.md (`a`) or a system prompt (`s`), the
approval step shows a **git-style colored diff** (old → new) so you decide *before* writing
(`f` toggles to the full proposed text; ENTER approve, ESC reject). The previous version is
snapshotted under `.claudectl/snapshots/`, so the workspace screen (`w`) lists recent changes
with `+/−` counts and re-opens the last diff on `c` (CLAUDE.md) / `s` (system prompt).

## Hiding a project

**📦 Hide / restore projects** on the main screen takes a project out of the project list
and out of the desktop app's sidebar, for folders you never want to launch from again. It
is a view flag, not an archive: nothing on disk moves, the project's sessions stay
resumable, and restoring is one keypress. See [Terminal UI](tui.md#built-in-screens).

## See also

- [Configuration](configuration.md) — every per-project file, and where it lives
- [Files, layout & encoding](reference.md#claudemd-auto-generation) — how CLAUDE.md is
  generated
- [Project memory](memory.md) — what goes stale, and what rebuilds it
