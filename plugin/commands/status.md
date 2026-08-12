---
description: Workspace status for this project — memory age, repos, and health
---

Run `claudectl workspace status` with the Bash tool from the project root and
show what it reports.

It prints the state claudectl tracks for this workspace: how stale the project
memory is, which repositories and worktrees are underneath it, and the health
checks that catch the common Claude Code problems (a CLAUDE.md that has grown
past its budget, a memory graph that has not been rebuilt since the code moved,
directories that no longer exist).

Summarise it — do not paste the whole output back. Lead with anything that
needs action, and say plainly when nothing does. If the command is not found,
say claudectl is not installed (`pip install claudectl`).
