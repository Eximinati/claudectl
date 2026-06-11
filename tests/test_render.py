import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_sessions.render import strip_ansi, disp_width, trunc, pad, fit, cols
from claude_sessions import render


def test_strip_ansi():
    assert strip_ansi('\x1b[96mhello\x1b[0m') == 'hello'
    assert strip_ansi('plain') == 'plain'
    assert strip_ansi('\x1b[38;5;117mx\x1b[48;2;1;2;3my') == 'xy'


def test_disp_width_ascii():
    assert disp_width('hello') == 5


def test_disp_width_ignores_ansi():
    assert disp_width('\x1b[96mhello\x1b[0m') == 5


def test_disp_width_wide_chars():
    assert disp_width('中') == 2
    assert disp_width('日本語') == 6
    assert disp_width('a中b') == 4


def test_disp_width_ambiguous_narrow():
    # ★ ☆ are East Asian 'A' (ambiguous) — treated as 1 col (Windows Terminal default)
    assert disp_width('★') == 1


def test_trunc_no_cut():
    assert trunc('short', 10) == 'short'


def test_trunc_cuts_with_ellipsis():
    out = trunc('abcdefghij', 5)
    assert out.endswith('…')
    assert disp_width(out) <= 5


def test_trunc_ansi_safe():
    s = '\x1b[96mabcdefghij\x1b[0m'
    out = trunc(s, 5)
    assert disp_width(out) <= 5
    assert out.endswith('\x1b[0m')          # reset appended
    assert '\x1b[96m' in out                # code preserved


def test_trunc_wide_chars():
    out = trunc('中中中中', 5)
    assert disp_width(out) <= 5


def test_pad_left_right():
    assert pad('ab', 5) == 'ab   '
    assert pad('ab', 5, align='right') == '   ab'
    assert pad('abcdef', 3) == 'abcdef'   # never truncates


def test_pad_accounts_for_ansi():
    s = '\x1b[96mab\x1b[0m'
    assert disp_width(pad(s, 5)) == 5


def test_fit_exact_width():
    assert disp_width(fit('hello world this is long', 10)) == 10
    assert disp_width(fit('hi', 10)) == 10


def test_cols_total_width(monkeypatch):
    monkeypatch.setattr(render, 'content_width', lambda: 60)
    line = cols(['a', 'b', 'c'], [5, 7, None])
    assert disp_width(line) <= 60
    assert disp_width(line) >= 50


def test_render_frame_no_console_fallback(capsys):
    # No tty → fallback path; must not raise
    render.invalidate()
    render.render_frame(['line one', 'line two'])


def test_screen_init_noop_without_tty():
    render.screen_init()
    assert render.screen_active() is False   # no tty in test harness
    render.screen_restore()                  # idempotent, no raise
