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
