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

from .main import run

run()
