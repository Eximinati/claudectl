---
description: >-
  Common claudectl problems and their fixes — missing claude.exe, editors that don't open,
  crashes, missing projects, wrong account, stale usage stats.
---

# Troubleshooting

| Symptom | Fix |
|---------|-----|
| "claude.exe not found" screen on startup | Install [Claude Code](https://docs.anthropic.com/claude-code), or set the path in **⚙ Settings** |
| Generated files don't open in an editor | Set your editor path in **⚙ Settings** (auto-detects Notepad++, VS Code, falls back to Notepad) |
| Window closes instantly with an error | Check `%TEMP%\claudectl_crash.log` — the crash handler writes the traceback there |
| Projects missing from the list | The project folder was moved/deleted, or the path can't be decoded — see [Session encoding](reference.md#session-encoding) |
| Wrong account / want a second account | Set **Config dir** in **⚙ Settings** to that account's `CLAUDE_CONFIG_DIR` (e.g. `~/.claude-work`). Drives both session browsing and the env handed to `claude` at launch. Blank = default `~/.claude`. Restart claudectl to apply. See [Multiple accounts](accounts.md) for running two at once. |
| Settings location | `~/.claude/claudectl.json` — safe to edit by hand or delete to reset (always read from `~/.claude`, independent of Config dir) |
| Usage stats look stale | Delete `~/.claude/claudectl-stats-cache.json` — it rebuilds on the next scan |
| GUI window tears or flickers | Set `stage: lite` in Settings first; if it persists, `stage: off`, or launch with `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu-compositing` |
| OmniRoute free execution not working | See the [Plan → Execute troubleshooting](plan-execute.md#troubleshooting) section |
| Something failed and said nothing | Open **⚙ Logs** (TUI) or the **Logs** page (GUI). Background jobs, the auto-memory scheduler and claudectl's own Claude calls all record their failures there |
| "No output from Claude" when generating an agent / skill / CLAUDE.md | Usually the account's limit. claudectl now says so by name and offers another account — see [Rate limits and a second account](tui.md#rate-limits-and-a-second-account) |
| An AI feature refuses to run | The active account's session or weekly window is full. Pick another account when asked, set `headless_quota` to `auto`, or to `off` to launch regardless |

## Where the logs are

| File | What it holds |
|------|---------------|
| `~/.claude/claudectl-events.jsonl` | **Start here.** claudectl's own events — failed Claude calls with what `claude` actually printed, job crashes, scheduler passes, quarantined state files. Capped at 256 KB. Shown by the Logs screen in both interfaces |
| `%TEMP%\claudectl_crash.log` | The traceback when the window closes instantly |
| `%TEMP%\claudectl.log` | Verbose DEBUG tracing — **only** written when `CLAUDECTL_DEBUG=1` is set. Unbounded; turn it on for one run |
| `~/.claude/failover.log` | The local failover proxy's requests, when it is running |

Still stuck? [Open an issue](https://github.com/babarmuhammad/claudectl/issues) — and check
the [FAQ](https://claudectl.space/faq/) first.
