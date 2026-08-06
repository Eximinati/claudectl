"""Theme palettes: shape, contrast, ANSI derivation, and motion parity.

The palettes are hand-authored data, so the only thing standing between a typo
and an unreadable UI is this file. Contrast is checked against WCAG relative
luminance — the same maths a browser devtools contrast panel runs.
"""
import re

import pytest

from claude_sessions import config as config_mod
from claude_sessions import themes as themes_mod
from claude_sessions.themes import PALETTES, COLOR_KEYS, ansi_palette, hex_to_x256

HEX = re.compile(r'^#[0-9a-f]{6}$')

# the 17 names that shipped before the overhaul — a saved settings.json naming
# any of them must keep resolving, or a user silently loses their theme
LEGACY = ['default', 'ocean', 'forest', 'mono', 'mocha', 'tokyo', 'dracula',
          'nord', 'gruvbox', 'rose', 'catppuccin-latte', 'kanagawa',
          'everforest', 'ayu', 'monokai-pro', 'solarized', 'ember']


def _lum(hexc):
    def chan(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    n = int(hexc.lstrip('#'), 16)
    r, g, b = (n >> 16) & 255, (n >> 8) & 255, n & 255
    return .2126 * chan(r) + .7152 * chan(g) + .0722 * chan(b)


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + .05) / (lb + .05)


@pytest.mark.parametrize('name', list(PALETTES))
def test_palette_shape(name):
    pal = PALETTES[name]
    for key in COLOR_KEYS:
        assert HEX.match(pal[key]), (name, key, pal.get(key))
    assert pal['label'] and pal['family']
    assert pal['mode'] in ('dark', 'light')
    assert pal['motion']


@pytest.mark.parametrize('name', list(PALETTES))
def test_palette_contrast(name):
    """Body text must clear 4.5:1, secondary text and state colours 3:1."""
    p = PALETTES[name]
    for fg, bg, floor in (('txt', 'bg', 4.5), ('txt', 'panel', 4.5),
                          ('dim', 'panel', 3.0), ('dim2', 'bg', 2.5),
                          ('accent', 'bg', 3.0), ('accent2', 'bg', 3.0),
                          ('ok', 'panel', 3.0), ('warn', 'panel', 3.0),
                          ('err', 'panel', 3.0)):
        got = _ratio(p[fg], p[bg])
        assert got >= floor, f'{name}: {fg} on {bg} is {got:.2f}, need {floor}'


def test_hue_families_and_light_themes():
    fams = {p['family'] for p in PALETTES.values()}
    for want in ('cyan', 'blue', 'green', 'amber', 'yellow', 'orange', 'red',
                 'magenta', 'purple', 'violet', 'rose', 'neutral', 'light'):
        assert want in fams, f'no theme in the {want} family'
    assert sum(1 for p in PALETTES.values() if p['mode'] == 'light') >= 4


def test_legacy_theme_names_survive():
    for name in LEGACY:
        assert name in PALETTES, f'{name} would break saved settings'
        assert name in config_mod.THEMES


PERSONAS = ('crisp', 'smooth', 'lush')


def test_every_theme_declares_a_known_personality():
    """`motion` is a motion personality, not a per-theme background animation.

    It used to name one of 26 generative canvas renderers, and this test used to
    require all 26 to be distinct — which is what forced a new animated wallpaper
    into existence for every palette added. Now it maps to the
    --mo-lift/--mo-glow/--mo-beam/--t-spring vars, so palettes share personalities
    freely and only the vocabulary is closed."""
    for name, pal in PALETTES.items():
        assert pal['motion'] in PERSONAS, f'{name} has unknown personality {pal["motion"]}'
    # all three must actually be used, or the ladder has collapsed to one setting
    used = {p['motion'] for p in PALETTES.values()}
    assert used == set(PERSONAS), f'unused personality: {set(PERSONAS) - used}'


def test_personalities_are_implemented_in_the_js():
    """Every personality a palette can name must have CSS values behind it, or
    applyTheme() silently falls back and the palette's character is a no-op."""
    from claude_sessions.gui_html import PAGE
    block = PAGE[PAGE.index('const MOTION_PERSONA={'):]
    block = block[:block.index('};')]
    for k in PERSONAS:
        assert f'{k}:' in block, f'{k} missing from MOTION_PERSONA'
        # each must set all four vars or a theme switch leaves a stale value behind
    for var in ('lift:', 'glow:', 'beam:', 'spring:'):
        assert block.count(var) == len(PERSONAS), f'{var} not set for every personality'


def test_reference_palettes_are_present():
    """The three palettes derived from the reference dashboards. Named here so a
    rename has to be deliberate — a saved settings.json can point at them."""
    for name in ('neon', 'aurora', 'noir'):
        assert name in PALETTES, name
        assert PALETTES[name]['mode'] == 'dark'


def test_the_background_is_one_stage_not_thirty_canvases():
    """There IS an animated background again — but the thing that made the old
    one wrong was never that it moved.

    It was that it was 26 generative renderers mounted into ~30 places: a band
    above every page plus a micro-canvas inside every sidebar row, nav item,
    header chip and quota meter, each looping regardless of whether anything had
    happened. Motion was smeared through the content.

    What replaced it is ONE surface behind everything. This test guards the
    distinction rather than the absence: exactly one stage canvas, no per-row
    renderers, and none of the old mount points back."""
    from claude_sessions.gui_html import PAGE
    assert PAGE.count('<canvas id="stage"') == 1, 'the stage is exactly one canvas'
    assert 'z-index:-2' in PAGE, 'the stage must sit behind the whole app'
    for dead in ('const MOTIONS=', 'const LIVE=', 'function liveLoop',
                 'function renderMotion(', 'function microDraw(', 'liveMicro(',
                 'LIVE_OVERRIDE', 'LIVE_GLOBAL', 'data-live=', 'id="amb"',
                 'class="live', 'drawMotionPicker', 'moPreview'):
        assert dead not in PAGE, f'{dead} is back'
    # instruments.js is still the only thing allowed to make a canvas per widget,
    # and only where a number is being displayed
    assert "createElement('canvas')" not in PAGE.split('const STAGE = {')[1], \
        'the stage must not spawn canvases of its own'


def test_instruments_are_fed_by_the_page_that_owns_the_data():
    """Every gauge must be pushed by a renderer that already fetched the numbers.
    An unfed instrument renders an empty frame forever — and the rule that no
    instrument fetches for itself is what keeps them free."""
    import re
    from claude_sessions.gui_html import PAGE
    emitted = set(re.findall(r"INST\.html\('\w+','([\w:]+)'", PAGE))
    fed = set(re.findall(r"INST\.set\('([\w:]+)'", PAGE))
    # keyed instruments (acct:<name>, one per account) are built dynamically
    emitted = {k for k in emitted if not k.endswith(":'+a.name")}
    missing = {k for k in emitted if k not in fed and ':' not in k}
    assert not missing, f'instruments with no INST.set: {missing}'
    assert 'quota' in fed and 'burn' in fed and 'mcp' in fed


def test_ansi_palette_shape():
    for name, pal in PALETTES.items():
        out = ansi_palette(pal)
        for key in ('C_ACCENT', 'C_SEL_BG', 'C_HEADER_BG', 'C_OK', 'C_WARN',
                    'C_TITLE', 'C_SRCH', 'C_STAR'):
            assert out[key].startswith('\033['), (name, key)
        assert config_mod.THEMES[name] == out


def test_x256_quantization_round_trips():
    """hex_to_x256 must be idempotent through the cube it quantizes to, or the
    TUI palette drifts a little further from the GUI on every regeneration."""
    for pal in PALETTES.values():
        for key in COLOR_KEYS:
            idx = hex_to_x256(pal[key])
            assert 16 <= idx <= 255, 'never land on the 0-15 terminal-config range'
            assert hex_to_x256(_x256_to_hex(idx)) == idx


def _x256_to_hex(n):
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        r, g, b = steps[n // 36], steps[(n // 6) % 6], steps[n % 6]
    else:
        r = g = b = 8 + (n - 232) * 10
    return f'#{r:02x}{g:02x}{b:02x}'


def test_header_bar_keeps_its_hue():
    """Past ~35% toward the background an accent desaturates enough that the
    nearest ANSI neighbour is the gray ramp — the header would lose its tint."""
    def is_gray(i):
        if i >= 232:
            return True
        n = i - 16
        return (n // 36) == ((n // 6) % 6) == (n % 6)

    grays = [n for n, p in PALETTES.items()
             if p['family'] != 'neutral' and p['mode'] == 'dark'
             and is_gray(hex_to_x256(themes_mod._mix(p['accent'], p['bg'], .30)))]
    assert not grays, f'header bar loses its hue for {grays}'
