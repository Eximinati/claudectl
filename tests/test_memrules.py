import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox

from claude_sessions import memrules, memory


def _mem():
    return {
        'entities': [
            {'name': 'Engine', 'type': 'component', 'summary': 'core engine',
             'repo': 'svc', 'module': 'engine', 'source_files': ['svc/engine/core.py']},
            {'name': 'Cache', 'type': 'component', 'summary': 'lru cache',
             'repo': 'svc', 'module': 'engine', 'source_files': ['svc/engine/cache.py']},
            {'name': 'Lonely', 'type': 'component', 'summary': 'single entity',
             'repo': 'svc', 'module': 'tiny', 'source_files': ['svc/tiny/x.py']},
            {'name': 'L', 'type': 'lesson', 'status': 'approved', 'summary': 'x',
             'repo': 'svc', 'module': 'engine', 'source_files': []},
        ],
        'relations': [{'source': 'Engine', 'target': 'Cache', 'rel': 'uses', 'unit': 'svc/engine'}],
        'summaries': {'svc/engine': 'the engine module'},
    }


def test_sync_writes_globs_rule(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    written = memrules.sync_rules(actual, folder, _mem())
    assert written == [memrules.rule_filename('svc', 'engine')]
    p = os.path.join(actual, '.claude', 'rules', written[0])
    body = open(p, encoding='utf-8').read()
    assert 'globs: "svc/engine/**"' in body
    assert 'Engine' in body and 'Cache' in body
    assert 'the engine module' in body
    assert 'Engine uses Cache' in body
    assert 'Lonely' not in body                     # <2 entities → no rule
    assert '- L (' not in body                      # lessons never in rules


def test_sync_prunes_only_own_files(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    rules_dir = os.path.join(actual, '.claude', 'rules')
    os.makedirs(rules_dir)
    stale = os.path.join(rules_dir, 'claudectl-mem-old-unit.md')
    user = os.path.join(rules_dir, 'my-own-rule.md')
    open(stale, 'w').write('x')
    open(user, 'w').write('mine')
    memrules.sync_rules(actual, folder, _mem())
    assert not os.path.exists(stale)                 # our stale file pruned
    assert os.path.exists(user)                      # user rule untouched


def test_rule_token_cap(monkeypatch, tmp_path):
    ents = [{'name': f'E{i}', 'type': 'component', 'summary': 'word ' * 60,
             'repo': 'r', 'module': 'm', 'source_files': ['r/m/a.py']} for i in range(40)]
    body = memrules.render_rule('r', 'm', 'summary', ents, [])
    assert memory.tokens_estimate(body) <= memrules.RULE_MAX_TOKENS + 20


def test_setting_disables(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    monkeypatch.setattr('claude_sessions.config.load_settings',
                        lambda: {'memory_rules': False})
    assert memrules.sync_rules(actual, folder, _mem()) == []
    assert not os.path.isdir(os.path.join(actual, '.claude', 'rules'))
