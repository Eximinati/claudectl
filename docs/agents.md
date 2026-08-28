---
description: >-
  The agent library, per-project subagent selection, adaptive suggestions, AI-generated
  agents, and the skills manager — everything claudectl does with Claude Code subagents and
  SKILL.md files.
---

# Agents & skills

## Agents (subagents)

- **Agent library** — a category-organized store at `~/.claude/claudectl-agents/<category>/` (not auto-loaded by Claude, so sessions stay lean). Roll your own or bulk-install the [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) catalog (154 agents across 10 categories) — see [Installing the agent library](agent-library.md).
- **Per-project selection** (`g` in the sessions menu) — pick agents from a category checklist (optional, default none). The chosen agents are **copied into `<project>/.claude/agents/`** where Claude auto-discovers them, so they apply to every launch of that project and the selection auto-restores next time. claudectl only manages the files it placed (tracked in `.claudectl-managed.json`) — your own project agents are never touched.
- **Scaffold** — create an agent into a chosen or new category: pick tools (multi-select) and model, edit the body
- **AI-generated** — Claude analyzes the project and authors a focused subagent (role, when-to-use, tool subset, system prompt); you review before it's written
- **Lead agent** — also set a single `--agent` (from `~/.claude/agents/`) in launch options
- **Why copy, not `--agents`** — inline `--agents` JSON rides the command line (Windows ~32KB cap); a handful of real, multi-KB agents overruns it (`WinError 206`). Copying into `.claude/agents/` has no size limit and matches how Claude Code natively loads project subagents.

## Adaptive agent selection (`g`)

The agents screen opens with a **"Suggested for this project"** section — library agents
ranked against the project's languages (from the [dependency graph](graph.md)), memory
entities, and name. Local scoring, instant, free. Setting `agents_auto: 'auto'` applies
suggestions automatically on first open (your manual picks are never touched).

## Skills

**Skills manager** — browse, install, scaffold, and AI-generate Claude Code **skills**
(`.claude/skills/<name>/SKILL.md`) that load on demand instead of bloating `CLAUDE.md`.
Ships with cited starter templates (see [Credits](credits.md)). TUI: **⚙ Skills**; GUI: the
**Skills** tab.

Third-party skill and agent bundles are statically risk-scanned before install.
