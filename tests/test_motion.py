"""The motion layer: the `motion` setting, its migration, and the gates.

Structural invariants that keep motion off the QtWebEngine flicker path (one rAF
chain, parking when idle, compositor-only properties) live in
tests/test_gui_flicker.py. This file covers the setting itself and the rules that
decide when an effect is allowed to run at all.
"""
import re

import pytest

from claude_sessions.gui_html import PAGE

LEVELS = ('full', 'subtle', 'off')

_CSS = re.sub(r'/\*.*?\*/', '',
              PAGE[PAGE.index('<style>'):PAGE.index('</style>')], flags=re.S)


# ── the setting ───────────────────────────────────────────────

@pytest.mark.parametrize('saved,want', [
    # explicit new-style values pass straight through
    ({'motion': 'full'}, 'full'),
    ({'motion': 'subtle'}, 'subtle'),
    ({'motion': 'off'}, 'off'),
    # a garbage value falls back rather than disabling motion outright
    ({'motion': 'wat'}, 'full'),
    # nothing saved at all
    ({}, 'full'),
    # ── migration from the four old knobs ──
    # someone who had turned the wallpaper off must NOT come back to motion on
    ({'theme_motion': 'off'}, 'off'),
    ({'theme_motion_scope': 'off'}, 'off'),
    ({'theme_motion': 'rain', 'theme_motion_scope': 'off'}, 'off'),
    # 'panels' meant "the band only, no gauges in the chrome" — the nearest
    # equivalent now is informational motion without the flourishes
    ({'theme_motion_scope': 'panels'}, 'subtle'),
    # a named renderer with the default scope was motion fully on
    ({'theme_motion': 'rain', 'theme_motion_scope': 'everywhere'}, 'full'),
    ({'theme_motion': ''}, 'full'),
    # the new key wins over any legacy leftovers
    ({'motion': 'full', 'theme_motion': 'off'}, 'full'),
])
def test_motion_level_migration(saved, want):
    from claude_sessions.gui import _motion_level
    assert _motion_level(saved) == want


def test_motion_level_is_in_the_state_payload(monkeypatch, tmp_path):
    """The GUI reads its motion level from /api/state at boot."""
    from claude_sessions import gui
    assert "'motion':" in open(gui.__file__, encoding='utf-8').read()
    assert "MO.set(ST.motion||'full')" in PAGE


def test_only_the_new_key_is_persisted():
    """The four old keys are read for back-compat but never written again, so they
    age out of settings.json instead of lingering as dead config forever."""
    from claude_sessions.gui import _SETTING_KEYS
    assert 'motion' in _SETTING_KEYS
    for dead in ('theme_motion_scope', 'theme_motion_bg', 'theme_motion_intensity'):
        assert dead not in _SETTING_KEYS, f'{dead} is still being written'


# ── the gates ─────────────────────────────────────────────────

def test_every_level_has_a_gate():
    """`off` must stop everything and `subtle` must drop the decorative effects.
    Without the html-level classes each effect would have to check MO.level in JS,
    and the CSS-only ones (spotlight, beam) could not be gated at all."""
    assert "r.classList.toggle('mo-off', this.level === 'off')" in PAGE
    assert "r.classList.toggle('mo-subtle', this.level === 'subtle')" in PAGE
    # off kills animation and transition globally
    assert 'html.mo-off *,html.mo-off *::before,html.mo-off *::after{' in _CSS
    # subtle drops the purely decorative pointer spotlight
    assert 'html.mo-subtle .spot::before' in _CSS


def test_decorative_effects_are_full_only():
    """Stagger, spotlight and the travelling border carry no information — they
    must not run at `subtle`, which is the level for "show me what changed and
    nothing else"."""
    arrive = PAGE[PAGE.index('  arrive(root, sel) {'):]
    arrive = arrive[:arrive.index('\n  },')]
    assert 'if (!this.full) return;' in arrive
    spot = PAGE[PAGE.index('  spot(root) {'):]
    spot = spot[:spot.index('\n  },')]
    assert 'if (!this.full) return;' in spot
    assert "r.classList.toggle('mo-beam', this.full && MO_HAS_PROP)" in PAGE


def test_informational_motion_survives_subtle():
    """Value tweens, meter fills and the page change tell you something happened,
    so they are gated on `on` (not-off), not on `full`."""
    count = PAGE[PAGE.index('  count(el, to, fmt) {'):]
    count = count[:count.index('\n  },')]
    assert 'if (!this.on ||' in count and 'this.full' not in count
    page = PAGE[PAGE.index('  page(el) {'):]
    page = page[:page.index('\n  },')]
    assert 'if (!this.on ||' in page


# ── number tweens ─────────────────────────────────────────────

def test_number_tweens_are_idempotent():
    """A poll re-reporting the same value must cost nothing AND must not restart
    the tween — the dashboard polls every 10s and most numbers do not move."""
    count = PAGE[PAGE.index('  count(el, to, fmt) {'):]
    count = count[:count.index('\n  },')]
    assert 'if (from === to) return;' in count
    # a second call while one is in flight retargets rather than racing
    assert 'if (el.__mvj) {' in count


def test_number_tweens_use_tabular_figures():
    """A proportional-figure counter changes width on every frame, which reflows
    the row it sits in ~30 times a second."""
    # the gauge readouts and the KPI numbers are the ones that tween. findall,
    # not search: a narrow-window @media block also declares .kpi .kv2 (font-size
    # only) and happens to appear earlier in the sheet.
    for sel in (r'\.iread b\{', r'\.kpi \.kv2\{'):
        bodies = re.findall(sel + r'([^}]*)\}', _CSS)
        assert bodies, f'no rule for {sel}'
        assert any('tabular-nums' in b for b in bodies), (sel, bodies)
    assert any('var(--mono)' in b for b in re.findall(r'\.iread b\{([^}]*)\}', _CSS))


def test_direction_is_shown_with_colour_not_movement():
    """A number that both moves and travels is unreadable; the delta direction is
    a brief tint on the settled digits instead."""
    assert '.mo-up{color:var(--ok)}' in _CSS
    assert '.mo-dn{color:var(--dim)}' in _CSS
    for prop in ('transform', 'translate'):
        block = _CSS[_CSS.index('.mo-up,.mo-dn{'):]
        assert prop not in block[:block.index('}')]


# ── in-place feedback ─────────────────────────────────────────

def test_button_feedback_restores_on_throw():
    """A failed fetch must not leave a button stuck as a spinner forever."""
    press = PAGE[PAGE.index('  press(btn, run) {'):]
    press = press[:press.index('\n  },')]
    assert 'try { r = run(); } catch (e) { done(); throw e; }' in press
    assert 'e => { done(); throw e; }' in press
    # the width is pinned so swapping the label for a spinner cannot reflow the row
    assert "btn.style.minWidth = w + 'px';" in press


def test_skeletons_on_first_paint():
    """A card that renders empty and fills half a second later reads as broken."""
    assert 'skel(n, h)' in PAGE
    for host in ('dashProjects', 'dashRecent', 'dashChart'):
        assert f'id="{host}">${{MO.skel(' in PAGE, host


# ── instruments ───────────────────────────────────────────────

def test_instrument_readouts_are_dom_not_canvas():
    """Canvas text ignores the palette, needs font loading, cannot be selected and
    re-rasterises every frame. Every readout is a real element."""
    inst = PAGE[PAGE.index('const IKIND = {'):PAGE.index('window.INST = INST;')]
    for dead in ('fillText', 'measureText', "c.font"):
        assert dead not in inst, f'{dead} in an instrument renderer'


def test_only_the_equalizer_runs_continuously_among_instruments():
    """Every other gauge settles and parks. `eq` is the exception because "work is
    happening right now" is itself a continuous fact — and it goes flat, and stops,
    the moment there is nothing to report.

    The background stage is the second and last long-running job in the app, but
    it is not an instrument: it is one surface behind everything rather than a
    gauge next to a number, and it has its own switch. Its pause conditions are
    asserted in tests/test_stage.py."""
    inst = PAGE[PAGE.index('const IKIND = {'):PAGE.index('window.INST = INST;')]
    kinds = set(re.findall(r'\n  (\w+)\(c, w, h, D, S, P, dt\) \{', inst))
    assert {'ring', 'dial', 'spark', 'eq', 'flow'} <= kinds, kinds
    eq = inst[inst.index('eq(c, w, h, D, S, P, dt) {'):]
    eq = eq[:eq.index('\n  },')]
    # liveness comes from running jobs ONLY. Driving it off throughput (`v`) made
    # the strip animate forever any time a token had been spent today — caught by
    # tools/smoke_gui.py asserting the loop parks, not by any string match.
    assert 'const live = beats > 0;' in eq
    assert 'return moving || (live' in eq
    # ring/dial/spark return only whether they are still travelling
    for kind in ('ring', 'dial'):
        body = inst[inst.index(f'{kind}(c, w, h, D, S, P, dt) {{'):]
        body = body[:body.index('\n  },')]
        assert body.rstrip().endswith('return moving;'), kind


def test_forced_redraws_do_not_animate():
    """dt === 0 means settle immediately. A resize or theme change must not look
    like a data change — the gauge should already be at its value."""
    assert 'if (!dt) { S[name] = target; return { v: target, moving: false }; }' in PAGE
