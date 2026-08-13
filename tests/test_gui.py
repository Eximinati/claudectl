"""GUI server tests — real HTTP requests against a sandboxed server on an
ephemeral port, plus launch parity with the TUI's build_launch_command."""

import http.client
import json
import os
import pytest
import subprocess
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox, make_jsonl
from claude_sessions import gui
from claude_sessions import main as main_mod
from claude_sessions import config as config_mod


def _serve(monkeypatch):
    srv = gui.make_server(0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def _req(url, body=None, headers=None):
    h = {'X-Claudectl': gui.TOKEN}
    if headers is not None:
        h = headers
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h,
                               method='POST' if data else 'GET')
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def _seed(sb, monkeypatch):
    """One project with one titled session, resolvable by gui.list_projects."""
    actual = str(sb.root / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = 'X--enc-alpha'
    folder = sb.projects / enc
    folder.mkdir()
    sid = 'aaaa0000-0000-0000-0000-000000000000'
    make_jsonl(str(folder / f'{sid}.jsonl'), title='Fix the bug')
    monkeypatch.setattr(gui, 'find_actual_path', lambda e, *a, **k: actual if e == enc else None)
    return actual, enc, sid


def test_list_projects_and_sessions(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, sid = _seed(sb, monkeypatch)
    projs = gui.list_projects()
    assert len(projs) == 1
    assert projs[0]['encoded'] == enc and projs[0]['path'] == actual
    assert projs[0]['accounts'] == ['default']
    sess = gui.list_sessions(enc)
    assert len(sess) == 1
    assert sess[0]['sid'] == sid and sess[0]['title'] == 'Fix the bug'
    assert sess[0]['account'] == 'default'


def test_sessions_omni_flag(monkeypatch, tmp_path):
    """A session that ran on a non-Anthropic (OmniRoute free-tier) model is
    flagged omni=True; a plain Anthropic session is not."""
    sb = Sandbox(monkeypatch, tmp_path)
    actual = str(sb.root / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = 'X--enc-alpha'
    folder = sb.projects / enc
    folder.mkdir()
    make_jsonl(str(folder / 'aaaa0000-0000-0000-0000-000000000000.jsonl'),
               title='Anthropic run', model='claude-sonnet-5')
    make_jsonl(str(folder / 'bbbb0000-0000-0000-0000-000000000000.jsonl'),
               title='Omni run', model='deepseek-v4-flash-free')
    monkeypatch.setattr(gui, 'find_actual_path', lambda e, *a, **k: actual if e == enc else None)
    by_title = {s['title']: s for s in gui.list_sessions(enc)}
    assert by_title['Omni run']['omni'] is True
    assert by_title['Anthropic run']['omni'] is False
    # OmniRoute records bare provider model names (no slash namespace); the
    # discriminator is "not an Anthropic/Claude model".
    assert gui._used_omni({'models': ['big-pickle']}) is True
    assert gui._used_omni({'models': ['mimo-auto']}) is True
    assert gui._used_omni({'models': ['claude-opus-4-8', 'claude-sonnet-5']}) is False
    assert gui._used_omni({'models': ['sonnet']}) is False            # bare Claude alias
    assert gui._used_omni({'models': ['us.anthropic.claude-sonnet-5']}) is False
    # a mixed session (Claude + free-tier) still flags omni
    assert gui._used_omni({'models': ['claude-sonnet-5', 'big-pickle']}) is True
    assert gui._used_omni({'models': []}) is False


def test_http_state_and_sessions(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, sid = _seed(sb, monkeypatch)
    srv, base = _serve(monkeypatch)
    try:
        code, st = _req(base + '/api/state')
        assert code == 200
        assert st['projects'][0]['encoded'] == enc
        assert st['ui_mode'] == 'tui'
        assert 'efforts' in st['options'] and 'models' in st['options']
        code, d = _req(base + f'/api/sessions?enc={enc}')
        assert code == 200 and d['sessions'][0]['sid'] == sid
    finally:
        srv.shutdown()


def test_http_guard_rejects_missing_header(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        code, d = _req(base + '/api/state', headers={})   # no X-Claudectl
        assert code == 403
        code, d = _req(base + '/api/launch', body={'path': 'x'}, headers={})
        assert code == 403
    finally:
        srv.shutdown()


@pytest.mark.skipif(os.name != 'nt',
                    reason='asserts the Windows new-console spawn shape '
                           '(cmd /c title ... &&); POSIX uses a different '
                           'terminal table')
def test_http_launch_spawns_new_console(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, sid = _seed(sb, monkeypatch)
    calls = []
    monkeypatch.setattr(subprocess, 'Popen',
                        lambda cmd, **kw: calls.append((cmd, kw)) or None)
    srv, base = _serve(monkeypatch)
    try:
        code, d = _req(base + '/api/launch', body={
            'path': actual, 'enc': enc, 'choice': f'resume:{sid}',
            'opts': {'effort': 'high', 'model': 'claude-sonnet-5'}})
        assert code == 200 and d['ok'], d
    finally:
        srv.shutdown()
    (cmd, kw), = [c for c in calls if c[0][:2] == ['cmd', '/c']]
    # new-console pattern: cmd /c title "<title with space>" && <claude args>
    # (no `|| pause` — window must always close when claude exits, any code)
    assert cmd[2] == 'title'
    assert ' ' in cmd[3]                     # title must be quoted by list2cmdline
    assert cmd[4] == '&&'
    claude_args = cmd[5:]
    assert ['-r', sid] == claude_args[1:3]
    assert '--effort' in claude_args and 'high' in claude_args
    assert '--model' in claude_args and 'claude-sonnet-5' in claude_args
    assert kw['cwd'] == actual
    assert kw['env']['CLAUDE_CONFIG_DIR'] == str(sb.cfg)
    assert kw['creationflags'] == subprocess.CREATE_NEW_CONSOLE


@pytest.mark.skipif(os.name != 'nt',
                    reason='asserts the Windows new-console spawn shape '
                           '(cmd /c title ... &&); POSIX uses a different '
                           'terminal table')
def test_launch_parity_with_tui_builder(monkeypatch, tmp_path):
    """The argv the GUI hands to the new console must be exactly what the
    TUI's build_launch_command produces for the same inputs."""
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, sid = _seed(sb, monkeypatch)
    opts = {'effort': 'low', 'model': '', 'perm': 'plan', 'name': '',
            'worktree': '', 'agent': '', 'agents_json': '', 'cfgdir': '',
            'max_thinking': '8000', 'subagent_model': 'claude-haiku-4-5'}
    args, env, _pf = main_mod.build_launch_command(actual, enc, f'fork:{sid}', opts)
    calls = []
    monkeypatch.setattr(subprocess, 'Popen',
                        lambda cmd, **kw: calls.append((cmd, kw)) or None)
    ok, err = gui.launch_session(actual, enc, f'fork:{sid}', opts)
    assert ok, err
    (cmd, kw), = [c for c in calls if c[0][:2] == ['cmd', '/c']]
    assert cmd[5:] == args                      # exact argv parity, no trailing `|| pause`
    assert kw['env']['MAX_THINKING_TOKENS'] == '8000'
    assert kw['env']['CLAUDE_CODE_SUBAGENT_MODEL'] == 'claude-haiku-4-5'
    assert env['CLAUDE_CONFIG_DIR'] == kw['env']['CLAUDE_CONFIG_DIR']


def test_settings_ui_mode_roundtrip(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        code, d = _req(base + '/api/settings', body={'ui_mode': 'gui'})
        assert code == 200 and d['ok']
    finally:
        srv.shutdown()
    assert config_mod.load_settings()['ui_mode'] == 'gui'
    # invalid values are ignored, not saved
    srv, base = _serve(monkeypatch)
    try:
        _req(base + '/api/settings', body={'ui_mode': 'evil'})
    finally:
        srv.shutdown()
    assert config_mod.load_settings()['ui_mode'] == 'gui'


def test_settings_failover_roundtrip(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        code, d = _req(base + '/api/settings', body={
            'failover_models': ['  auto/a  ', '', 'auto/b'],
            'failover_port': 20130, 'failover_quiet': True})
        assert code == 200 and d['ok']
    finally:
        srv.shutdown()
    s = config_mod.load_settings()
    assert s['failover_models'] == ['auto/a', 'auto/b']   # stripped, blanks dropped
    assert s['failover_port'] == 20130
    assert s['failover_quiet'] is True


def test_settings_failover_accepts_newline_text_and_caps_length(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        _req(base + '/api/settings',
             body={'failover_models': '\n'.join('m%d' % i for i in range(20))})
    finally:
        srv.shutdown()
    assert config_mod.load_settings()['failover_models'] == ['m%d' % i for i in range(8)]


def test_state_payload_exposes_failover(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    from claude_sessions.gui import state_payload
    p = state_payload()
    assert p['failover_models'] == []
    assert p['failover_port'] == 20129
    assert p['failover_quiet'] is False


def test_rename_via_api(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, sid = _seed(sb, monkeypatch)
    srv, base = _serve(monkeypatch)
    try:
        code, d = _req(base + '/api/rename', body={
            'enc': enc, 'cfgdir': str(sb.cfg), 'sid': sid, 'name': 'My Feature'})
        assert code == 200 and d['ok']
    finally:
        srv.shutdown()
    from claude_sessions.sessions import load_name
    assert load_name(str(sb.projects / enc), sid) == 'My Feature'


def test_index_serves_html(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        with urllib.request.urlopen(base + '/') as r:
            body = r.read().decode('utf-8')
            assert r.status == 200
            assert 'claudectl' in body and '<html' in body
    finally:
        srv.shutdown()


# ── the guard is not just a custom header ────────────────────

def _raw(port, path='/api/state', method='GET', extra=None, host=None):
    """Full header control, incl. Host — urllib always sets Host to the address it
    dialled, which is precisely the thing a rebinding test has to spoof."""
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    h = {'Host': host or ('127.0.0.1:%d' % port)}
    h.update(extra or {})
    conn.request(method, path, headers=h)
    r = conn.getresponse()
    out = (r.status, r.read())
    conn.close()
    return out


def test_guard_requires_the_per_run_token(monkeypatch, tmp_path):
    """A constant header value is guessable by any local process that found the
    port; the token is not."""
    Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    port = srv.server_address[1]
    try:
        assert _raw(port, extra={'X-Claudectl': '1'})[0] == 403
        assert _raw(port, extra={'X-Claudectl': gui.TOKEN})[0] == 200
    finally:
        srv.shutdown()


def test_guard_rejects_a_rebound_host(monkeypatch, tmp_path):
    """DNS rebinding defeats a custom-header check outright: the attacker's page
    becomes same-origin with this server, so it can send any header it likes.
    Host is the one thing it cannot forge into our allowlist."""
    Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    port = srv.server_address[1]
    try:
        code, body = _raw(port, extra={'X-Claudectl': gui.TOKEN},
                          host='evil.example:%d' % port)
        assert code == 403 and b'bad host' in body
        # the unguarded routes are covered too, or the page itself leaks the token
        assert _raw(port, path='/', host='evil.example:%d' % port)[0] == 403
        assert _raw(port, path='/vendor/anime.esm.min.js',
                    host='evil.example:%d' % port)[0] == 403
    finally:
        srv.shutdown()


def test_page_carries_the_token_and_the_placeholder_never_ships(monkeypatch, tmp_path):
    Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    port = srv.server_address[1]
    try:
        code, body = _raw(port, path='/')
        assert code == 200
        assert gui.TOKEN.encode() in body
        assert b'__CLAUDECTL_TOKEN__' not in body
    finally:
        srv.shutdown()


def test_graph_is_guarded_and_validates_its_path(monkeypatch, tmp_path):
    """/graph cannot carry a header (window.open), so the token rides the query
    string — but it is not therefore exempt, and `path` reaches the filesystem."""
    Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    port = srv.server_address[1]
    real = str(tmp_path)
    try:
        assert _raw(port, path='/graph?path=%s' % real)[0] == 403
        assert _raw(port, path='/graph?k=nope&path=%s' % real)[0] == 403
        code, body = _raw(port, path='/graph?k=%s&path=%s'
                          % (gui.TOKEN, tmp_path / 'nope'))
        assert code == 400 and b'not a directory' in body
    finally:
        srv.shutdown()


def test_launch_refuses_a_path_that_is_not_a_directory(monkeypatch, tmp_path):
    """`path` arrives in a request body and becomes a subprocess cwd."""
    sb = Sandbox(monkeypatch, tmp_path)
    _actual, enc, sid = _seed(sb, monkeypatch)
    calls = []
    monkeypatch.setattr(subprocess, 'Popen',
                        lambda cmd, **kw: calls.append(cmd) or None)
    ok, err = gui.launch_session(str(tmp_path / 'not-there'), enc, f'resume:{sid}', {})
    assert not ok and 'not a directory' in err
    assert calls == []


def test_responses_carry_the_hardening_headers(monkeypatch, tmp_path):
    Sandbox(monkeypatch, tmp_path)
    srv, base = _serve(monkeypatch)
    try:
        r = urllib.request.Request(base + '/api/state',
                                   headers={'X-Claudectl': gui.TOKEN})
        with urllib.request.urlopen(r) as resp:
            h = dict(resp.headers)
        assert h['X-Content-Type-Options'] == 'nosniff'
        assert h['X-Frame-Options'] == 'DENY'
        assert "frame-ancestors 'none'" in h['Content-Security-Policy']
    finally:
        srv.shutdown()
