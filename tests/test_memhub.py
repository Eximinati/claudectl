import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox, run_flow, ESC, ENTER, typed

from claude_sessions import memhub, memory


def flat(*parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def _graph():
    return {'schema_version': 2, 'entities': [
        {'name': 'Engine', 'type': 'component', 'summary': 'core',
         'repo': 'svc', 'module': 'engine', 'source_files': ['svc/e.py'], 'rank': 3},
        {'name': 'L1', 'type': 'lesson', 'status': 'pending', 'summary': 'x',
         'repo': '', 'module': '(project)', 'source_files': [], 'rank': 0}],
        'relations': [], 'summaries': {'svc/engine': 'engine'}, 'provenance': {},
        'module_edges': [], 'lessons_scanned': {}, 'session_counter': 0,
        'generated_at': '2026-07-03T00:00:00+00:00'}


def test_hub_renders_state(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    memory.save_memory(actual, folder, _graph())
    _res, cap, _ = run_flow(monkeypatch, ESC, memhub.hub_screen, actual, folder, 'alpha')
    plain = cap.plain
    assert '1 entities' in plain
    assert '1 lessons' in plain and 'pending review' in plain
    assert 'What Claude sees' in plain
    assert 'recall hook' in plain


def test_hub_empty_state(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    _res, cap, _ = run_flow(monkeypatch, ESC, memhub.hub_screen, actual, folder, 'alpha')
    assert 'no memory yet' in cap.plain
    assert 'press b to build' in cap.plain


def test_hub_toggle_hook(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    memory.save_memory(actual, folder, _graph())
    from claude_sessions import hooks
    monkeypatch.setattr(hooks, 'settings_path', str(sb.cfg / 'settings.json'))
    keys = flat(typed('h'), ESC)
    run_flow(monkeypatch, keys, memhub.hub_screen, actual, folder, 'alpha')
    from claude_sessions.config import load_settings
    from claude_sessions.paths import encode_component
    s = load_settings()
    proj = s['project_defaults'][encode_component(os.path.abspath(actual))]
    assert proj['memory_hook'] is True
    assert hooks.memory_hook_installed()
