"""Dashboard endpoint tests — /api/dashboard aggregate shape + the
always-show usage contract on /api/usage_plan (empty accounts never dropped)."""

import json
import os
import threading
import time
import urllib.request

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox, make_jsonl
from claude_sessions import gui
from claude_sessions import gui_api


def _serve(monkeypatch):
    srv = gui.make_server(0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def _req(url, body=None, headers=None):
    h = {'X-Claudectl': '1'}
    if headers is not None:
        h = headers
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h,
                               method='POST' if data else 'GET')
    with urllib.request.urlopen(r) as resp:
        return resp.status, json.loads(resp.read() or b'{}')


def _fresh(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    gui_api._dash_cache = None            # dashboard caches 10s module-global
    gui_api._dash_cached_at = 0.0
    with gui_api._JOBS_LOCK:
        gui_api._JOBS.clear()
    return sb


def _seed(sb, monkeypatch):
    actual = str(sb.root / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = 'X--enc-alpha'
    folder = sb.projects / enc
    folder.mkdir()
    sid = 'aaaa0000-0000-0000-0000-000000000000'
    make_jsonl(str(folder / f'{sid}.jsonl'), title='Fix the bug')
    monkeypatch.setattr(gui, 'find_actual_path', lambda e: actual if e == enc else None)
    return actual, enc, sid


def _write_today(path, model, tokens=1000):
    """Transcript stamped *now*, so it lands inside the breakdown window."""
    import datetime
    ts = datetime.datetime.now().astimezone().isoformat()
    rows = [{'role': 'user', 'content': 'hello there', 'timestamp': ts},
            {'type': 'assistant',
             'message': {'role': 'assistant', 'model': model,
                         'usage': {'input_tokens': tokens, 'output_tokens': tokens,
                                   'cache_read_input_tokens': 0,
                                   'cache_creation_input_tokens': 0},
                         'content': [{'type': 'text', 'text': 'hi'}]},
             'timestamp': ts}]
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')


def test_dashboard_breakdown_splits_accounts_and_flags_omni(monkeypatch, tmp_path):
    """One scan feeds the whole dashboard: per-day tokens attributed per account,
    per-project OmniRoute flag, and free-tier tokens costed at zero."""
    sb = _fresh(monkeypatch, tmp_path)
    second = tmp_path / 'cfg2' / 'projects'
    second.mkdir(parents=True)
    monkeypatch.setattr('claude_sessions.config.all_config_dirs',
                        lambda: [('default', str(sb.cfg)), ('work', str(tmp_path / 'cfg2'))])
    actual = str(sb.root / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = 'X--enc-alpha'
    (sb.projects / enc).mkdir()
    (second / enc).mkdir()
    _write_today(sb.projects / enc / 'a.jsonl', 'claude-sonnet-4-6')
    _write_today(second / enc / 'b.jsonl', 'big-pickle')       # OmniRoute free tier
    for mod in ('claude_sessions.gui.find_actual_path',
                'claude_sessions.paths.find_actual_path'):
        monkeypatch.setattr(mod, lambda e: actual if e == enc else None)
    srv, base = _serve(monkeypatch)
    try:
        _code, d = _req(f'{base}/api/dashboard')
        bd = d['breakdown']
        accts = {a['account']: a for a in bd['accounts']}
        assert set(accts) == {'default', 'work'}
        assert accts['work']['omni_tokens'] > 0
        assert accts['work']['cost'] == 0.0            # free-tier model costs nothing
        assert accts['default']['omni_tokens'] == 0
        assert accts['default']['cost'] > 0
        today = bd['days'][-1]
        assert today['tokens'] > 0
        assert sum(today['accounts'].values()) == today['tokens']
        assert set(today['accounts']) == {'default', 'work'}
        proj = bd['projects'][0]
        assert proj['omni'] is True
        assert sorted(proj['accounts']) == ['default', 'work']
        assert bd['totals']['omni_saved'] > 0          # what OmniRoute avoided
    finally:
        srv.shutdown()


def test_dashboard_recent_spans_accounts_and_skips_headless_oneshots(monkeypatch, tmp_path):
    """Recent sessions come from the transcript scan, not last-session.json —
    that store only knows sessions claudectl itself launched, so anything opened
    with `claude` directly (or under another account) never appeared."""
    sb = _fresh(monkeypatch, tmp_path)
    second = tmp_path / 'cfg2' / 'projects'
    second.mkdir(parents=True)
    monkeypatch.setattr('claude_sessions.config.all_config_dirs',
                        lambda: [('default', str(sb.cfg)), ('work', str(tmp_path / 'cfg2'))])
    actual = str(sb.root / 'work' / 'alpha')
    os.makedirs(actual, exist_ok=True)
    enc = 'X--enc-alpha'
    (sb.projects / enc).mkdir()
    (second / enc).mkdir()
    make_jsonl(str(sb.projects / enc / 'real-default.jsonl'), n_msgs=12, title='Real work')
    make_jsonl(str(second / enc / 'real-work.jsonl'), n_msgs=12, title='Other account')
    make_jsonl(str(sb.projects / enc / 'oneshot.jsonl'), n_msgs=2, title='Distil lessons')
    for mod in ('claude_sessions.gui.find_actual_path',
                'claude_sessions.paths.find_actual_path'):
        monkeypatch.setattr(mod, lambda e: actual if e == enc else None)
    srv, base = _serve(monkeypatch)
    try:
        _code, d = _req(f'{base}/api/dashboard')
        sids = [r['sid'] for r in d['recent']]
        assert 'real-default' in sids and 'real-work' in sids
        assert 'oneshot' not in sids
        assert {r['account'] for r in d['recent']} == {'default', 'work'}
        assert all(r['mtime'] > 0 and r['age'] for r in d['recent'])
    finally:
        srv.shutdown()


def test_dashboard_week_is_7_and_increasing(monkeypatch, tmp_path):
    sb = _fresh(monkeypatch, tmp_path)
    _seed(sb, monkeypatch)
    srv, base = _serve(monkeypatch)
    try:
        _code, d = _req(f'{base}/api/dashboard')
        assert _code == 200
        week = d['week']
        assert len(week) == 7
        dates = [w['date'] for w in week]
        assert dates == sorted(dates)
        assert len(set(dates)) == 7            # strictly increasing, no dupes
    finally:
        srv.shutdown()


def test_dashboard_jobs_elapsed_is_int(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    job = {'id': 'fakejob123', 'status': 'running', 'label': 'test job',
           'messages': [], 'error': '', 'gate': None, 'decision': None,
           'decision_evt': threading.Event(), 'inputs': [], 'started': time.time(),
           'cancelled': False, 'cancel_event': threading.Event(), 'procs': []}
    with gui_api._JOBS_LOCK:
        gui_api._JOBS[job['id']] = job
    srv, base = _serve(monkeypatch)
    try:
        _code, d = _req(f'{base}/api/dashboard')
        jobs = d['jobs']
        assert any(j['id'] == 'fakejob123' for j in jobs)
        assert all(isinstance(j['elapsed'], int) for j in jobs)
    finally:
        srv.shutdown()


def test_usage_plan_returns_every_configured_account(monkeypatch, tmp_path):
    """An account configured but with zero transcripts still appears — the
    regression guard for 'usage must always show'."""
    sb = _fresh(monkeypatch, tmp_path)
    empty_dir = tmp_path / 'empty-cfg'
    empty_dir.mkdir()
    with open(sb.settings, 'w', encoding='utf-8') as f:
        json.dump({'accounts': [{'name': 'second', 'dir': str(empty_dir)}]}, f)
    srv, base = _serve(monkeypatch)
    try:
        _code, d = _req(f'{base}/api/usage/plan')
        accts = {a['account']: a for a in d['accounts']}
        assert 'default' in accts
        assert 'second' in accts
        assert accts['second']['windows'] == []      # zero data → empty windows
    finally:
        srv.shutdown()
