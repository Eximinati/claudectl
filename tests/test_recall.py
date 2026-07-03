import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Sandbox

from claude_sessions import recall, memory


def _graph():
    ents = [
        {'name': 'UsageParser', 'type': 'component', 'summary': 'parses plan usage limits from the oauth endpoint',
         'repo': 'app', 'module': 'usage', 'source_files': ['app/usage.py'], 'rank': 12},
        {'name': 'GraphBuilder', 'type': 'component', 'summary': 'builds the architecture dependency graph',
         'repo': 'app', 'module': 'connections', 'source_files': ['app/connections.py'], 'rank': 30},
        {'name': 'MemoryStore', 'type': 'service', 'summary': 'persists the semantic knowledge graph',
         'repo': 'app', 'module': 'memory', 'source_files': ['app/memory.py'], 'rank': 8},
        {'name': 'ThemeConfig', 'type': 'model', 'summary': 'color palettes for the TUI',
         'repo': 'app', 'module': 'config', 'source_files': ['app/config.py'], 'rank': 2},
        {'name': 'FixTimeout', 'type': 'lesson', 'status': 'approved', 'summary': 'usage fetch needs retry-after backoff',
         'repo': '', 'module': '(project)', 'source_files': [], 'rank': 0},
        {'name': 'PendingL', 'type': 'lesson', 'status': 'pending', 'summary': 'usage related pending lesson',
         'repo': '', 'module': '(project)', 'source_files': [], 'rank': 0},
    ]
    rels = [{'source': 'UsageParser', 'target': 'ThemeConfig', 'rel': 'uses', 'unit': 'app/usage'}]
    edges = [{'source': 'app/usage', 'target': 'app/memory', 'weight': 3}]
    return {'schema_version': 2, 'entities': ents, 'relations': rels,
            'summaries': {'app/usage': 'usage tracking'}, 'provenance': {},
            'module_edges': edges, 'lessons_scanned': {}, 'session_counter': 0}


def test_scoring_order_and_lesson_boost(monkeypatch, tmp_path):
    mem = _graph()
    idx = recall.build_index(mem)
    scored = recall.score_entities(mem, idx, 'how does usage limit parsing work')
    names = [e['name'] for _s, e in scored]
    assert names[0] in ('UsageParser', 'FixTimeout')
    assert 'UsageParser' in names and 'FixTimeout' in names
    assert 'PendingL' not in names                     # pending never injectable
    assert 'GraphBuilder' not in names                 # zero-overlap dropped


def test_relation_and_module_edge_expansion(monkeypatch, tmp_path):
    mem = _graph()
    idx = recall.build_index(mem)
    seeds = recall.score_entities(mem, idx, 'usage limits')
    extra = recall.expand_relations(mem, idx, seeds, hops=1)
    got = {e['name'] for _s, e in extra}
    assert 'ThemeConfig' in got                        # via entity relation
    assert 'MemoryStore' in got                        # via module edge


def test_budget_cut(monkeypatch, tmp_path):
    mem = _graph()
    idx = recall.build_index(mem)
    scored = recall.score_entities(mem, idx, 'usage parsing graph memory theme')
    text, toks = recall.render_context(scored, mem, budget_tokens=40)
    assert toks <= 40 and text.startswith('PROJECT MEMORY')


def test_retrieve_end_to_end(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    memory.save_memory(actual, folder, _graph())
    r = recall.retrieve(actual, folder, 'usage limit parsing', budget_tokens=600)
    assert not r['empty'] and 'UsageParser' in r['text']
    assert r['tokens'] <= 600
    # deterministic
    r2 = recall.retrieve(actual, folder, 'usage limit parsing', budget_tokens=600)
    assert r2['text'] == r['text']


def test_retrieve_empty_cases(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    assert recall.retrieve(actual, folder, 'anything')['empty']      # no graph
    memory.save_memory(actual, folder, _graph())
    assert recall.retrieve(actual, folder, '')['empty']              # no query
    assert recall.retrieve(actual, folder, 'zzz qqq xxyzzy')['empty']  # no match


def test_retrieve_fast_on_large_graph(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    mem = _graph()
    mem['entities'] += [
        {'name': f'Entity{i}', 'type': 'component', 'summary': f'component number {i} doing work',
         'repo': 'app', 'module': f'mod{i % 20}', 'source_files': [f'app/m{i}.py'], 'rank': i % 9}
        for i in range(500)]
    memory.save_memory(actual, folder, mem)
    t0 = time.perf_counter()
    recall.retrieve(actual, folder, 'component work entity', budget_tokens=600)
    assert time.perf_counter() - t0 < 0.5


def test_recall_imports_no_ui():
    # fresh interpreter — popping ui from sys.modules here would corrupt other tests
    import subprocess
    code = ("import sys; sys.path.insert(0, r'%s'); "
            "import claude_sessions.recall; "
            "sys.exit(1 if 'claude_sessions.ui' in sys.modules else 0)"
            % os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert subprocess.run([sys.executable, '-c', code]).returncode == 0


def test_memory_status_line(monkeypatch, tmp_path):
    sb = Sandbox(monkeypatch, tmp_path)
    actual, enc, folder, _ = sb.add_project('alpha')
    memory.save_memory(actual, folder, _graph())
    s = {'memory_prompt_hook': True, 'memory_budget': 600}
    line = recall.memory_status_line(actual, folder, s)
    assert 'tok always' in line and 'hook <=600/prompt' in line
