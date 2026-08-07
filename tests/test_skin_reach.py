"""Does a look actually reach the whole app, or only the cards?

This is the test this round exists for. The previous roster changed corner
radius, border weight, one surface texture and a heading font — about 20 of
~130 component selectors — so every theme still read as the same application
in a different hue, and the verdict was blunt:

    "Glass, Mecha e Sakura da buttare."
    "devono proprio cambiare la vista della gui, ma proprio tutta tutta,
     ogni piccola cosa"

The fix was not more per-skin CSS (7 x 130 rules is unmaintainable); it was a
token vocabulary that the components read, so a look writes ~30 tokens and the
whole interface follows. What keeps that true is this file: every component
family must be reached by a token or by a look-scoped rule, so the NEXT look
cannot quietly go back to being chrome-deep.
"""
import re

from claude_sessions.gui_html import PAGE
from claude_sessions.themes import SKINS, SKIN_KEYS, WORLDS

_CSS = re.sub(r'/\*.*?\*/', '',
              PAGE[PAGE.index('<style>'):PAGE.index('</style>')], flags=re.S)

#: family -> a selector that must be reached, and the token that reaches it.
#: Not exhaustive by design — one representative per family, because a family
#: that has any token at all was thought about.
FAMILIES = {
    'buttons':     ('.btn', '--sk-btn-r'),
    'segmented':   ('.seg', '--sk-btn-r'),
    'chips/tags':  ('.chip,.tag,.hchip', '--sk-pill-r'),
    'inputs':      ('.fld input', '--sk-in-r'),
    'cards':       ('.card', '--sk-r'),
    'list rows':   ('.sess,.proj', '--sk-row-r'),
    'tables':      ('.tbl td', '--sk-cell-pad'),
    'nav':         ('.nav .it', '--sk-nav-r'),
    'icons':       ('.nav .it .ic', '--sk-icon-plate'),
    'meters':      ('.bar', '--sk-bar-r'),
    'spinner':     ('.spin', '--sk-spin-r'),
    'scrollbars':  ('::-webkit-scrollbar', '--sk-sb-w'),
    'selection':   ('::selection', '--sk-sel-bg'),
    'focus':       (':focus-visible', '--sk-focus'),
    'drawer':      ('.drawer', '--sk-drawer-r'),
}


def test_every_component_family_is_token_driven():
    """Each family reads a token, so a look restyles it without touching CSS."""
    for family, (sel, token) in FAMILIES.items():
        first = sel.split(',')[0]
        assert first in _CSS, f'{family}: {first} not styled at all'
        assert token in _CSS, f'{family}: {token} never used — look cannot reach it'


def test_a_look_that_forgets_a_token_is_not_silently_half_applied():
    """A missing token falls back to the default and the look quietly resembles
    another one. Every skin declares every key."""
    for name, sk in SKINS.items():
        missing = [k for k in SKIN_KEYS if k not in sk]
        assert not missing, f'{name} is missing {missing}'


def test_each_world_restyles_far_more_than_a_card():
    """A world is supposed to change everything. Counting the selectors each one
    actually touches is the crudest possible proxy, and it is the one that would
    have caught the previous roster: Sakura reached four rules."""
    for name in WORLDS:
        rules = re.findall(r'html\.skin-%s\b[^{]*\{' % re.escape(name), _CSS)
        assert len(rules) >= 8, f'{name} touches only {len(rules)} rules — chrome-deep'
        # …and it must declare a block of tokens, not just paint a few surfaces
        block = re.search(r'html\.skin-%s\{([^}]*)\}' % re.escape(name), _CSS)
        assert block, f'{name} declares no tokens'
        assert block.group(1).count('--sk-') >= 8, \
            f'{name} sets only {block.group(1).count("--sk-")} tokens'


def test_every_world_has_the_parts_a_token_cannot_express():
    """Icons, overlay, hover, cursor: the things that make it a world rather
    than a skin. Each must exist on both sides."""
    for name, w in WORLDS.items():
        assert f"'{w['icons']}':{{" in PAGE.replace(' ', '') \
            or f'{w["icons"]}:{{' in PAGE.replace(' ', ''), f'{name}: no icon set'
        assert f'.ov-{w["overlay"]}' in _CSS, f'{name}: no overlay'
        assert f'html.world-{name}' in _CSS or f'.skin-{w["skin"]} .spot.hv' in _CSS, \
            f'{name}: no world-scoped rule'


def test_world_hover_is_scoped_and_costs_one_class():
    """Per-world hover rides the existing delegated listener — a class toggle,
    not a new handler per card."""
    assert "_mark(el)" in PAGE
    assert "el.classList.add('hv')" in PAGE
    assert PAGE.count("addEventListener('pointermove'") == 1
    for skin in ('anime', 'cyber', 'deck', 'graph'):
        assert f'html.skin-{skin} .spot.hv' in _CSS, skin


def test_overlays_cannot_swallow_clicks_or_survive_motion_off():
    """One element, above the app, inert, and killable.

    An overlay DOES drift — a world whose scanlines are frozen is not a world,
    which is what the first cut got wrong by treating brightness and motion as
    one knob. What has to stay true is everything else: exactly one element, it
    cannot take a click, `motion:off` removes it entirely, and its animation is
    compositor-only (the global keyframes audit in test_gui_flicker.py already
    rejects any property outside transform/opacity)."""
    assert PAGE.count('id="overlay"') == 1
    assert '.ovl-fx{position:fixed;inset:0;z-index:60;pointer-events:none}' in _CSS
    assert 'html.mo-off .ovl-fx{display:none!important}' in _CSS
    for name in {w['overlay'] for w in WORLDS.values()}:
        assert re.search(r'\.ov-%s\{' % re.escape(name), _CSS), name
        anim = re.search(r'\.ov-%s\{animation:(\w+)' % re.escape(name), _CSS)
        assert anim, f'.ov-{name} does not drift — a frozen overlay is a texture'
        kf = re.search(r'@keyframes %s\{([^}]*\})' % re.escape(anim.group(1)), _CSS)
        assert kf, f'{anim.group(1)} has no keyframes'


def test_the_background_still_moves_when_nothing_is_happening():
    """Brightness and motion are separate knobs, and only brightness was the
    complaint. Turning both down produced a background that had stopped being
    animated at all — the regression this pins.

        calm = how bright (capped, that is the anti-overstimulating lever)
        flow = how much it moves (per skin, must stay well above zero)
    """
    from claude_sessions.themes import SKINS
    assert re.search(r'STAGE_FPS_IDLE = 2\d;', PAGE), 'idle fps too low to read as motion'
    m = re.search(r'this\._T \+= fdt \* flow \* \(([\d.]+)', PAGE)
    assert m, 'scene clock is not flow-scaled'
    assert float(m.group(1)) >= 0.4, f'idle time multiplier {m.group(1)} is frozen'
    for name, sk in SKINS.items():
        assert sk['flow'] >= 0.45, f'{name}: flow={sk["flow"]} is effectively static'
        assert sk['calm'] <= 0.5, f'{name}: calm={sk["calm"]} is back to overstimulating'


def test_a_world_locks_the_classic_pickers():
    """All or nothing. Leaving the palette gallery live while a world is on is
    just a way to get half a world."""
    assert 'function curWorld()' in PAGE
    assert 'if(w)return w.skin;' in PAGE, 'skinFor does not honour the world'
    assert 'if(w)name=w.palette;' in PAGE, 'applyTheme does not honour the world'
    assert "cb.classList.toggle('locked',!!ST.world)" in PAGE
    assert '#classicBlock.locked{opacity:' in _CSS


def test_world_palettes_and_skins_stay_out_of_the_classic_pickers():
    from claude_sessions.themes import CLASSIC_SKINS, PALETTES
    for w in WORLDS.values():
        assert w['skin'] not in CLASSIC_SKINS, w['skin']
        assert PALETTES[w['palette']].get('hidden'), w['palette']
    # and the classic three are all still offered
    assert set(CLASSIC_SKINS) == {'hud', 'crt', 'brutal'}
