"""Test that the built GUI HTML contains flicker-prevention structures.

QtWebEngine composites the page through a GPU hardware surface on Windows, and
anything that makes the compositor read the framebuffer back — a blur, a filter,
a blend mode — tears the surface swap. A plain Chromium tab handles the same DOM
fine, so a glitch in the Qt shell but NOT the browser is always the embedding,
not the markup. See the CLAUDE.md gotcha.

The rules that fall out of that, and which these tests pin:
  · animate transform and opacity only; both are compositor-only
  · ONE requestAnimationFrame chain for the whole app, and it parks when idle
  · never write DOM on a poll tick unless the value actually changed
  · no backdrop-filter / blur / mix-blend-mode anywhere
"""
import re

from claude_sessions.gui_html import PAGE

#: the page with every /* comment */ and // note stripped. Needed because these
#: tests search for the very constructs the comments explain — a comment saying
#: "backdrop-filter was removed because…" would otherwise fail the test asserting
#: backdrop-filter is gone.
def _decomment(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^\s*//.*$', '', src, flags=re.M)


_CSS = _decomment(PAGE[PAGE.index('<style>'):PAGE.index('</style>')])
_CODE = _decomment(PAGE)


def _keyframes(css):
    """(name, body) for every @keyframes block, brace-matched.

    A regex can't do this: keyframe bodies nest one level (`0%{…}`), and a
    non-greedy `\\{.*?\\}` stops at the first inner close brace while a greedy one
    runs to the end of the stylesheet."""
    out = []
    for m in re.finditer(r'@keyframes\s+([\w-]+)\s*\{', css):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(css)):
            if css[j] == '{':
                depth += 1
            elif css[j] == '}':
                depth -= 1
                if depth == 0:
                    out.append((m.group(1), css[i + 1:j]))
                    break
    return out


def test_poll_uses_cache_vars():
    """The job poll must skip DOM writes when values are unchanged. It runs every
    600ms; an unconditional write destroys and recreates text nodes each tick."""
    assert '__plMsgs' in PAGE, 'expected __plMsgs cache variable'
    assert '__plSub' in PAGE, 'expected __plSub cache variable'
    assert '__plLabel' in PAGE, 'expected __plLabel cache variable'
    assert 'msgsHtml!==__plMsgs' in PAGE, 'expected conditional DOM update for messages'
    assert 'innerHTML=msgsHtml' in PAGE, 'expected innerHTML for messages only'
    # the inline presentation needs the same discipline — it polls identically
    assert 'host.__jsub' in PAGE and 'host.__jmsgs' in PAGE


def test_poll_uses_textcontent():
    """Label/sub are text, so they must be written with textContent. innerHTML
    would reparse and rebuild the node on every tick."""
    assert 'lab.textContent=J.label' in PAGE, 'expected textContent for label'
    assert "$('#jSub').textContent=sub" in PAGE, 'expected textContent for sub (elapsed)'
    assert 'sub.textContent=J.sub' in PAGE, 'expected textContent for the inline sub'


def test_loading_bar_exists():
    """The loading bar infrastructure must be present."""
    assert 'id="loading"' in PAGE, 'expected loading bar element'
    assert 'setLoading' in PAGE, 'expected setLoading() function'
    assert '__loadingCount' in PAGE, 'expected __loadingCount variable'


def test_escape_closes_modals():
    """Escape key handler must close all modals."""
    assert "'Escape'" in PAGE, 'expected Escape key handler'
    assert "classList.remove('show')" in PAGE, 'expected class-based modal close'


def test_modals_have_aria():
    """Modals should have dialog role for accessibility."""
    assert 'role="dialog"' in PAGE, 'expected role="dialog" on modals'
    assert 'aria-modal="true"' in PAGE, 'expected aria-modal="true" on modals'


def test_no_backdrop_filter():
    """A blurred backdrop makes QtWebEngine's compositor read back and reblur the
    whole framebuffer every composite — the original flicker source."""
    assert 'backdrop-filter:' not in _CODE


def test_no_blurred_or_readback_layers():
    """Belt-and-braces alongside test_no_backdrop_filter: the pointer spotlight
    and the travelling border are both new gradient effects, and either one could
    have reached for a blur to soften itself."""
    for dead in ('backdrop-filter:', 'filter:blur', 'mix-blend-mode:'):
        assert dead not in _CODE, dead


def test_header_status_chips_are_styled():
    """.hchip/.hdrchips are emitted by refreshDashboard; without CSS they render
    as one unspaced run ('failover:20129mcp 1/10')."""
    assert '.hdrchips{' in PAGE and '.hchip{' in PAGE and '.hchip.ok{' in PAGE


def test_plan_exec_failure_is_persistent():
    """A plan job runs for minutes — its failure must outlive a 3.5s toast."""
    assert 'peDismissError' in PAGE and '.perun.err{' in PAGE


def test_long_jobs_back_off():
    """A job that has run a minute will not finish in the next 600ms; polling it
    at that rate is pure round-trips."""
    assert 'PE.elapsed>60?4000' in PAGE
    assert 'J.elapsed>60?4000' in PAGE


def test_stale_draw_is_discarded():
    assert 'let NAV_ID=0' in PAGE and 'if(myNav!==NAV_ID)return' in PAGE


def test_esc_escapes_quotes_without_dom():
    """esc() feeds attribute values too, so quotes must be escaped; the old
    textContent round-trip escaped only & < > and allocated a node per call."""
    esc = PAGE[PAGE.index('function esc(s)'):]
    esc = esc[:esc.index('\n')]
    assert 'createElement' not in esc
    assert "'\"':'&quot;'" in PAGE


# ── the motion layer ──────────────────────────────────────────
# These replaced the test_live_layer_* cases. Those pinned an ambient-wallpaper
# layer: 26 generative canvas renderers mounted into ~30 places, looping at
# 6-30fps whether or not anything had happened. The invariants below are the same
# ones — one scheduler, bounded backing store, unmount on detach, reduced-motion
# honoured — asserted against instruments that tween to a value and then stop.


def test_exactly_one_raf_chain_in_the_app():
    """Gauges, number tweens, the vendored anime engine and the 3D background all
    register into ONE loop (MO.frame). Two chains was the previous state — the
    live layer plus the dashboard constellation — and it put both on the
    compositor independently.

    anime.js is the interesting one: it ships its own rAF loop and would have
    quietly become a second chain, so useDefaultMainLoop is turned off and
    MO._loop drives engine.update() instead."""
    assert PAGE.count('_loop(now)') == 1
    # entered from exactly two places: kick(), and the loop's own tail
    assert PAGE.count('requestAnimationFrame(t => this._loop(t))') == 2
    assert 'A.engine.useDefaultMainLoop = false;' in PAGE
    # the stage renders from a registered job, never from a loop of its own
    stage = PAGE[PAGE.index('const STAGE = {'):PAGE.index('window.STAGE = STAGE;')]
    assert 'requestAnimationFrame' not in stage, 'the stage started its own chain'
    assert 'MO.frame(dt => this._tick(dt))' in stage
    # no renderer may start a loop of its own
    for dead in ('function liveLoop', 'function constLoop', 'function moLoop'):
        assert dead not in PAGE, dead


def test_the_frame_loop_parks_when_nothing_is_visible():
    """The property this has always protected is "no frames when nothing is
    visible" — NOT "no frames ever". Those were the same statement while every
    job was a value tween that settled; the background stage makes them differ,
    because a scene that is meant to be running has nothing to settle to.

    So the rule is now stated exactly. The chain still drops jobs that return
    falsy and stops once the set empties, which is what makes an idle dashboard
    with the stage off render zero frames. And with the stage ON it still refuses
    to run while the page is hidden or the window blurred — Qt reports a
    minimized window as 'visible', which is why MO.vis exists alongside
    document.hidden.

    tools/smoke_gui.py exercises both halves against a real browser; string
    matching cannot prove a loop parks."""
    assert '// parked' in PAGE
    assert 'if (!this._jobs.size) return;' in PAGE
    assert 'this.job = null;' in PAGE
    assert 'if (document.hidden || !this.vis) return;' in PAGE
    assert 'function setVis(v)' in PAGE
    # the one long-lived job has to be named as such where the rule is stated,
    # so the next person does not read the exception as a bug and "fix" it
    assert 'ONE job is allowed to stay registered indefinitely' in PAGE
    # …and every way it can be switched off must exist
    stage = PAGE[PAGE.index('const STAGE = {'):PAGE.index('window.STAGE = STAGE;')]
    assert "this.tier === 'off'" in stage
    assert '!MO.on' in stage, 'motion:off must stop the stage'
    assert 'MO.unframe(this._job)' in stage, 'no way to deregister the stage'


def test_instruments_use_one_shared_draw_path():
    """One resize/clear/draw dance for every gauge. Duplicating it per renderer is
    what made adding a surface expensive in the old layer."""
    assert PAGE.count('setTransform(dpr, 0, 0, dpr, 0, 0)') == 1
    assert PAGE.count('draw(force, dt)') == 1


def test_instruments_are_frame_capped_and_dpr_bounded():
    """A gauge has nothing to say at 60fps, and an unbounded backing store costs
    4x the fill on a 4K panel. DPR is capped at 2 rather than the ambient layer's
    1: these draw 1px ticks and hairline arcs, which alias badly at 1x."""
    assert 'const INST_FPS = 30;' in PAGE
    assert 'if (this.acc < 1 / INST_FPS) return true;' in PAGE
    assert 'Math.min(window.devicePixelRatio || 1, 2)' in PAGE


def test_instruments_unmount_detached_canvases():
    """The SPA rewrites #content wholesale; targets pointing at dead nodes must
    drop out or the registry grows without bound."""
    assert 'if (t.el.isConnected) continue;' in PAGE
    assert 'this.reg.splice(i, 1)' in PAGE
    assert 'const INST_MAX = 24;' in PAGE


def test_motion_respects_reduced_motion():
    """An OS reduce-motion preference overrides the app setting, and must stop the
    WAAPI/JS animations too — a CSS `transition:none` alone would not."""
    assert "MO_REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches" in PAGE
    assert "this.level = MO_REDUCED ? 'off' : (level || 'full');" in PAGE
    assert '@media (prefers-reduced-motion: reduce)' in PAGE


def test_animations_target_only_compositor_properties():
    """Every keyframe must animate transform/opacity (or the registered custom
    property the border angle uses), never a paint property. The old shimmer
    animated background-position and repainted the element on every step."""
    blocks = _keyframes(_CSS)
    assert blocks, 'no keyframes found'
    allowed = {'transform', 'opacity', '--beam-a'}
    for name, body in blocks:
        props = set(re.findall(r'([-\w]+)\s*:', body))
        bad = props - allowed
        assert not bad, f'@keyframes {name} animates paint properties: {bad}'


def test_no_frame_throttling_steps():
    """steps(8)/steps(20)/steps(30) were frame-rate throttles — a workaround for
    animating PAINT properties, trading smoothness for fewer invalidations. Every
    keyframe is transform/opacity now, so the compositor owns them and stepping
    buys nothing.

    steps() as a deliberate aesthetic still stands: the CRT caret must snap rather
    than fade (a caret that eases is not a caret) and the Mecha entrance hard-cuts
    on purpose. Those are design, not throttling."""
    for dead in ('steps(8)', 'steps(20)', 'steps(30)'):
        assert dead not in _CSS, dead
    # the only stepped CSS animation may be the CRT caret
    stepped = re.findall(r'animation:\s*([\w-]+)[^;}]*steps\(', _CSS)
    assert set(stepped) <= {'crtcaret'}, f'unexpected stepped animation: {stepped}'


def test_custom_property_animation_is_feature_detected():
    """@property is Chrome 85+; QtWebEngine's Chromium is older on some Qt builds.
    The travelling border must degrade to a static frame there, not break —
    color-mix() was skipped for exactly this reason."""
    assert 'CSS.registerProperty' in PAGE
    assert 'MO_HAS_PROP' in PAGE
    assert 'html:not(.mo-beam) .beam{' in PAGE


def test_lists_reconcile_instead_of_rebuilding():
    """setV() caches by HTML string, so any change rebuilt every row — losing
    hover state and making one session finishing look like the list flashing."""
    assert 'patch(host, items, keyOf, html, cls)' in PAGE
    assert 'appendChild on an existing child is a move' in PAGE
    for host in ("$('#dashRecent')", "$('#dashProjects')"):
        assert f'MO.patch({host}' in PAGE, host
    assert 'MO.patch(box,list,p=>p.encoded' in PAGE, 'sidebar rows still rebuilt'


def test_jobs_run_inline_and_escalate_to_the_modal():
    """Jobs must not hold the UI hostage for the minutes they spend in a Claude
    call. They start inline and take the modal only when the job actually parks at
    an approval gate — reacting to what the job did, not to a per-kind allowlist
    that would go stale the moment another code path called diffview.confirm."""
    assert 'function inlineJob(host,kind,params,o)' in PAGE
    assert 'if(!J.modal){J.modal=true;inlineClear(J);}   // escalate' in PAGE
    for kind in ('memory_build', 'review', 'ai_scaffold', 'ai_compress',
                 'lessons_scan', 'agent_ai', 'skill_ai', 'hook_ai'):
        assert f"inlineJob('#jban','{kind}'" in PAGE, kind
        assert f"runJob('{kind}'" not in PAGE, f'{kind} still opens the modal'


def test_instrument_refit_is_observer_driven():
    """The Qt shell and the 720px transcript drawer both change #content's width
    WITHOUT firing a window resize, so onresize alone leaves gauges mis-sized."""
    assert 'new ResizeObserver(()=>INST.refit())' in PAGE
