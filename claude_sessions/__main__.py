"""`python -m claude_sessions [...]` — same dispatch as claude-sessions.py.

Exists so the detached background memory worker (memory.spawn_background_worker)
can re-invoke claudectl without depending on the repo-root launcher script.

The statusline is dispatched HERE, before `main` is imported: `main` pulls the
whole TUI stack plus `usage`, which drags in urllib/ssl/http.client for an OAuth
poll the statusline must never make — 48ms of import on a path that runs on
every conversation turn.
"""
import sys

if len(sys.argv) >= 2 and sys.argv[1] == 'statusline':
    from .statusline import main
    raise SystemExit(main(sys.argv[2:]))

# The deferred self-upgrade worker (versions.update_self spawns it). Dispatched
# HERE for a second reason on top of the statusline's: pip is about to replace
# every file in this package, so the worker must hold no lazy import of one.
# `proc` imports os/subprocess/sys/time and nothing from claudectl.
if len(sys.argv) >= 4 and sys.argv[1] == '--self-update':
    from .proc import wait_and_run
    raise SystemExit(wait_and_run(sys.argv[2], sys.argv[3:]))

from .main import run

run()
