---
title: claudectl FAQ
description: >-
  Common questions about claudectl — managing Claude Code sessions on Windows, reducing
  token usage, running multiple accounts, dependencies, platform support and the GUI.
jsonld: |
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {"@type": "Question", "name": "How do I manage Claude Code sessions on Windows?",
       "acceptedAnswer": {"@type": "Answer", "text": "Claude Code stores each session as a JSONL transcript under your config directory, but gives you no way to browse them. claudectl lists every session per project with its topic, message count and age, and lets you search, tag, fork, resume, export and archive them from a terminal UI or a desktop GUI."}},
      {"@type": "Question", "name": "How do I reduce Claude Code token usage?",
       "acceptedAnswer": {"@type": "Answer", "text": "The largest recurring cost is context you pay for on every message. claudectl keeps the always-on CLAUDE.md block to a bounded index of about 250 tokens, moves per-module detail into path-scoped rules files that load only when Claude touches those files, and can inject only the memory subgraph a given prompt needs. It also routes its own internal calls to a cheap model and can run Plan to Execute with an expensive model for planning and a cheap one for execution."}},
      {"@type": "Question", "name": "Does claudectl require any Python dependencies?",
       "acceptedAnswer": {"@type": "Answer", "text": "No. claudectl runs on the Python standard library alone and needs Python 3.10 or newer. PyQt6 is optional and only needed for the native desktop shell; without it the GUI opens in your browser."}},
      {"@type": "Question", "name": "Does claudectl work on macOS and Linux, or only Windows?",
       "acceptedAnswer": {"@type": "Answer", "text": "It runs on Windows, macOS and Linux, and CI tests all three. It is Windows-first in the sense that Windows gets the widest Python version matrix and the most real-world use, so rough edges are likelier elsewhere."}},
      {"@type": "Question", "name": "How is claudectl different from Claude Code's built-in resume?",
       "acceptedAnswer": {"@type": "Answer", "text": "The resume command reattaches you to a recent session in the current directory. claudectl treats sessions as a searchable archive across every project and account, adds tags, export, fork and archive, and controls what model, effort, permissions and project context the session launches with."}},
      {"@type": "Question", "name": "Is claudectl free and open source?",
       "acceptedAnswer": {"@type": "Answer", "text": "Yes. It is MIT licensed and free. It uses your existing Claude Code authentication and does not add a subscription or an API key of its own."}}
    ]
  }
---

# Frequently asked questions

## How do I manage Claude Code sessions on Windows?

Claude Code stores every session as a JSONL transcript under your config directory, but
gives you no way to browse them. claudectl lists every session per project with its topic,
message count and age, and lets you search, tag, fork, resume, export and archive them —
from a terminal UI or a desktop GUI.

[Session management →](features.md)

## How do I reduce Claude Code token usage?

The largest recurring cost is context you pay for on *every* message. claudectl attacks it
in four places:

- the always-on `CLAUDE.md` block is a bounded index of ~250 tokens, not a full dump, and
  does not grow with the codebase;
- per-module detail lives in path-scoped `.claude/rules/` files that load only when Claude
  touches those files;
- an optional prompt hook injects only the memory subgraph your prompt actually needs;
- claudectl's own internal calls (memory extraction, lesson distillation, generation) route
  to a cheap economy model, and Plan → Execute runs an expensive model once for the plan
  and a cheap one for execution.

[Token economy →](token-economy.md)

## What is a Claude Code MCP server manager?

MCP servers are configured in JSON and are otherwise invisible — you cannot easily tell
which are connected to a project or what tools they expose. claudectl detects the servers
configured for each project, shows them at a glance, and can run an analysis that lists a
server's actual tools into your global `CLAUDE.md` inside a re-updatable block.

## How do I run multiple Claude accounts at the same time?

Claude Code selects its account through the `CLAUDE_CONFIG_DIR` environment variable.
claudectl detects every configured account, merges their projects into one list, shows
per-account usage side by side, and sets that variable for you when it launches a session,
so you pick the account at launch rather than juggling environment variables.

## Does claudectl require any Python dependencies?

No. It runs on the Python standard library alone and needs Python 3.10 or newer. PyQt6 is
optional and only needed for the native desktop shell — without it the GUI opens in your
browser instead.

## Does claudectl work on macOS and Linux, or only Windows?

It runs on all three, and CI tests all three. It is Windows-first in that Windows gets the
widest Python version matrix and the most real-world use, so rough edges are likelier on
macOS and Linux. Bug reports from those platforms are welcome.

## How is claudectl different from Claude Code's built-in `/resume`?

`/resume` reattaches you to a recent session in the current directory. claudectl treats
your sessions as a searchable archive across every project *and every account*, adds tags,
export, fork and archive, and controls what model, effort, permissions and project context
a session launches with. `/resume` answers "put me back"; claudectl answers "what have I
done here, and how should the next session start".

## Can I use a cheaper model to execute a plan made by a stronger model?

Yes — that is what Plan → Execute does. It runs a headless planning pass with the strong
model, shows you the plan for approval or editing, then hands the approved plan to a
cheaper model to carry out.

## What happens to my project memory after `/compact`?

`/compact` discards detail from the conversation, which is where context loss usually
bites. claudectl's memory lives outside the transcript — in the project's memory graph and
its rules files — so it is re-injected at the next launch regardless of what the
conversation dropped.

## Does claudectl have a GUI, or is it terminal-only?

Both, over the same engine. The terminal UI is the default. `claudectl --gui` opens a
desktop GUI — a native window if PyQt6 is installed, otherwise your browser, served over
loopback only.

## Is claudectl free and open source?

Yes, MIT licensed. It uses your existing Claude Code authentication and adds no
subscription and no API key of its own.

## Can I install it from PyPI?

Not yet — the package is not published. Clone the repo and run `pip install -e .`, or run
it straight from the checkout. See [Install](install.md).
