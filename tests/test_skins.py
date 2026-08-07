"""Skins: a theme overhauls the shape of the app, not only its colours.

A palette answers "what colours"; a skin answers "what IS this app" — corner
treatment, border weight, surface fill, heading type, how cards arrive, how a
gauge is stroked. The two are orthogonal, so these tests never touch colour
(tests/test_themes.py owns contrast) and only guard the skin contract.

The load-bearing rule is the one-shot rule: a skin's signature effect fires on an
event and stops. A looping flourish is the ambient wallpaper this project already
deleted once.
"""
import re

from claude_sessions.gui_html import PAGE
from claude_sessions.themes import PALETTES, SKINS, SKIN_KEYS, SKIN_NAMES

_CSS = re.sub(r'/\*.*?\*/', '',
              PAGE[PAGE.index('<style>'):PAGE.index('</style>')], flags=re.S)
_JS = PAGE[PAGE.index('</style>'):]


# ── the data ──────────────────────────────────────────────────

def test_every_skin_defines_every_token():
    """A missing token silently falls back to the CSS default, which makes the
    skin a partial no-op that still *looks* configured."""
    for name, sk in SKINS.items():
        for key in SKIN_KEYS:
            assert key in sk, f'{name} is missing {key}'
        assert isinstance(sk['radius'], int) and isinstance(sk['border'], int)
        assert sk['label'] and sk['blurb']


def test_every_skin_defines_its_gauge_language():
    """A HUD ring and a Sakura ring must not be the same ring recoloured."""
    for name, sk in SKINS.items():
        g = sk['gauge']
        assert g['tick'] in ('line', 'dot', 'block'), (name, g['tick'])
        assert g['cap'] in ('round', 'butt'), (name, g['cap'])
        assert 0 < g['lw'] <= 3 and 0 <= g['glow'] <= 1, (name, g)
    # and they must not all be identical, or the setting does nothing
    assert len({(s['gauge']['tick'], s['gauge']['cap']) for s in SKINS.values()}) > 1


def test_every_palette_wears_a_real_skin():
    for name, pal in PALETTES.items():
        assert pal.get('skin') in SKINS, f'{name} wants missing skin {pal.get("skin")}'


def test_every_skin_is_worn_by_default_somewhere():
    """A skin no palette defaults to is one nobody will discover."""
    worn = {p['skin'] for p in PALETTES.values()}
    assert worn == set(SKIN_NAMES), f'never a default: {set(SKIN_NAMES) - worn}'


# ── the CSS ───────────────────────────────────────────────────

def test_every_skin_has_a_css_block():
    for name in SKIN_NAMES:
        assert f'html.skin-{name} ' in _CSS, f'no CSS for skin {name}'


def test_skin_css_comes_last():
    """A class on <html> adds no more specificity than the .card rule it
    countermands, so only source order decides. Placed before the base rules the
    entire skin system silently becomes a no-op — which is exactly what happened
    to the narrow-window icon rail before it was moved."""
    assert _CSS.index('html.skin-hud ') > _CSS.index('.card{background:')
    assert _CSS.index('html.skin-brutal ') > _CSS.index('.btn{background:')


def test_no_skin_reintroduces_a_readback_layer():
    """The temptation moves between looks; the answer does not.

    It used to be Glass wanting real glassmorphism. That skin was thrown out, and
    the pull is now Cyberpunk wanting a neon bloom — both reach for the same
    property that caused this project's QtWebEngine tearing. The reasoning has to
    live somewhere a skin's deletion cannot take it with it, which is why it now
    sits at the top of the override block rather than inside one look."""
    for dead in ('backdrop-filter', 'filter:blur', 'mix-blend-mode'):
        assert dead not in _CSS, dead
    # and the reasoning has to survive in the source, or someone "fixes" it
    assert 'Do not add the blur' in PAGE or 'do not add the blur' in PAGE.lower()


def test_skin_geometry_is_token_driven():
    """Card geometry reads from --sk-*, so adding a skin needs no new CSS rule
    for radius/border — only for its signature trait."""
    assert 'border-radius:var(--sk-r' in _CSS
    assert 'border-width:var(--sk-bw' in _CSS
    assert 'font-family:var(--sk-font' in _CSS


# ── the motion ────────────────────────────────────────────────

def test_every_skin_has_an_entrance():
    block = _JS[_JS.index('const SKIN_ENTER = {'):]
    block = block[:block.index('\n};')]
    for name in SKIN_NAMES:
        key = f"'{name}'" if '-' in name else name
        assert re.search(rf'(^|\s){re.escape(key)}:\s*\{{', block, re.M), \
            f'{name} has no entrance'


def test_every_skin_has_a_burst_and_it_exists():
    block = _JS[_JS.index('const SKIN_BURST = {'):]
    block = block[:block.index('};')]
    named = dict(re.findall(r"'?([\w-]+)'?:\s*'(\w+)'", block))
    for name in SKIN_NAMES:
        assert name in named, f'{name} has no burst'
        assert f'  {named[name]}(host)' in _JS, \
            f'{name} points at missing burst {named[name]}'


def test_bursts_never_loop():
    """THE rule. A signature effect fires on an event, runs once, and removes
    itself. Petals falling forever is the ambient wallpaper this project deleted;
    petals bursting once on session launch is feedback."""
    block = _JS[_JS.index('const MO_BURST = {'):]
    block = block[:block.index('\n};')]
    assert block, 'MO_BURST not found'
    # no WAAPI option may request repeats
    for dead in ('iterations', 'Infinity', 'infinite'):
        assert dead not in block, f'a burst uses {dead}'
    # and the overlay must be torn down when the animations finish
    tear = _JS[_JS.index('  burst(el, kind) {'):]
    tear = tear[:tear.index('\n  },')]
    assert 'host.remove()' in tear
    assert 'a.onfinish = done' in tear and 'a.oncancel = done' in tear


def test_bursts_are_full_motion_only():
    """A flourish carries no information, so it must not run at `subtle`."""
    tear = _JS[_JS.index('  burst(el, kind) {'):]
    tear = tear[:tear.index('\n  },')]
    assert 'if (!this.full || !el) return;' in tear
    assert 'html.mo-off .burst,html.mo-subtle .burst{display:none}' in _CSS


def test_burst_overlay_cannot_affect_layout():
    """It is injected into arbitrary cards, so it has to be inert."""
    assert '.burst{position:absolute;inset:0;pointer-events:none' in _CSS


def test_the_only_looping_skin_effect_in_the_dom_is_the_crt_caret():
    """One deliberate exception in CSS, and it must be gated. A terminal caret
    that does not blink is not a caret; everything else that loops in the DOM is
    decoration.

    A skin's background scene loops too, but it is not a DOM effect: it is GL on
    one surface behind the app, governed separately (its own setting, and it
    stops on hidden/blur/motion-off). Keeping this assertion scoped to CSS is the
    point — it is what still catches a petal keyframe sneaking back into a
    card."""
    looping = re.findall(r'animation:[^;}]*infinite', _CSS)
    # the shared spinner/pip/shimmer are app-level, not skin-level
    skin_loops = [m for m in looping if 'crtcaret' in m]
    assert len(skin_loops) == 1, f'skin-level loops: {looping}'
    assert 'html.mo-off.skin-crt .card h3::after{animation:none' in _CSS


# ── the wiring ────────────────────────────────────────────────

def test_skin_is_applied_and_persisted():
    assert 'function applySkin(name)' in PAGE
    assert 'function skinFor(themeName)' in PAGE
    assert "MO.skin=name" in PAGE, 'entrance choreography not wired to the skin'
    assert 'INST.setSkin(sk)' in PAGE, 'gauges not wired to the skin'
    assert "localStorage.setItem('ctl_skin'" in PAGE
    assert "post('/api/settings',{skin:n})" in PAGE


def test_an_explicit_skin_overrides_the_palette_default():
    """`skin:''` means "wear whatever the palette names" — the default state."""
    fn = PAGE[PAGE.index('function skinFor(themeName){'):]
    fn = fn[:fn.index('\n}')]
    assert 'if(ST.skin&&' in fn
    assert 't.skin' in fn


def test_the_launch_moment_is_marked():
    """A session opens in a separate console window; without this the GUI gives no
    sign anything happened beyond a toast."""
    assert 'MO.launched(' in PAGE
    assert 'launched(el)' in PAGE


def test_skin_setting_round_trips():
    from claude_sessions import gui
    src = open(gui.__file__, encoding='utf-8').read()
    assert "'skin': s.get('skin', '')" in src
    assert "'skins':" in src
    allow = src[src.index("for k in ('default_effort'"):]
    allow = allow[:allow.index('):')]
    assert "'skin'" in allow, 'the skin choice is never saved'


def test_settings_offers_the_picker():
    assert 'function drawSkinPicker()' in PAGE
    assert 'id="thSkin"' in PAGE
    # Only the CLASSIC skins are offered — a world skin is one part of a bundle
    # and is meaningless bolted onto an arbitrary palette. Worlds get their own
    # picker above the gallery.
    from claude_sessions.themes import CLASSIC_SKINS, WORLDS
    for name in CLASSIC_SKINS:
        assert f'.skm-{name}' in _CSS, f'no picker mock for {name}'
    assert 'function drawWorldPicker()' in PAGE
    assert 'id="thWorld"' in PAGE
    for name in WORLDS:
        assert f'.wm-{name}' in _CSS or f"data-v=\"${{esc(n)}}\"" in PAGE, name
    # and picking a world must disable the classic controls
    assert "cb.classList.toggle('locked',!!ST.world)" in PAGE


def test_fonts_stay_offline():
    """The GUI is self-contained by design — no CDN, no webfont. Skins may only
    name fonts that ship with Windows."""
    assert '@font-face' not in _CSS
    assert 'fonts.googleapis' not in PAGE and 'fonts.gstatic' not in PAGE
    for name, sk in SKINS.items():
        assert 'url(' not in sk['font'], name
