"""Console-script entry point (`claudectl`).

Deliberately thin, and the statusline dispatch is deliberately duplicated from
__main__.py rather than shared: importing anything that would let it be shared is
the exact cost this exists to avoid. `main` pulls the whole TUI stack plus
`usage`, which drags in urllib/ssl/http.client for an OAuth poll the statusline
must never make — measured at 66ms of import on a path that runs on every
conversation turn, and the console script was paying it because it pointed
straight at main:run.
"""
import sys


def run():
    if len(sys.argv) >= 2 and sys.argv[1] == 'statusline':
        from .statusline import main
        raise SystemExit(main(sys.argv[2:]))
    from .main import run as _run
    _run()
