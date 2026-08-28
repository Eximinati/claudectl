---
description: >-
  Launcher-side mitigations for the most common Claude Code problems — a pre-launch health
  card, context-loss insurance after /compact, and a permission-fatigue killer.
---

# Project health & auto-fixes

`w` in the sessions menu. Launcher-side mitigations for the most common Claude Code
problems (2026 field research):

- **Pre-launch health card** — CLAUDE.md over-budget (loads every session!), missing `--add-dir`/PATH entries, non-UTF-8 CLAUDE.md, stale memory, MCP failures, session-window burn ≥70% (suggests cheaper model/effort for routine work).
- **Context-loss insurance** — after every session a 5-line summary (goal + files touched) is appended to `.claudectl/session-log.md`, so the next session can recall what happened even after `/compact` wiped the context. Local, free.
- **Permission fatigue killer** — `P` in the workspace screen scans your history for repeatedly-used Bash commands and proposes `permissions.allow` rules for the project settings.json (diff-previewed, you approve).

The same screen shows [workspace provenance and freshness](reference.md#workspace-status):
whether the context claudectl generated still matches the repo it was generated from, and a
`safe_to_launch` flag.

Over-budget warnings on the health card are the summary; the itemised breakdown is the
[context weight audit](token-economy.md#context-weight-audit-w).
