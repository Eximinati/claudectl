"""Hook scripts write to a PIPE, so CPython picks the locale codepage (cp1252
here) for their streams unless they reconfigure.

Two things measured on Windows/CPython 3.10, because they decide which parts of
this are a real hazard and which are policy:

  - `sys.stdout` on a pipe is cp1252 with errors='strict' — a bare non-ASCII
    print RAISES. `test_a_bare_non_ascii_print_really_does_die_on_a_pipe` proves
    it rather than asserting it, so the policy below is not cargo cult.
  - `sys.stderr` is cp1252 with errors='backslashreplace' — it does NOT raise.
    So guard_hook's bare stderr write was never able to fail open, and this file
    does not claim it was; the try/except there is belt-and-braces.

The JSON-emitting hooks are safe for a third reason: `json.dumps` escapes
non-ASCII by default. That is a property of the payload, not of the stream, and
it silently stops holding the moment a hook prints anything that is not JSON —
which is what the policy test guards.

PYTHONIOENCODING is stripped from every child environment. With it set the
environment supplies the encoding and every test here passes for the wrong
reason.
"""

import json
import os
import pytest
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'claude_sessions')

#: cp1252 can encode none of these.
WIDE = 'caffè ▕ 日本 · €'


def _env():
    return {k: v for k, v in os.environ.items() if k != 'PYTHONIOENCODING'}


def _run(script, payload, *args):
    return subprocess.run([sys.executable, os.path.join(_PKG, script), *args],
                          input=payload, capture_output=True, timeout=30,
                          env=_env())


def _stdout_utf8(r):
    return r.stdout.decode('utf-8')          # raises if the child mangled it


@pytest.mark.skipif(os.name != 'nt',
                    reason='the hazard is cp1252 being picked for a pipe; a '
                           'POSIX default of UTF-8 simply does not raise')
def test_a_bare_non_ascii_print_really_does_die_on_a_pipe():
    """The hazard, demonstrated. Without this the policy test below is a rule
    with no evidence behind it."""
    naive = subprocess.run([sys.executable, '-c', 'print(%r)' % WIDE],
                           capture_output=True, env=_env())
    assert naive.returncode != 0
    assert b'UnicodeEncodeError' in naive.stderr

    fixed = subprocess.run(
        [sys.executable, '-c',
         "import sys;sys.stdout.reconfigure(encoding='utf-8');print(%r)" % WIDE],
        capture_output=True, env=_env())
    assert fixed.returncode == 0
    assert fixed.stdout.decode('utf-8').strip() == WIDE


def test_every_hook_script_reconfigures_stdout():
    """Policy, held for the whole family. A per-file judgement call is how five
    of the six came to be missing it, and the JSON-escaping that covers them
    today stops covering them the first time one prints something else."""
    missing = []
    for name in sorted(os.listdir(_PKG)):
        if not name.endswith('_hook.py'):
            continue
        src = open(os.path.join(_PKG, name), encoding='utf-8').read()
        if 'print(' not in src and 'stdout.write' not in src:
            continue
        if 'sys.stdout.reconfigure' not in src:
            missing.append(name)
    assert not missing, 'hook scripts printing without a utf-8 stdout: %s' % missing


def test_a_block_still_blocks_when_its_message_is_non_ascii():
    r = _run('guard_hook.py', b'{"tool_input":{"command":"rm -rf /"}}',
             'command', r'rm\s+-rf', WIDE)
    assert r.returncode == 2, r.stderr
    assert 'caff' in r.stderr.decode('utf-8', 'replace')
    assert _run('guard_hook.py', b'{"tool_input":{"command":"ls"}}',
                'command', r'rm\s+-rf', WIDE).returncode == 0


def test_session_start_rules_survive_a_pipe():
    for script in ('concise_hook.py', 'minimalcode_hook.py'):
        r = _run(script, b'{"hook_event_name":"SessionStart"}')
        assert r.returncode == 0, (script, r.stderr)
        out = json.loads(_stdout_utf8(r))
        assert out['hookSpecificOutput']['additionalContext'], script


def test_testfilter_round_trips_a_non_ascii_command():
    """The user's own command is echoed back into the rewritten JSON."""
    cmd = 'python -m pytest tests/caffè_日本/'
    payload = json.dumps({'hook_event_name': 'PreToolUse',
                          'tool_name': 'Bash',
                          'tool_input': {'command': cmd}}).encode('utf-8')
    r = _run('testfilter_hook.py', payload)
    assert r.returncode == 0, r.stderr
    out = json.loads(_stdout_utf8(r))
    assert 'caffè_日本' in out['hookSpecificOutput']['updatedInput']['command']
