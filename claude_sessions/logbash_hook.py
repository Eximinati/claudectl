"""Claude Code PostToolUse hook — append the Bash command to
.claudectl/bash-log.txt (in the project cwd). Shell-agnostic; never errors.
"""

import sys
import os
import json

# Claude Code captures stdout as a PIPE, so CPython picks the locale
# codepage (cp1252 on Windows) and any non-ASCII character in the payload
# either mojibakes or raises — silently losing the whole hook output.
sys.stdout.reconfigure(encoding='utf-8')


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    cmd = str((data.get('tool_input') or {}).get('command', '')).strip()
    if not cmd:
        return 0
    cwd = data.get('cwd') or os.getcwd()
    try:
        d = os.path.join(cwd, '.claudectl')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, 'bash-log.txt')
        with open(p, 'a', encoding='utf-8') as f:
            f.write(cmd + '\n')
        _rotate(p)
    except Exception:
        pass
    return 0


#: this file had grown to 90 KB unbounded. Bounded in BYTES rather than lines:
#: a bash command has no characteristic length, and bytes is what the problem
#: actually was.
_MAX_BYTES = 64 * 1024
_KEEP_BYTES = _MAX_BYTES // 2


def _rotate(path):
    """Drop the oldest half once the log passes _MAX_BYTES. Size-gated so the
    common append does no extra I/O, and the trim reads only the tail — this
    runs inside a PreToolUse hook, on the turn's critical path."""
    try:
        if os.path.getsize(path) <= _MAX_BYTES:
            return
        with open(path, 'rb') as f:
            f.seek(-_KEEP_BYTES, os.SEEK_END)
            tail = f.read()
        # the seek lands mid-line; drop that partial first line
        tail = tail.split(b'\n', 1)[1] if b'\n' in tail else tail
        with open(path, 'wb') as f:
            f.write(tail)
    except Exception:
        pass


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
