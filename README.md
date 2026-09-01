<h1 align="center">claudectl</h1>

<p align="center">
  <b>The workspace layer for Claude Code.</b><br>
  Your projects stop being a stream of chats and start being workspaces —
  with memory, history, and per-project launch control.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-0078D6">
  <img alt="Dependencies" src="https://img.shields.io/badge/runtime%20deps-zero%20(stdlib)-brightgreen">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1367-brightgreen">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Claude Code" src="https://img.shields.io/badge/for-Claude%20Code-8A5CF6">
</p>

<p align="center">
  <b>📖 Full documentation → <a href="https://claudectl.vercel.app/">claudectl.vercel.app</a></b><br>
  <sub>Everything below is the short version. Every feature, key binding and file is
  documented in detail on the docs site.</sub>
</p>

<p align="center">
  <img alt="claudectl dashboard" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/gui-dashboard.png" width="900">
</p>

---

## What problem does this solve?

Claude Code is excellent inside a session and forgetful between them. Every new
session starts from nothing, your old sessions are hard to find, and the only
way to give the agent context is a `CLAUDE.md` that grows until it costs more
than it's worth.

**claudectl sits in front of Claude Code and fixes that.** Pick a project, see
every session you've ever had in it, and launch with the model, effort,
permissions and context you meant. Underneath, it maintains a semantic memory
of the codebase and injects only the part relevant to what you just asked.

It is a terminal UI and a desktop GUI over the same engine — use whichever you
prefer, they do the same things.

## Quickstart

```bash
pipx install claudectl     # or: pip install claudectl
claudectl
```

There is nothing to build and no dependencies to install. To run it from a
checkout instead:

```bash
git clone https://github.com/babarmuhammad/claudectl.git
cd claudectl
python claude-sessions.py          # terminal UI
python claude-sessions.py --gui    # desktop GUI
```

Requires **Python 3.10+** and the
[Claude Code CLI](https://docs.anthropic.com/claude-code) (auto-detected on
PATH or at `~/.local/bin/`). No API key — it uses the Claude Code auth you
already have. No third-party packages.

It also ships as a Claude Code plugin, if you'd rather stay inside the session:

```
/plugin marketplace add babarmuhammad/claudectl
/plugin install claudectl@claudectl
```

→ [Full install guide](https://claudectl.vercel.app/install/)

## What it looks like

<table>
<tr>
<td width="50%"><img alt="Session browser" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/gui-sessions.png"><br>
<sub><b>Every session, every project.</b> Search, tag, fork, resume, archive,
export — across multiple Claude accounts at once.</sub></td>
<td width="50%"><img alt="Project memory" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/gui-memory.png"><br>
<sub><b>Memory Claude built about your code.</b> Entities, relations and
lessons, with the token cost of every block shown before you spend it.</sub></td>
</tr>
<tr>
<td><img alt="Usage" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/gui-usage.png"><br>
<sub><b>Where the tokens went.</b> Per day, per project, per account, per
model — read from your own transcripts, not an API.</sub></td>
<td><img alt="Claude Code's own state" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/gui-claude-code.png"><br>
<sub><b>Claude Code itself, made visible.</b> Which skills and plugins you
actually use, what is on disk, and a typed editor for every account's
settings.</sub></td>
</tr>
</table>

The terminal UI is the same tool, keyboard-first:

<p align="center">
  <img alt="claudectl TUI — project picker" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/tui-main.png" width="49%">
  <img alt="claudectl TUI — sessions" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/img/tui-sessions.png" width="49%">
</p>

<p align="center">
  <img alt="Architecture graph" src="https://raw.githubusercontent.com/babarmuhammad/claudectl/main/docs/graph-real.gif" width="820">
  <br><sub><b>The architecture graph</b> — every module and its dependencies,
  expandable down to single files (Python · C/C++ · C# · JS/TS).</sub>
</p>

<sub>Also: 29 palettes, 7 skins and 4 themed worlds — a skin changes the shape of the app,
not just its colours.
<a href="https://claudectl.vercel.app/gui/">See them →</a></sub>

---

## Why claudectl

- 🧠 **Intelligent memory, not a memory dump** — task-scoped, token-budgeted injection at the launcher: a micro-index always on (≤250 tok), per-module detail loaded only when Claude touches those files, and an optional per-prompt hook that injects just the subgraph relevant to what you asked.
- 📚 **It learns from every session** — durable lessons (fixes, decisions, preferences) distilled from transcripts, human-reviewed, injected when relevant, decayed when stale.
- 🕸️ **See your architecture** — an animated, expandable dependency graph that opens at the project level and drills down to single files.
- 🩺 **Auto-solves common Claude Code pain** — pre-launch health checks, context-loss insurance after `/compact`, permission-fatigue killer, token-burn advisor, daily usage tracking.
- 🤖 **Adaptive agents** — the right subagents suggested (or auto-applied) per project from local signals.
- 📦 **Workspace, not chats** — browse, search, tag, fork, resume and archive every Claude Code session across every project and account.
- ⚡ **Zero runtime dependencies** — pure Python standard library; uses your existing Claude Code auth.

### How claudectl saves tokens

Without claudectl, a big project either starves the agent (no context) or floods it (a huge CLAUDE.md loaded every message). claudectl spends the *minimum* tokens for the *maximum* relevant context:

- **Flat always-on cost** — the CLAUDE.md block is a ≤250-token index, not a full dump; it does **not** grow as the codebase grows.
- **On-demand detail** — per-module knowledge lives in path-scoped `.claude/rules/`, so nothing is paid for until it's relevant.
- **Task-scoped injection** — the optional prompt hook injects only the subgraph your prompt actually needs (budgeted, default ≤600 tok).
- **No stale weight** — superseded facts are invalidated, dead entities evicted.
- **Cheaper model for the grunt work** — Plan→Execute runs the expensive model once for the plan and a cheap (or free) one for execution.

→ [How the token economy works](https://claudectl.vercel.app/token-economy/)

---

## Documentation

The full manual lives at **[claudectl.vercel.app](https://claudectl.vercel.app/)**.

| | |
|---|---|
| [Install](https://claudectl.vercel.app/install/) | pipx, pip, checkout, plugin, GUI window, Windows shortcuts |
| [Download](https://claudectl.vercel.app/download/) | every way to get it, what a release contains, versioning |
| [Usage](https://claudectl.vercel.app/usage/) | every screen, every key binding, the command line |
| [Features](https://claudectl.vercel.app/features/) | one page per area — start here to see the whole surface |
| [Project memory](https://claudectl.vercel.app/memory/) | the three injection surfaces, lessons, recall |
| [Architecture graph](https://claudectl.vercel.app/graph/) | the interactive dependency view |
| [Plan → Execute](https://claudectl.vercel.app/plan-execute/) | two-model runs and free execution via OmniRoute |
| [Token economy](https://claudectl.vercel.app/token-economy/) | measuring and cutting the per-turn cost |
| [Reference](https://claudectl.vercel.app/reference/) | per-project files, workspace status, session encoding, layout |
| [API reference](https://claudectl.vercel.app/api/) | the local HTTP API the GUI is built on |
| [FAQ](https://claudectl.vercel.app/faq/) · [Compare](https://claudectl.vercel.app/compare/) · [Troubleshooting](https://claudectl.vercel.app/troubleshooting/) | honest answers, including what claudectl does *not* do |
| [Project dashboard](https://claudectl.vercel.app/dashboard/) | downloads, stars, test count, commit activity |

## Credits

claudectl is built on ideas from the wider Claude Code ecosystem — cognee and Aider's
repo-map behind the memory graph, Anthropic's `code-review` plugin behind `claudectl review`,
claude-mem behind recent-work memory, OmniRoute behind free execution, and VoltAgent's
subagent catalog behind the agent library. Every one is credited, with links, on the
[Credits page](https://claudectl.vercel.app/credits/).

## License

MIT — see [LICENSE](LICENSE).
