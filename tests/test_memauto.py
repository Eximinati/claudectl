"""Auto-memory updates everything, and overwrites nothing it did not write.

    "se abilitato auto memory, tutte le cose riguardanti memoria devono essere
     aggiornate automaticamente, tenendo in mente di non sovrascrivere regole
     importanti che non sono state auto generate da claudectl"

Two halves, and the second is the load-bearing one. Silent automation that
rewrites a file is only acceptable if the boundary of what it may rewrite is
exact and tested — so the tests below seed hand-written content in every place
claudectl writes and assert it comes back byte-identical.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions import memory, claude_md, memrules, lessons
from claude_sessions.config import _MEMORY_START, _MEMORY_END


HAND_WRITTEN = """# My project

This paragraph is mine. Nobody generated it and nothing may rewrite it.

## House rules
- always run the linter
- never touch vendor/

<!-- CLAUDECTL:MEMORY:START -->
## Project memory (claudectl — auto-maintained)

- stale content that SHOULD be replaced
<!-- CLAUDECTL:MEMORY:END -->

## Notes after the block
Also mine. Also untouchable.
"""


def _mem(entities=()):
    return {'entities': list(entities), 'relations': [], 'summaries': {},
            'provenance': {}, 'module_edges': [], 'lessons_scanned': {},
            'session_counter': 0}


# ── the boundary ──────────────────────────────────────────────

def test_the_claudemd_block_is_the_only_thing_rewritten(tmp_path):
    """Prose above it, prose below it, and the user's own headings all survive.
    Only the region between the sentinels changes."""
    p = tmp_path / 'proj'
    p.mkdir()
    md = p / 'CLAUDE.md'
    md.write_text(HAND_WRITTEN, encoding='utf-8')

    ok, old, new = claude_md.write_memory_block(str(p), '- fresh digest line')
    assert ok
    assert 'stale content' not in new
    assert '- fresh digest line' in new
    # everything outside the sentinels is byte-identical
    assert new[:new.index(_MEMORY_START)] == old[:old.index(_MEMORY_START)]
    assert (new[new.index(_MEMORY_END):].replace(_MEMORY_END, '', 1)
            == old[old.index(_MEMORY_END):].replace(_MEMORY_END, '', 1))
    for line in ('This paragraph is mine.', '- always run the linter',
                 '- never touch vendor/', 'Also mine. Also untouchable.'):
        assert line in new, line


def test_rewriting_the_block_is_idempotent(tmp_path):
    """Same digest in, same bytes out.

    It was not: the seam between the closing sentinel and the text after it was
    concatenated rather than normalised, so every rewrite inserted one more
    blank line. Harmless when a human triggered it occasionally; a slow leak now
    that auto_cycle runs unattended on a timer."""
    p = tmp_path / 'proj'
    p.mkdir()
    md = p / 'CLAUDE.md'
    md.write_text(HAND_WRITTEN, encoding='utf-8')

    claude_md.write_memory_block(str(p), '- digest')
    once = md.read_text(encoding='utf-8')
    for _ in range(5):
        claude_md.write_memory_block(str(p), '- digest')
    assert md.read_text(encoding='utf-8') == once, 'the file grows on every write'
    assert '\n' * 3 not in once, 'blank lines accumulated'


def test_a_hand_written_rules_file_is_never_touched(tmp_path):
    """`.claude/rules/` holds both. claudectl owns the `claudectl-mem-` prefix
    and must treat everything else in that directory as someone's work."""
    p = tmp_path / 'proj'
    rules = p / '.claude' / 'rules'
    rules.mkdir(parents=True)
    mine = rules / 'our-conventions.md'
    mine.write_text('# ours\nnever delete me\n', encoding='utf-8')
    # a stale generated one, which SHOULD be pruned
    stale = rules / 'claudectl-mem-gone.md'
    stale.write_text('# old unit\n', encoding='utf-8')
    before = mine.read_bytes()

    memrules.sync_rules(str(p), str(tmp_path / 'folder'), _mem())

    assert mine.read_bytes() == before, 'a hand-written rule was modified'
    assert mine.is_file()
    assert not stale.exists(), 'a stale generated rule was not pruned'


def test_decay_never_evicts_a_pinned_lesson(tmp_path):
    """Pinning is the user saying "keep this". Ageing it out anyway would make
    the pin a lie, and the whole cycle unsafe to run unattended."""
    mem = _mem([
        {'type': 'lesson', 'name': 'pinned one', 'status': 'pinned', 'last_used': 0},
        {'type': 'lesson', 'name': 'approved old', 'status': 'approved', 'last_used': 0},
        {'type': 'component', 'name': 'not a lesson', 'last_used': 0},
    ])
    mem['session_counter'] = 500
    evicted = memrules and lessons.apply_decay(mem, {'memory_lessons_ttl': 30})
    names = {e['name'] for e in mem['entities']}
    assert 'pinned one' in names, 'a pinned lesson was evicted'
    assert 'not a lesson' in names, 'decay hit a non-lesson entity'
    assert 'approved old' not in names, 'nothing aged out at all'
    assert evicted == 1


# ── the cycle actually covers everything ──────────────────────

def test_auto_cycle_mines_lessons_not_just_the_graph(tmp_path, monkeypatch):
    """The gap this exists to close: refresh_memory alone left lessons frozen."""
    calls = []
    monkeypatch.setattr(memory, 'refresh_memory',
                        lambda *a, **k: calls.append('graph') or _mem())
    monkeypatch.setattr(memory, 'load_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'save_memory', lambda *a, **k: None)
    monkeypatch.setattr(lessons, 'pending_sids', lambda *a, **k: ['s1', 's2'])
    monkeypatch.setattr(lessons, 'scan_sessions',
                        lambda *a, **k: calls.append('lessons') or (2, 2))
    monkeypatch.setattr(memory, 'sync_to_claudemd',
                        lambda *a, **k: calls.append('claudemd'))
    monkeypatch.setattr(memrules, 'sync_rules', lambda *a, **k: calls.append('rules'))

    out = memory.auto_cycle(str(tmp_path), str(tmp_path), 'proj')

    assert 'graph' in calls, 'the graph was not refreshed'
    assert 'lessons' in calls, 'lessons were not mined — the original bug'
    assert out['lessons'] == 2
    # the digest COUNTS lessons, so it has to be rewritten after they land
    assert calls.index('claudemd') > calls.index('lessons'), calls
    assert 'rules' in calls


def test_lessons_off_is_honoured(tmp_path, monkeypatch):
    """'off' is a real answer, not a default to be overridden by automation."""
    from claude_sessions import config as cfg
    calls = []
    monkeypatch.setattr(cfg, 'load_settings',
                        lambda: dict(cfg._DEFAULT_SETTINGS, memory_lessons='off'))
    monkeypatch.setattr(memory, 'refresh_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'load_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'save_memory', lambda *a, **k: None)
    monkeypatch.setattr(lessons, 'scan_sessions',
                        lambda *a, **k: calls.append('lessons') or (0, 0))

    memory.auto_cycle(str(tmp_path), str(tmp_path), 'proj')
    assert calls == [], 'mined lessons despite memory_lessons=off'


def test_a_failing_lesson_scan_does_not_lose_the_graph_refresh(tmp_path, monkeypatch):
    """Unattended work must degrade, not roll back. A Claude call that fails
    mid-scan cannot cost the graph update that already succeeded."""
    monkeypatch.setattr(memory, 'refresh_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'load_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'save_memory', lambda *a, **k: None)
    monkeypatch.setattr(lessons, 'pending_sids', lambda *a, **k: ['s1'])

    def boom(*a, **k):
        raise RuntimeError('claude call failed')
    monkeypatch.setattr(lessons, 'scan_sessions', boom)

    out = memory.auto_cycle(str(tmp_path), str(tmp_path), 'proj')
    assert out['graph'] is True
    assert out['lessons'] == 0


def test_both_auto_paths_use_the_one_cycle():
    """Two entry points refresh memory automatically — the GUI scheduler and
    the detached worker. If either keeps calling refresh_memory directly, that
    half of the product silently stops learning again."""
    import inspect
    from claude_sessions import gui_api, main as main_mod
    g = inspect.getsource(gui_api._refresh_project)
    assert 'auto_cycle' in g and 'refresh_memory(' not in g, g
    m = inspect.getsource(main_mod)
    worker = m[m.index('def _bg_scan_worker') if 'def _bg_scan_worker' in m else 0:]
    assert 'auto_cycle' in worker


def test_the_cycle_stamps_when_it_last_ran(tmp_path, monkeypatch):
    """Silent automation still has to be legible."""
    saved = {}
    monkeypatch.setattr(memory, 'refresh_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'load_memory', lambda *a, **k: _mem())
    monkeypatch.setattr(memory, 'save_memory',
                        lambda p, f, mem: saved.update(mem))
    monkeypatch.setattr(lessons, 'pending_sids', lambda *a, **k: [])

    memory.auto_cycle(str(tmp_path), str(tmp_path), 'proj')
    assert saved.get('auto_updated'), saved
    assert 'auto_last' in saved
