"""`claudectl statusline` — one line under every Claude Code prompt.

Claude Code runs a `statusLine.command` from settings.json, pipes it session
JSON on stdin, and renders the first line of stdout. It refreshes whenever the
conversation changes, throttled to 300ms.

WHY CLAUDECTL SHOULD SHIP ONE
-----------------------------
There is a whole category of statusline tools and they all show the same four
things, because that is all the stdin payload contains: model, directory, cost,
context usage. claudectl knows things none of them can:

  · whether this project's memory is FRESH or stale, and by how long
  · how many lessons are waiting for review
  · which account this session is burning, out of several
  · today's burn against your own heaviest day, not an absolute number

That is the difference between a readout and a warning. "memory 6d" is the one
piece of information that changes what you do next, and only the tool that
maintains the memory can say it.

It also changes where claudectl lives: today it is something you use *between*
sessions. This puts it in front of you *during* every one.

CONSTRAINTS THAT SHAPE THIS FILE
--------------------------------
It runs on every conversation turn, so it must be fast and it must never fail
loudly. A statusline that throws leaves a Python traceback under the user's
prompt for the rest of the session — so every read is guarded and any error
degrades to a shorter line, never to a crash. It also must not do a transcript
scan: the dashboard's aggregate is far too expensive to run per turn, so the
numbers here come from files claudectl has already written.
"""

import json
import os
import re
import sys
import time

#: ANSI, kept minimal — the terminal is the user's and its palette is not ours
_DIM = '\033[2m'
_OFF = '\033[0m'
_WARN = '\033[33m'
_ERR = '\033[31m'
_SEP = f'{_DIM} · {_OFF}'


def _age(seconds):
    """Compact age: 20m / 4h / 6d. Never a date — the point is the distance."""
    if seconds < 90:
        return 'now'
    if seconds < 5400:
        return f'{int(seconds // 60)}m'
    if seconds < 172800:
        return f'{int(seconds // 3600)}h'
    return f'{int(seconds // 86400)}d'


def _load(project_path):
    """The graph for this cwd. `load_memory` resolves the folder itself, so the
    statusline never has to reproduce the encoding rules."""
    from . import memory
    return memory.load_memory(project_path)


def _iso_age(stamp):
    """Seconds since an ISO timestamp, or None. The graph records its own
    `generated_at`, which beats stat-ing a file — it is the age of the DATA,
    not of the last time something touched the file."""
    if not stamp:
        return None
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return max(0.0, datetime.now(timezone.utc).timestamp() - t.timestamp())
    except Exception:
        return None


def _memory_bit(mem):
    """`memory 4h` — amber past a week, red past two.

    This is the bit no other statusline can print, and the only one here that
    changes what you do next: a graph that has not been rebuilt in six days is
    quietly feeding the agent a stale picture of the codebase.
    """
    if not mem.get('entities'):
        return f'{_DIM}no memory{_OFF}'
    age = _iso_age(mem.get('auto_updated') or mem.get('generated_at'))
    if age is None:
        return ''
    col = _ERR if age > 1209600 else (_WARN if age > 604800 else _DIM)
    return f'{col}memory {_age(age)}{_OFF}'


def _lessons_bit(mem):
    """`3 to review` — pending lessons, which now go unnoticed *because* the
    mining became automatic. Nothing else surfaces them mid-session."""
    n = sum(1 for e in mem.get('entities', [])
            if e.get('type') == 'lesson' and e.get('status') == 'pending')
    return f'{_WARN}{n} to review{_OFF}' if n else ''


def _account_bit():
    """Which account is being spent. Only shown when there are several — on a
    single-account setup it is noise."""
    try:
        from . import config as _c
        accts = _c.all_config_dirs()
        if len(accts) < 2:
            return ''
        cur = os.path.normcase(os.path.abspath(_c.config_dir))
        for name, d in accts:
            if os.path.normcase(os.path.abspath(d)) == cur:
                return f'{_DIM}{name}{_OFF}'
    except Exception:
        pass
    return ''


def _context_bit(data):
    """Context pressure, straight from the payload — amber past 70%, red past
    85%, absent below half, because a number you cannot act on is decoration."""
    try:
        pct = None
        for key in ('context_used_pct', 'contextUsedPercent'):
            if isinstance(data.get(key), (int, float)):
                pct = float(data[key])
        if pct is None:
            used = (data.get('context') or {}).get('used')
            total = (data.get('context') or {}).get('total')
            if used and total:
                pct = 100.0 * used / total
        if pct is None or pct < 50:
            return ''
        col = _ERR if pct >= 85 else (_WARN if pct >= 70 else _DIM)
        return f'{col}ctx {int(pct)}%{_OFF}'
    except Exception:
        return ''


def render(data):
    """Build the line from one stdin payload. Pure — the tests call this."""
    cwd = data.get('cwd') or (data.get('workspace') or {}).get('current_dir') or ''
    model = ((data.get('model') or {}).get('display_name')
             or (data.get('model') or {}).get('id') or '')
    bits = []
    if model:
        bits.append(model)
    acct = _account_bit()
    if acct:
        bits.append(acct)
    if cwd:
        # one read, both bits — this runs on every conversation turn
        try:
            mem = _load(cwd)
            bits.append(_memory_bit(mem))
            bits.append(_lessons_bit(mem))
        except Exception:
            pass
    bits.append(_context_bit(data))
    cost = (data.get('cost') or {}).get('total_cost_usd')
    if isinstance(cost, (int, float)) and cost > 0:
        bits.append(f'{_DIM}${cost:.2f}{_OFF}')
    return _SEP.join(b for b in bits if b)


# ── install / remove ─────────────────────────────────────────
# Writes Claude Code's own settings.json, reusing hooks.py's accessors so there
# is one reader and one writer for that file rather than two that can disagree.

_ANSI = re.compile(r'\[[0-9;]*m')


def plain(line):
    """The same line without colour, for the GUI preview.

    The statusline is written for a terminal, so it carries SGR codes. Rendering
    those into HTML would show the escape sequences themselves — the preview has
    to be the text, not the bytes.
    """
    return _ANSI.sub('', line)


def _command():
    """`"<python>" -m claude_sessions statusline`, absolute and quoted so it
    works whatever shell Claude Code invokes it through — the same reasoning as
    hooks._py_hook."""
    return f'"{sys.executable}" -m claude_sessions statusline'


def is_installed():
    from . import hooks
    sl = (hooks._load().get('statusLine') or {})
    return 'claude_sessions' in str(sl.get('command', ''))


def install():
    """Point settings.json at us. Returns (ok, message).

    Refuses to clobber someone else's statusline: that is a single-valued key,
    and quietly replacing a line the user built themselves would be exactly the
    kind of silent overwrite the memory work went to lengths to avoid.
    """
    from . import hooks
    s = hooks._load()
    cur = (s.get('statusLine') or {}).get('command', '')
    if cur and 'claude_sessions' not in str(cur):
        return False, f'A different statusline is already set: {str(cur)[:60]}'
    s['statusLine'] = {'type': 'command', 'command': _command()}
    return (True, 'Statusline installed') if hooks._save(s) else (False, 'Write failed')


def remove():
    from . import hooks
    s = hooks._load()
    if not is_installed():
        return False, 'Not installed'
    s.pop('statusLine', None)
    return (True, 'Statusline removed') if hooks._save(s) else (False, 'Write failed')


def main(argv=None):
    """Read one JSON payload from stdin, print one line. Never raises.

    Claude Code renders only the FIRST line of stdout, and anything on stderr is
    the user's problem for the rest of the session — so failure here has to be
    silence, not a traceback under the prompt.
    """
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    try:
        line = render(data)
    except Exception:
        line = ''
    sys.stdout.write(line.replace('\n', ' ') + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
