---
description: >-
  claudectl's hooks manager — 19 ready-made Claude Code hook templates (formatting, safety
  guardrails, audit, context injection, token savers), AI-generated hooks, and repair of
  broken ones.
---

# Hooks

- **19 ready-made templates** — one-key install, toggle, or remove (edits `settings.json` safely). Formatting (Prettier, Ruff, ESLint, gofmt), safety guardrails that **block** dangerous tools (`rm -rf`, `git reset --hard`, force-push, sudo, curl; reading `.env`; writing secrets — exit-code-2 blocks), audit/notify (log Bash commands, beep on finish / when input is needed), context injection (git status at session start; a compact **code-minimization** rule that curbs over-engineering — inspired by [Ponytail](https://github.com/DietrichGebert/ponytail)), and **token savers** (`concise-output` trims narration and re-printed code; `filter-test-output` pipes test runs through a failures-only filter before the output enters context). Guards/blocks run as bundled Python (shell-agnostic); formatters no-op when the tool is absent.
- **AI-generate a hook** — describe what you want in plain language; Claude returns a validated hook spec (event + matcher + command) you preview and confirm before it's saved.
- **Remove broken/legacy hooks** — one action purges hook commands that error under a bash hook shell.

Hooks are written into Claude Code's own `settings.json`, read-modify-write and atomically,
so your existing hooks, permissions and output style survive every edit. With multiple
[accounts](accounts.md) configured, `claudectl sync-accounts` places the same hooks in every
account's config dir.

SessionStart hook injections are counted by the
[context weight audit](usage.md) — a hook that injects on every session is a
per-turn cost like any other.

!!! note "The plugin ships no hooks, on purpose"

    claudectl's hook manager already places the recall, worklog and guard hooks per account.
    Bundling the same hooks in the [Claude Code plugin](plugin.md)
    would give one `settings.json` entry two owners: installing both runs the recall hook
    twice on every prompt, and uninstalling either leaves the other behind looking broken.
