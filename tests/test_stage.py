"""The stage: one animated 3D background behind the whole app.

This is a deliberate, scoped reversal of "there is no ambient layer", and these
tests exist to hold the line that makes it a different thing from the layer that
was deleted:

  ONE surface, not thirty.   Guarded in tests/test_themes.py.
  Driven by state.          It is handed numbers a renderer already fetched; it
                            never issues a request, exactly like INST.set().
  It stops.                 Hidden, blurred, motion:off, stage:off, reduced
                            motion, lost context.
  It fails open.            No vendor bundle, no WebGL or a dead context all land
                            on the static CSS gradient with the app untouched.

Plus the two things a second GPU surface in this particular shell must never do:
introduce a CSS readback (the original cause of the Qt tearing) or make the app
depend on 890KB of vendored code having arrived.
"""
import re

from claude_sessions import gui, themes
from claude_sessions.gui_html import PAGE, VENDOR_FILES, vendor_asset

_CSS = PAGE[PAGE.index('<style>'):PAGE.index('</style>')]
#: all of stage.js — the object AND the scene factories, which is what the
#: "must not appear" assertions below want to cover
_STAGE = PAGE[PAGE.index('const STAGE_SCALE ='):PAGE.index('window.STAGE = STAGE;')]
_SCENES = PAGE[PAGE.index('const STAGE_SCENES = {'):PAGE.index('/* ── wiring ──')]


# ── the data ──────────────────────────────────────────────────

def test_every_skin_names_a_scene_that_exists():
    """A skin naming a missing scene falls back to 'hud' silently, so the skin
    would look identical to another one and nobody would know why."""
    for name, sk in themes.SKINS.items():
        assert sk['stage'] in themes.STAGE_SCENES, f'{name}: {sk["stage"]}'
        assert f"  {sk['stage']}(TH, c) {{" in _SCENES \
            or f"  '{sk['stage']}'(TH, c) {{" in _SCENES, \
            f'{name}: no {sk["stage"]} implementation'


def test_every_scene_is_worn_by_a_skin():
    """The other direction: an orphan scene is dead code that still costs review
    attention every time someone touches this file."""
    worn = {sk['stage'] for sk in themes.SKINS.values()}
    assert set(themes.STAGE_SCENES) == worn, set(themes.STAGE_SCENES) ^ worn


def test_bloom_is_off_where_the_skin_says_it_should_be():
    """Bloom costs two extra render targets. Brutalism has no glow by definition
    and the CRT draws its own in-shader, so both must genuinely skip the
    composer rather than run it at strength 0."""
    assert themes.SKINS['brutal']['bloom'] == 0
    assert themes.SKINS['crt']['bloom'] == 0
    assert 'if (!strength) return;' in _STAGE


def test_translucency_is_what_makes_the_stage_visible():
    """Fully opaque panels would hide the scene everywhere but the gutters, so
    every skin has to make a deliberate choice about it — and Brutalist choosing
    1.0 is a choice, not an oversight."""
    for name, sk in themes.SKINS.items():
        assert 0.5 <= sk['op'] <= 1.0, f'{name}: op={sk["op"]}'
    assert themes.SKINS['glass']['op'] < themes.SKINS['brutal']['op']
    assert '--sk-op' in _CSS
    assert 'rgba(var(--panel-rgb' in _CSS


# ── the contract ──────────────────────────────────────────────

def test_the_stage_never_fetches_anything():
    """Same rule the instruments follow. A background that polls is a background
    that keeps the machine awake for its own benefit."""
    for dead in ('fetch(', 'api(', 'XMLHttpRequest', 'setInterval'):
        assert dead not in _STAGE, f'{dead} in the stage'


def test_it_is_driven_by_real_workspace_state():
    """The honest answer to "animated everywhere": the motion means something.
    Energy comes from running jobs, a launch shocks it, navigation ripples it."""
    for fn in ('energy(n)', 'shock()', 'impulse()', 'page(name)'):
        assert fn in _STAGE, fn
    assert 'function stageEnergy(jobs,burn)' in PAGE
    assert 'stageEnergy(liveJobs(),0)' in PAGE, 'jobs do not feed the stage'
    assert 'STAGE.shock()' in PAGE, 'the launch moment does not reach the stage'
    assert 'STAGE.page(page);STAGE.impulse();' in PAGE, 'navigation does not'
    # ...and NOT off throughput alone. Feeding a liveness test from a token
    # counter is the one-word bug that made the equalizer animate forever.
    assert 'const j=Math.min(1,(jobs||0)/2);' in PAGE


def test_every_pause_condition_is_present():
    """Five ways it must stop. Losing any one of them means a laptop rendering a
    3D scene into a window nobody is looking at."""
    assert 'if (document.hidden || !this.vis) return;' in PAGE   # tab hidden
    assert 'function setVis(v)' in PAGE                          # Qt blur/minimise
    assert '!MO.on' in _STAGE                                    # motion:off
    assert "this.tier === 'off'" in _STAGE                       # stage:off
    assert "MO_REDUCED ? 'off'" in PAGE                          # OS preference
    assert 'webglcontextlost' in _STAGE                          # driver reset


def test_it_is_frame_capped_and_render_scaled():
    """A background has nothing to say at 60fps, and devicePixelRatio is ignored
    on purpose: this is a soft full-screen field, not the instruments' hairline
    arcs (which clamp to 2 for exactly the opposite reason)."""
    assert 'const STAGE_SCALE = 0.75;' in PAGE
    assert re.search(r'STAGE_FPS_IDLE = 2\d;', PAGE)
    assert 'if (this._acc < 1 / fps) return true;' in _STAGE
    assert 'devicePixelRatio' not in _STAGE, 'DPR must not drive the stage'


def test_the_fallback_chain_exists():
    """WebGL -> static gradient, at every failure point, with the app untouched.
    The washes paint from first byte and are only removed once GL has actually
    rendered a frame, so a slow module import is not a second of blank."""
    assert '_static()' in _STAGE and '_giveUp(why)' in _STAGE
    assert 'stage-off' in _CSS and 'stage-on' in _CSS
    assert 'html.stage-on body::before,html.stage-on body::after{opacity:0}' in _CSS
    assert 'body::before' in _CSS, 'the static wash was deleted, not kept'
    assert "if (!this._painted) { this._painted = true; this._live(); }" in _STAGE
    assert "window.addEventListener('vendor-failed'" in PAGE


def test_the_app_does_not_depend_on_the_vendor_bundle():
    """Every reach into the vendored globals is guarded. A failed import must
    cost the background and nothing else."""
    assert PAGE.count('if(window.STAGE)') + PAGE.count('if (window.STAGE)') >= 4
    assert 'const A = window.ANI;\n    if (!A) return null;' in PAGE
    # motion falls back to its own WAAPI path when anime is missing
    assert 'if (!A) {                                  // no vendor bundle: old path' in PAGE


def test_no_readback_layer_anywhere_near_the_canvas():
    """The whole reason bloom is affordable here is that it happens in GL. A CSS
    filter on or around this canvas would reintroduce the exact framebuffer
    readback that caused the Qt tearing."""
    stage_css = _CSS[_CSS.index('#stage{'):_CSS.index('body::before')]
    for dead in ('backdrop-filter', 'filter:', 'mix-blend-mode'):
        assert dead not in stage_css, f'{dead} on the stage layer'
    assert 'alpha: false' in _STAGE, 'a transparent surface costs a blend per composite'


# ── serving the vendored code ─────────────────────────────────

def test_vendored_libraries_are_present_with_their_licences():
    """Vendored, not CDN'd: the GUI is offline by design. Both are MIT and the
    licence text ships beside the code."""
    for f in ('three.module.min.js', 'three.core.min.js', 'anime.esm.min.js',
              'LICENSE-three.txt', 'LICENSE-anime.txt'):
        assert f in VENDOR_FILES, f
    for f in ('postprocessing/EffectComposer.js', 'postprocessing/UnrealBloomPass.js',
              'postprocessing/Pass.js', 'shaders/CopyShader.js'):
        assert f in VENDOR_FILES, f
    assert 'MIT' in VENDOR_FILES['LICENSE-three.txt'].read_text(encoding='utf-8')


def test_vendor_is_served_not_inlined():
    """~890KB in the page string on every load, for code no test asserts on, is
    pure cost. It is a separate cacheable route instead — and stage.js, which IS
    ours, stays inside PAGE so the string-matching tests can still see it."""
    assert 'three.module.min' not in PAGE.replace('"/vendor/three.module.min.js"', '')
    assert len(PAGE) < 600_000, f'page is {len(PAGE)} bytes — is a library inlined?'
    assert 'const STAGE = {' in PAGE, 'stage.js must stay in the bundle'


def test_the_vendor_route_is_reachable_without_the_guard_header():
    """A <script src> cannot attach X-Claudectl, so a guarded route would 403
    every module fetch. Placed with / and /graph, before _guard()."""
    src = gui.do_GET_SOURCE if hasattr(gui, 'do_GET_SOURCE') else ''
    import inspect
    src = src or inspect.getsource(gui._Handler.do_GET)
    assert src.index("startswith('/vendor/')") < src.index('self._guard()')


def test_the_vendor_route_cannot_escape_its_directory():
    """The allowlist is a dict built by walking the directory, so traversal is a
    miss rather than a path-arithmetic bug waiting to be got wrong."""
    for evil in ('../gui.py', '../../pyproject.toml', '/etc/passwd',
                 '..%2Fgui.py', 'nope.js', '', '.'):
        assert vendor_asset(evil) is None, evil
    got = vendor_asset('anime.esm.min.js')
    assert got and got[1] == 'text/javascript' and len(got[0]) > 1000


def test_vendored_assets_are_cached_hard():
    """Pinned, immutable library code fetched once — not on every reload."""
    import inspect
    src = inspect.getsource(gui._Handler._serve_vendor)
    assert 'max-age=' in src and 'immutable' in src


# ── the setting ───────────────────────────────────────────────

def test_stage_tier_round_trips(monkeypatch, tmp_path):
    monkeypatch.setattr(gui._c, 'config_dir', str(tmp_path))
    for saved, want in (({}, 'cinematic'), ({'stage': 'lite'}, 'lite'),
                        ({'stage': 'off'}, 'off'), ({'stage': 'bogus'}, 'cinematic')):
        assert gui._stage_tier(saved) == want, saved


def test_motion_off_forces_the_stage_off():
    """Someone who has asked for no animation has not asked for a 3D
    background, whatever the stage setting happens to say."""
    assert gui._stage_tier({'motion': 'off', 'stage': 'cinematic'}) == 'off'
    assert gui._stage_tier({'theme_motion': 'off'}) == 'off'   # legacy key


def test_the_setting_is_offered_and_persisted():
    assert "id=\"sStage\"" in PAGE
    assert "post('/api/settings',{stage:ST.stage})" in PAGE
    assert "localStorage.setItem('ctl_stage'" in PAGE
    import inspect
    assert "'stage'" in inspect.getsource(gui._Handler.do_POST)


def test_lite_is_documented_as_the_tearing_escape_hatch():
    """The Qt surface-swap history is the reason this tier exists at all; if the
    note goes, the next person just turns the whole thing off."""
    assert 'lite' in themes.STAGE_TIERS
    assert 'tear' in PAGE[PAGE.index('const STAGE_NOTE={'):
                          PAGE.index('const STAGE_NOTE={') + 700]
