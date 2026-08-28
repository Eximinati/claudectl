---
description: >-
  Everything claudectl does, one card per area — sessions, project memory, the architecture
  graph, Plan to Execute, multiple accounts, MCP servers, agents, hooks, the status line and
  the desktop GUI.
---

# Features

Everything claudectl does, grouped. Each card is a page.

<div class="grid cards" markdown>

- **[Sessions & search](sessions.md)**

    Browse, search, tag, fork, resume, archive and export every session across every project
    — plus usage analytics and per-project launch control.

- **[Project memory](memory.md)**

    A semantic graph of your codebase, injected through three token-budgeted surfaces,
    bounded as the project grows, learning durable lessons from every session.

- **[Architecture graph](graph.md)**

    An interactive, self-contained HTML view of your project's real dependency structure,
    expandable from repo down to single files.

- **[Plan → Execute & OmniRoute](plan-execute.md)**

    Plan on an accurate model, execute on a cheap — or completely free — one, from the
    launcher.

- **[Multiple accounts](accounts.md)**

    Two or more Claude accounts side by side, one row per project, cross-account context
    injection and account-accurate memory.

- **[Context hand-off](context-handoff.md)**

    Start a fresh session seeded with a previous one's transcript — under any account. For
    when the context window fills up, or an account hits its limit mid-task.

- **[MCP servers](mcp.md)**

    Add, remove and inspect MCP servers, see which ones are actually connected, and document
    their tools.

- **[Agents & skills](agents.md)**

    A category-organized agent library, per-project subagent selection, adaptive
    suggestions, and the skills manager.

- **[Hooks](hooks.md)**

    19 ready-made Claude Code hook templates — formatting, safety guardrails, audit, context
    injection, token savers — plus AI-generated ones.

- **[Status line, failover & checkpoints](statusline.md)**

    A cheap per-turn status line, a proxy that retries a dead model instead of hanging, and a
    read-only view of Claude Code's checkpoint store.

- **[Desktop GUI](gui.md)**

    The whole thing as a native desktop app — full parity with the terminal UI, 29 palettes,
    7 skins and 4 themed worlds.

</div>

## Guides

- [Token economy](token-economy.md) — how the per-turn context cost is measured and cut
- [Project health & auto-fixes](health.md) — launcher-side mitigations for common Claude Code problems
- [Installing the agent library](agent-library.md) — bulk-install 154 community subagents

## Reference

- [Files, layout & encoding](reference.md) — where everything is stored
- [API reference](api.md) — the local HTTP API the GUI is built on
