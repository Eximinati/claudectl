import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions import ui, memory


def test_run_with_progress_silent_skips_renderer(monkeypatch):
    monkeypatch.setattr(memory._tls, 'silent', True, raising=False)

    def boom(*a, **k):
        raise AssertionError('render_frame must not run in silent mode')
    monkeypatch.setattr(ui.render, 'render_frame', boom)

    from claude_sessions import gui_api
    captured = {}
    def fake_run_cancellable(args, **kw):
        captured['args'] = args
        return 'hello'
    monkeypatch.setattr(gui_api, '_run_cancellable', fake_run_cancellable)

    out, cancelled = ui.run_with_progress(['echo', 'hi'], ('A', 'B'), 'label')
    assert out == 'hello' and cancelled is False
    assert captured['args'] == ['echo', 'hi']


def test_run_with_progress_stdin_silent_skips_renderer(monkeypatch):
    monkeypatch.setattr(memory._tls, 'silent', True, raising=False)

    def boom(*a, **k):
        raise AssertionError('render_frame must not run in silent mode')
    monkeypatch.setattr(ui.render, 'render_frame', boom)

    from claude_sessions import gui_api
    captured = {}
    def fake_run_cancellable(args, **kw):
        captured['input'] = kw.get('input_text')
        return 'plan text'
    monkeypatch.setattr(gui_api, '_run_cancellable', fake_run_cancellable)

    out, cancelled = ui.run_with_progress_stdin(['echo'], 'my prompt', ('A', 'B'), 'label')
    assert out == 'plan text' and cancelled is False
    assert captured['input'] == 'my prompt'


if __name__ == '__main__':
    test_run_with_progress_silent_skips_renderer()
    test_run_with_progress_stdin_silent_skips_renderer()
    print('ok')
