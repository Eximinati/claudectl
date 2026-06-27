import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox

from claude_sessions import memory, connections


def _mkfile(base, rel, content='x = 1\n'):
    p = os.path.join(base, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    return p


def _stub(monkeypatch, calls=None):
    """Stub Claude extraction: one entity named after the unit, so coverage is
    checkable. Records the units it was called for."""
    def fake(corpus, cwd, unit='', progress=''):
        if calls is not None:
            calls.append(unit)
        return {'summary': f'summary of {unit}',
                'entities': [{'name': f'E[{unit}]', 'type': 'module', 'summary': 's'}],
                'relations': []}
    monkeypatch.setattr(memory, '_extract', fake)


# ── persistence ──────────────────────────────────────────────

def test_migrate_has_summaries(monkeypatch, tmp_path):
    Sandbox(monkeypatch, tmp_path)
    m = memory._migrate({'entities': []})
    assert 'summaries' in m and m['schema_version'] == memory.SCHEMA_VERSION


# ── whole-project coverage ───────────────────────────────────

def test_refresh_covers_every_unit(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    _mkfile(actual, 'mod1/a.py')
    _mkfile(actual, 'mod2/b.py')
    calls = []
    _stub(monkeypatch, calls)
    mem = memory.refresh_memory(actual, folder, 'alpha')
    repos = {e['repo'] for e in mem['entities']}
    assert repos == {'mod1', 'mod2'}                 # every top-level unit covered
    assert set(calls) == {'mod1/(root)', 'mod2/(root)'}
    assert mem['summaries']                           # per-unit summaries stored


def test_incremental_only_changed_unit(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    _mkfile(actual, 'mod1/a.py')
    _mkfile(actual, 'mod2/b.py')
    calls = []
    _stub(monkeypatch, calls)
    memory.refresh_memory(actual, folder, 'alpha')
    assert len(calls) == 2
    calls.clear()
    memory.refresh_memory(actual, folder, 'alpha')   # nothing changed
    assert calls == []
    _mkfile(actual, 'mod1/a.py', 'changed = True\n')  # only mod1 changes
    memory.refresh_memory(actual, folder, 'alpha')
    assert calls == ['mod1/(root)']


def test_deleted_unit_entities_dropped(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    _mkfile(actual, 'mod1/a.py')
    _mkfile(actual, 'mod2/b.py')
    _stub(monkeypatch)
    memory.refresh_memory(actual, folder, 'alpha')
    assert any(e['repo'] == 'mod2' for e in memory.load_memory(actual, folder)['entities'])
    import shutil
    shutil.rmtree(os.path.join(actual, 'mod2'))
    mem = memory.refresh_memory(actual, folder, 'alpha')
    assert not any(e['repo'] == 'mod2' for e in mem['entities'])


# ── digest ───────────────────────────────────────────────────

def test_build_digest_structured(monkeypatch, tmp_path):
    Sandbox(monkeypatch, tmp_path)
    mem = {'entities': [
        {'name': 'Engine', 'type': 'module', 'summary': 'core', 'repo': 'svc', 'module': 'engine'},
        {'name': 'Cache', 'type': 'component', 'summary': 'lru', 'repo': 'svc', 'module': 'engine'}],
        'summaries': {'svc/engine': 'the engine module'}, 'relations': []}
    d = memory.build_digest(mem)
    assert '### svc' in d and '**engine**' in d
    assert 'Engine' in d and 'Cache' in d and 'the engine module' in d


def test_refresh_writes_claudemd(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    _mkfile(actual, 'mod1/a.py')
    monkeypatch.setattr('claude_sessions.config.load_settings',
                        lambda: {'memory_to_claudemd': True, 'memory_max_calls': None})
    _stub(monkeypatch)
    memory.refresh_memory(actual, folder, 'alpha')
    md = os.path.join(actual, 'CLAUDE.md')
    assert os.path.isfile(md) and 'CLAUDECTL:MEMORY' in open(md, encoding='utf-8').read()


# ── ask ──────────────────────────────────────────────────────

def test_ask_uses_answer(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    m = memory._empty()
    m['entities'] = [{'id': 'entity:svc:eng:Parser', 'name': 'Parser', 'type': 'component',
                      'summary': 'parses tokens', 'repo': 'svc', 'module': 'eng', 'source_files': []}]
    memory.save_memory(actual, folder, m)
    monkeypatch.setattr(memory, '_answer', lambda ctx, q, cwd: 'ANSWER:' + q)
    assert memory.ask_memory(actual, folder, 'what parses tokens') == 'ANSWER:what parses tokens'
