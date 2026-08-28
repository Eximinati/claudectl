---
description: >-
  claudectl's task-scoped, token-budgeted project memory — a semantic graph of your codebase
  injected through three surfaces, bounded as the project grows, and learning durable
  lessons from every session.
---

# Project memory

The feature that makes claudectl unique: **task-scoped, token-budgeted memory injection at
the launcher**. Claude remembers the whole project while paying the fewest possible tokens
— three injection surfaces, zero duplication.

Reached with `m` in the sessions menu (the memory hub), or the **Memory** project tab in
the GUI.

## The three surfaces

| Surface | What Claude sees | Cost |
|---|---|---|
| CLAUDE.md micro-index | repo one-liners + module names + recall pointer | ≤250 tok, every session |
| `.claude/rules/claudectl-mem-*.md` | per-module entities & relations, `globs:`-scoped | **0 until Claude touches those files** |
| `UserPromptSubmit` hook (opt-in) | the subgraph relevant to *your current prompt*, budget-cut | ≤600 tok/prompt, <1s local |

## How it works

- **Whole-project extraction** — `claude.exe` summarizes every repo and module (incrementally by file hash), merged with the **real dependency graph** (cross-module edges + importance rank) from the [connections engine](graph.md). Stored in `.claudectl/memory/graph.json`.
- **Bounded & self-consolidating** — the graph stays lean *as the project grows*: duplicate entities merge across modules, and a global importance cap (`memory_max_entities`, default 500) evicts the least-connected. So the always-on token cost stays flat while accuracy rises — the memory gets *leaner and sharper* the more you build, not heavier.
- **Temporal facts (Graphiti-style)** — when the code changes and a fact is superseded (you migrated Flask→FastAPI), the old fact is **invalidated with a timestamp, not deleted** — kept as history, never injected. Memory tracks *what's true now* and *what changed*, instead of drifting stale.
- **Reinforcement + rollups** — entities recalled often gain weight and survive consolidation; dead knowledge fades (access-based, like a forgetting curve). Per-repo **rollup summaries** (GraphRAG-style, built locally — no extra Claude call) give an accurate one-line repo overview and cheap global answers. Plus Obsidian-style **unlinked-mention** edges enrich retrieval for free.
- **Recall engine** — local scoring (IDF keyword + path match + dependency rank + graph expansion), no embeddings, deterministic, <0.5s on 500 entities. On-demand CLI: `claudectl recall "<topic>"` — Claude itself can call it mid-session via Bash.
- **Session learning** — after each session claudectl distills durable *lessons* (error→fix pairs, decisions, preferences) from the transcript. High-confidence lessons **auto-approve** (`memory_lessons_autoapprove`); the rest wait in the `⇧L` review screen. Approved lessons boost recall and decay if unused. The project literally gets smarter the more you use it.
- **Cross-project conventions** — preferences/corrections that recur across your repos (or you pin) are promoted to a small block in your user-level `~/.claude/CLAUDE.md`, so a convention learned once ("this machine uses PowerShell 5.1", "prefer pytest") is remembered in *every* project. No competitor spans projects.
- **Auto-refresh** — memory refreshes incrementally on project open (`memory_auto_refresh`, capped so a big rebuild never runs silently). Zero user action. The update runs in a **detached background worker** that survives launching a session, saves after every step (an interruption never loses progress), and shows live progress in the sessions menu — so you can open a chat immediately instead of waiting for the scan to finish.
- **Memory hub** (`m` in the sessions menu) — one screen for everything: status, build, ask, injection preview with live "what would my prompt inject?" probe, lessons, **work suggestions** (`s` — next-steps from lessons + graph + health, local), **since-last-session diff** (`d` — git + session-log), per-surface toggles.
- **Ask the project** — grounded Q&A over the graph, answered by Claude with only the relevant subgraph as context.

*(Graph memory inspired by [cognee](https://github.com/topoteretes/cognee); retrieval
budgeting inspired by [Aider's repo-map](https://aider.chat/docs/repomap.html); both
reimplemented from scratch — pure stdlib.)*

## CLAUDE.md and system prompts

- **Scaffold CLAUDE.md** (`c`) — build project context mechanically from git repos, recent commits, READMEs, and prior session topics
- **AI CLAUDE.md generation** (`a`) — Claude deep-analyzes the codebase and writes/updates a comprehensive CLAUDE.md; reviewed before writing
- **System prompts** (`s`) — AI-generate or hand-edit a per-project system prompt injected on every launch
- **Memory map** (`M`) — see which CLAUDE.md files load for a project (user / project / .claude / local) and their `@import`s; open any in your editor

Exactly what each generator reads and which blocks it rewrites is in
[CLAUDE.md auto-generation](reference.md#claudemd-auto-generation).

## Recent-work memory

Opt-in per project (Memory tab / `⇧W` in the hub). Records a token-free one-line summary +
files touched at the end of each session and injects a compact digest on the next
`SessionStart`, so Claude knows what the last few sessions did.

## Keeping it honest

Everything memory generates is tracked for provenance and freshness — see
[Workspace status](reference.md#workspace-status). Where the token budget goes, and how to
cut it further, is on the [Token economy](token-economy.md) page.
