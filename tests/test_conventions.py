import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox

from claude_sessions import conventions, memory
from claude_sessions.config import _CONV_START, _CONV_END


def _pref(summary, status='approved', kind='preference', conf=0.9):
    return {'name': summary[:20], 'type': 'lesson', 'kind': kind, 'status': status,
            'summary': summary, 'confidence': conf, 'repo': '', 'module': '(project)'}


def test_promotes_recurring_convention(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    a1, e1, f1, _ = sb.add_project('alpha')
    a2, e2, f2, _ = sb.add_project('beta')
    conv = 'this machine uses PowerShell 5.1 not bash'
    m1 = memory._empty(); m1['entities'] = [_pref(conv)]
    memory.save_memory(a1, f1, m1)
    m2 = memory._empty(); m2['entities'] = [_pref('this machine uses PowerShell 5.1 not bash syntax')]
    memory.save_memory(a2, f2, m2)
    got = conventions.collect_conventions()
    assert any('PowerShell' in s for s, _sc in got)   # recurs across 2 projects


def test_single_project_not_promoted_unless_pinned(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    a1, e1, f1, _ = sb.add_project('alpha')
    m1 = memory._empty(); m1['entities'] = [_pref('one-off preference only here')]
    memory.save_memory(a1, f1, m1)
    assert conventions.collect_conventions() == []
    # pinned single-project → promoted
    m1['entities'][0]['status'] = 'pinned'
    memory.save_memory(a1, f1, m1)
    assert conventions.collect_conventions()


def test_sync_writes_global_block(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    a1, e1, f1, _ = sb.add_project('alpha')
    a2, e2, f2, _ = sb.add_project('beta')
    c = 'prefer pytest over unittest for tests'
    for a, f in ((a1, f1), (a2, f2)):
        m = memory._empty(); m['entities'] = [_pref(c)]
        memory.save_memory(a, f, m)
    assert conventions.sync_to_global()
    from claude_sessions.config import global_claude_md
    text = open(global_claude_md, encoding='utf-8').read()
    assert _CONV_START in text and _CONV_END in text and 'pytest' in text


def test_sync_disabled_setting(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr('claude_sessions.config.load_settings',
                        lambda: {'conventions_to_global': False})
    assert conventions.sync_to_global() is False
