"""Headless smoke test for the GUI: boot the real PAGE against stub API data and
inspect what actually rendered.

The string-matching tests in tests/ prove the code is *shaped* right; this proves
it *runs* — instruments mount and paint, readouts carry values, the frame loop
parks when nothing is happening, every page renders without a JS error, and the
narrow-window layout re-fits.

Cannot verify the QtWebEngine flicker itself: a headless/GPU-less box won't
composite to a capturable buffer, so screen-scrape probes see a static frame
(CLAUDE.md). That needs real hardware.

    py -3 tools/smoke_gui.py
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from claude_sessions import gui                       # noqa: E402
from claude_sessions.gui_html import PAGE, vendor_asset  # noqa: E402
from claude_sessions import themes as _TH        # noqa: E402

PORT = 8793

STATE = {
    'projects': [{'name': 'Claude', 'path': 'D:\\Claude', 'encoded': 'd--claude',
                  'accounts': ['default', 'work'], 'primary_cfgdir': '',
                  'auto_memory': True, 'last_active': '2m'},
                 {'name': 'Other', 'path': 'D:\\Other', 'encoded': 'o',
                  'accounts': ['work'], 'primary_cfgdir': 'w',
                  'auto_memory': False, 'last_active': '1d'}],
    'accounts': [{'name': 'default', 'dir': '', 'active': True},
                 {'name': 'work', 'dir': 'w', 'active': False}],
    'recent': [{'project': 'Claude', 'path': 'D:\\Claude', 'encoded': 'd--claude',
                'sid': 's1', 'name': 'a session', 'age': '2m', 'cfgdir': ''}],
    'options': {'efforts': ['default', 'high'], 'models': ['opus', 'sonnet'],
                'model_labels': ['Opus', 'Sonnet'], 'perms': ['default'],
                'perm_labels': ['d'], 'thinking': [''], 'thinking_labels': [''],
                'frontier': [['opus', 'high', 'Opus', '$$', '70', 'note']]},
    'defaults': {'effort': '', 'model': '', 'perm': '', 'max_thinking': '',
                 'subagent_model': ''},
    'ui_mode': 'gui', 'gui_shell': 'auto', 'theme': 'neon', 'motion': 'full',
    'stage': 'cinematic',
    'themes': gui.theme_palettes(), 'skin': '',
    'skins': {n: dict(v) for n, v in _TH.SKINS.items()},
    'worlds': {n: dict(v) for n, v in _TH.WORLDS.items()},
    'classic_skins': list(_TH.CLASSIC_SKINS),
    'world': '',
    'plan_model': '', 'exec_model': '', 'extract_model': '',
    'omniroute_base_url': '', 'omniroute_has_key': False,
    'omniroute_exec_model': '', 'failover_models': [], 'failover_port': 20129,
    'failover_quiet': False,
}
_NOW = time.time()
DASH = {
    'today': {'tokens': 412000, 'sessions': 7}, 'days': 30, 'generated_at': _NOW,
    'jobs': [],
    'mcp': [{'name': 'ide', 'running': True}, {'name': 'asana', 'running': False}],
    'failover': {'running': True, 'port': 20129},
    'recent': [{'project': 'Claude', 'title': 'a session', 'msgs': 12, 'sid': 's1',
                'age': '2m', 'path': 'D:\\Claude', 'encoded': 'd--claude',
                'cfgdir': '', 'account': 'default', 'omni': True}],
    'breakdown': {
        'days': [{'date': '2026-08-%02d' % (i + 1), 'tokens': 100000 + i * 9000,
                  'cost': i * 0.4, 'omni_tokens': i * 3000,
                  'accounts': {'default': 100000 + i * 9000}} for i in range(14)],
        'accounts': [{'account': 'default'}],
        'projects': [
            {'name': 'Claude', 'enc': 'd--claude', 'tokens': 900000, 'cost': 4.2,
             'age': '2m', 'mtime': _NOW, 'accounts': ['default', 'work'],
             'omni': True, 'sparkline': [1, 4, 2, 7, 3, 9, 5]},
            {'name': 'Other', 'enc': 'o', 'tokens': 300000, 'cost': 1.1,
             'age': '1d', 'mtime': _NOW - 90000, 'accounts': ['work'],
             'sparkline': [2, 1, 3]}],
        'totals': {'omni_tokens': 120000, 'omni_saved': 7.5}},
}
PLAN = {'accounts': [{'account': 'default', 'email': 'me@x.ai', 'plan': 'max',
                      'status': 'ok',
                      'windows': [{'label': 'session', 'pct': 62, 'resets': 'in 3h'},
                                  {'label': 'weekly', 'pct': 88, 'resets': 'Fri'}]}]}
ROUTES = {
    '/api/state': STATE, '/api/dashboard': DASH, '/api/usage/plan': PLAN,
    '/api/memory/active': {'active': ['D:\\Claude']},
    '/api/search-index': {'rows': []},
    '/api/mcp': {'servers': [{'name': 'ide', 'status': 'ok'},
                             {'name': 'asana', 'status': 'down'}]},
    '/api/usage/daily': {'days': [{'day': 'd%d' % i, 'tokens': i * 1000,
                                   'tok_fmt': '%dk' % i, 'cost': i * .1}
                                  for i in range(14)]},
    '/api/usage/projects': {'projects': []},
    '/api/accounts': {'accounts': [
        {'name': 'default', 'resolved': '~/.claude', 'active': True, 'dir': ''},
        {'name': 'work', 'resolved': '~/.claude-work', 'active': False, 'dir': 'w'}]},
    '/api/agents': {'categories': []}, '/api/skills': {'project': [], 'templates': []},
    '/api/hooks': {'hooks': [], 'templates': []},
    '/api/omniroute/status': {'ok': False}, '/api/failover/status': {'running': False},
    '/api/memory/auto-list': {'projects': []},
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, o):
        b = json.dumps(o).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _raw(self, body, ctype):
        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/':
            self._raw(PAGE.encode(), 'text/html')
            return
        # the vendored modules, same allowlist the real server uses. Without
        # these the import in index.html fails, `vendor-ready` never fires and
        # the whole stage silently falls back — which the checks below would
        # then report as a stage bug rather than a missing route.
        if p.startswith('/vendor/'):
            got = vendor_asset(p[len('/vendor/'):])
            if got is None:
                self.send_error(404)
                return
            self._raw(*got)
            return
        self._j(ROUTES.get(p, {}))

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        self.rfile.read(n)
        self._j({'ok': True})


def main():
    from playwright.sync_api import sync_playwright
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    errs = []
    fails = []

    def check(label, ok, detail=''):
        print(('  OK   ' if ok else '  FAIL ') + label + (' — ' + str(detail) if detail else ''))
        if not ok:
            fails.append(label)

    with sync_playwright() as pw:
        # Headless Chromium has no GPU, so WebGL needs SwiftShader explicitly or
        # every scene falls back to the static gradient and the stage checks
        # below test nothing. --enable-unsafe-swiftshader is required from
        # Chrome 132; harmless before it.
        br = pw.chromium.launch(args=[
            '--use-gl=angle', '--use-angle=swiftshader',
            '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = br.new_page(viewport={'width': 1600, 'height': 1000})
        pg.on('console', lambda m: errs.append((m.type, m.text)) if m.type == 'error' else None)
        # keep the stack: 'Cannot set properties of null' with no frame behind it
        # is a scavenger hunt across 3000 lines
        pg.on('pageerror', lambda e: errs.append(('pageerror', str(e) + '\n' + (e.stack or ''))))
        pg.goto(f'http://127.0.0.1:{PORT}/')
        pg.wait_for_timeout(1800)

        print('\n— dashboard —')
        kinds = pg.evaluate("INST.reg.map(t=>t.kind+':'+t.key)")
        check('instruments mounted', len(kinds) >= 5, kinds)
        paint = pg.evaluate("""INST.reg.map(t=>{
          const c=t.cv.getContext('2d');
          if(!t.cv.width||!t.cv.height)return t.kind+':NOSIZE';
          const d=c.getImageData(0,0,t.cv.width,t.cv.height).data;
          let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;
          return t.kind+':'+(n>200?'painted':'BLANK');})""")
        check('every gauge painted', all('painted' in p for p in paint), paint)
        reads = pg.evaluate("[...document.querySelectorAll('.iread b')].map(e=>e.textContent)")
        # a genuine zero is a valid reading (no jobs running); only the '–'
        # placeholder means a gauge never received a feed
        check('readouts left the placeholder', '–' not in reads and '' not in reads, reads)
        check('quota ring shows the peak window', reads and reads[0] == '88%', reads[:1])
        units = pg.evaluate("[...document.querySelectorAll('.iread i')].map(e=>e.textContent)")
        print('       units:', units)
        foots = pg.evaluate("[...document.querySelectorAll('.ifoot')].map(e=>e.textContent.trim())")
        for f in foots:
            print('       ·', f)
        kpi = pg.evaluate("[...document.querySelectorAll('.kpi .kv2')].map(e=>e.textContent)")
        check('KPI strip tweened', all(k not in ('', '–') for k in kpi), kpi)
        links = pg.evaluate("INST.feed('flow').links.length")
        check('flow map found a shared-account link', links > 0, f'{links} links')
        rows = pg.evaluate("document.querySelectorAll('#dashProjects .hrow').length")
        check('project rows reconciled', rows == 2, f'{rows} rows')
        print('\n— the background stage —')
        vend = pg.evaluate("[!!window.THREE, !!window.ANI, !!window.THREE_POST]")
        check('vendored three/anime/postprocessing loaded', vend == [True, True, True], vend)
        check('anime does not start a second rAF chain',
              pg.evaluate("MO.ani && MO.ani.engine.useDefaultMainLoop===false"))
        live = pg.evaluate("[STAGE.ok, STAGE.failed, document.documentElement.classList.contains('stage-on')]")
        check('stage mounted and painted a frame', live == [True, False, True], live)
        check('the static wash is gone once GL is live',
              pg.evaluate("getComputedStyle(document.body,'::before').opacity") == '0')
        # a scene per skin, each one actually building
        bad = pg.evaluate("""(()=>{const out=[];
          const S=ST.skins||{};
          for(const n of Object.keys(ST.worlds||{})){
            try{ST.world=n;applyTheme(ST.theme);
              const want=S[ST.worlds[n].skin].stage;
              if(!STAGE.ok)out.push(n+':dead');
              else if(STAGE.scene!==want)out.push(n+':'+STAGE.scene);
              else if(!document.documentElement.classList.contains('world-'+n))out.push(n+':no class');
            }catch(e){out.push(n+':'+e.message);}}
          ST.world='';
          for(const n of (ST.classic_skins||[])){
            try{ST.skin=n;applyTheme(ST.theme);
              if(!STAGE.ok)out.push(n+':dead');
              else if(STAGE.scene!==S[n].stage)out.push(n+':'+STAGE.scene);
            }catch(e){out.push(n+':'+e.message);}}
          ST.skin='';applyTheme(ST.theme);return out;})()""")
        # A scene object can construct fine while its shader fails to compile —
        # three logs that to the console and renders nothing. Counting console
        # errors across the loop is what actually catches an undeclared uniform.
        pg.wait_for_timeout(400)
        shader = [t for t in errs if 'Shader Error' in t[1] or 'not compiled' in t[1]]
        check('every world and skin builds its own scene', bad == [], bad)
        check('and every shader compiles', not shader,
              shader[0][1].split(chr(10))[0] if shader else '')

        print('\n— …and it is driven by state, not free-running —')
        # The whole justification for bringing a background back. String matching
        # can show the wiring exists; only running it shows the numbers move.
        pg.evaluate("stopDashboard()")          # else it re-feeds energy every 10s
        pg.evaluate("STAGE.energy(0)")
        pg.wait_for_timeout(2400)
        idle = pg.evaluate("STAGE._E")
        t0 = pg.evaluate("STAGE._T")
        pg.wait_for_timeout(900)
        idle_rate = pg.evaluate("STAGE._T") - t0
        check('idle settles to a crawl', idle < 0.15, round(idle, 3))

        pg.evaluate("stageEnergy(2,0)")          # two jobs running
        pg.wait_for_timeout(2400)
        busy = pg.evaluate("STAGE._E")
        t1 = pg.evaluate("STAGE._T")
        pg.wait_for_timeout(900)
        busy_rate = pg.evaluate("STAGE._T") - t1
        check('a running job raises energy', busy > 0.8, round(busy, 3))
        check('and the scene runs visibly faster', busy_rate > idle_rate * 2.5,
              f'{idle_rate:.2f}/s idle vs {busy_rate:.2f}/s busy')
        # Burn alone must NOT saturate. Driving liveness off a throughput number
        # is the one-word bug that made the equalizer animate forever after a
        # single token had been spent; the stage must not repeat it.
        pg.evaluate("stageEnergy(0,1)")
        pg.wait_for_timeout(2400)
        burn = pg.evaluate("STAGE._E")
        check('burn alone does not saturate it', 0.25 < burn < 0.65, round(burn, 3))

        pg.evaluate("MO.launched(document.querySelector('.main'))")
        pg.wait_for_timeout(120)
        check('launching fires a shockwave', pg.evaluate("STAGE._shock") > 0.5)
        pg.wait_for_timeout(1600)
        check('which decays away', pg.evaluate("STAGE._shock") == 0)

        was = pg.evaluate("[STAGE._densTgt, STAGE._T]")
        pg.evaluate("go('settings')")
        pg.wait_for_timeout(200)
        now = pg.evaluate("[STAGE._densTgt, STAGE._T, STAGE._pulse]")
        check('each page tunes the one stage', now[0] < was[0], f'{was[0]} -> {now[0]}')
        check('navigation ripples but never restarts it',
              now[2] > 0 and now[1] >= was[1], now)
        pg.evaluate("go('home');startDashboard()")
        pg.wait_for_timeout(600)

        print('\n— the headline claim: idle renders zero frames —')
        # The stage is the ONE job allowed to stay registered, so turn it off to
        # assert the underlying property: with nothing live, the chain empties.
        pg.evaluate("STAGE.setTier('off')")
        # long enough for the heartbeat's second tick (pollActiveMem runs every
        # other 2500ms tick) as well as for every gauge to settle
        pg.wait_for_timeout(4000)
        pip = pg.evaluate("document.querySelectorAll('#plist .amk.pip').length")
        check('scanning project shows a live pip', pip == 1, f'{pip}')
        parked = pg.evaluate("[MO._raf===null, MO._jobs.size, INST.job===null]")
        check('frame loop parked while idle', parked == [True, 0, True], parked)

        print('\n— and with the stage running, it still stops when unseen —')
        pg.evaluate("STAGE.setTier('cinematic')")
        pg.wait_for_timeout(700)
        check('stage keeps the chain alive while visible',
              pg.evaluate("MO._raf!==null && MO._jobs.size>0"),
              pg.evaluate("MO._jobs.size"))
        # Qt reports a minimized window as visible, which is why this is driven
        # off blur rather than document.hidden alone
        pg.evaluate("setVis(false)")
        pg.wait_for_timeout(400)
        check('blur parks the chain even with the stage on',
              pg.evaluate("MO._raf===null"))
        pg.evaluate("setVis(true)")
        pg.wait_for_timeout(400)
        check('focus resumes it', pg.evaluate("MO._raf!==null"))
        pg.evaluate("MO.set('off')")
        pg.wait_for_timeout(400)
        check('motion:off stops the stage too', pg.evaluate("MO._raf===null"))
        pg.evaluate("MO.set('full');STAGE.setTier('off')")
        pg.wait_for_timeout(300)

        print('\n— a running job keeps the activity gauge alive —')
        # Stop the 10s dashboard poll first. It re-feeds beats:0 from the stub,
        # so whether this check sees a live gauge would otherwise depend on
        # where in the poll cycle the preceding checks happened to land.
        pg.evaluate("stopDashboard()")
        pg.evaluate("INST.set('jobs',{v:.5,beats:2})")
        pg.wait_for_timeout(600)
        alive = pg.evaluate("[MO._raf!==null, INST.job!==null]")
        check('gauge runs while work is running', alive == [True, True], alive)
        pg.evaluate("INST.set('jobs',{v:0,beats:0})")
        pg.wait_for_timeout(1500)
        check('and parks again when it stops',
              pg.evaluate("MO._raf===null"), pg.evaluate("MO._jobs.size"))
        pg.evaluate("startDashboard()")

        print('\n— every page renders —')
        for p in ['usage', 'searchp', 'mcp', 'agents', 'skills', 'hooks',
                  'accounts', 'settings', 'helpp', 'home']:
            before = len(errs)
            pg.evaluate(f"go('{p}')")
            pg.wait_for_timeout(500)
            check(f'page {p}', len(errs) == before, errs[before:])

        print('\n— motion levels —')
        for lv, want in [('subtle', 'mo-subtle'), ('off', 'mo-off'), ('full', 'mo-beam')]:
            pg.evaluate(f"MO.set('{lv}')")
            pg.wait_for_timeout(200)
            cls = pg.evaluate("document.documentElement.className")
            check(f'motion={lv}', want in cls, cls)
        pg.evaluate("MO.set('off')")
        pg.wait_for_timeout(400)
        check('off stops the loop', pg.evaluate("MO._raf===null"))
        pg.evaluate("MO.set('full')")

        print('\n— running-job banner —')
        pg.evaluate("""(()=>{const J={jid:'x',label:'Building memory',status:'running',
          msgs:[{ok:true,text:'step 1'}],elapsed:12,sub:'12s elapsed',err:'',
          sel:'#jban',host:document.querySelector('#jban'),modal:false};
          JOBS['x']=J;inlineRender(J);})()""")
        pg.wait_for_timeout(300)
        check('banner visible with a travelling border',
              pg.evaluate("!!document.querySelector('#jban .perun.beam')"))
        check('banner label rendered',
              pg.evaluate("document.querySelector('#jban .jlbl').textContent")
              == 'Building memory')

        print('\n— skin signature effects fire once and clean up —')
        # stop the 10s dashboard poll first: it can wake the frame loop mid-check
        # and make a perfectly-parked burst look like a leak
        pg.evaluate("stopDashboard()")
        looks = ([('world', w) for w in pg.evaluate("Object.keys(ST.worlds||{})")]
                 + [('skin', k) for k in pg.evaluate("ST.classic_skins||[]")])
        for kind, sk in looks:
            if kind == 'world':
                pg.evaluate(f"ST.world='{sk}';applyTheme(ST.theme)")
            else:
                pg.evaluate(f"ST.world='';ST.skin='{sk}';applyTheme(ST.theme)")
            pg.wait_for_timeout(350)
            pg.evaluate("MO.burst(document.querySelector('.d-continue'))")
            pg.wait_for_timeout(100)
            mounted_n = pg.evaluate("document.querySelectorAll('.burst').length")
            nodes = pg.evaluate("document.querySelectorAll('.burst i').length")
            gone = True
            try:
                # a burst must outlast neither the action it marks nor 2s
                pg.wait_for_function(
                    "document.querySelectorAll('.burst').length===0", timeout=2000)
            except Exception:
                gone = False
            pg.wait_for_timeout(500)
            parked = pg.evaluate("MO._raf===null")
            check(f'burst {sk}', mounted_n == 1 and nodes > 0 and gone and parked,
                  f'mounted={mounted_n} nodes={nodes} cleaned={gone} parked={parked}')
        pg.evaluate("MO.set('subtle');MO.burst(document.querySelector('.d-continue'))")
        pg.wait_for_timeout(150)
        check('no burst at motion=subtle',
              pg.evaluate("document.querySelectorAll('.burst').length") == 0)
        pg.evaluate("MO.set('full');ST.world='';ST.skin='';applyTheme(ST.theme);startDashboard()")

        print('\n— narrow window —')
        pg.set_viewport_size({'width': 700, 'height': 900})
        pg.wait_for_timeout(800)
        cols = pg.evaluate("getComputedStyle(document.querySelector('.app')).gridTemplateColumns")
        check('sidebar collapsed to an icon rail', cols.startswith('64px'), cols)
        sizes = pg.evaluate("INST.reg.map(t=>t.cv.clientWidth+'x'+t.cv.clientHeight)")
        check('gauges re-fitted',
              all(int(s.split('x')[0]) > 20 and int(s.split('x')[1]) > 20 for s in sizes),
              sizes)
        pg.set_viewport_size({'width': 1600, 'height': 1000})

        print('\n— every theme applies —')
        bad = pg.evaluate("""(()=>{const out=[];
          for(const n of Object.keys(ST.themes)){
            try{applyTheme(n);
              const c=getComputedStyle(document.documentElement);
              if(!c.getPropertyValue('--mo-lift').trim())out.push(n+':nolift');
            }catch(e){out.push(n+':'+e.message);}}
          return out;})()""")
        check('all palettes apply with a personality', bad == [], bad)

        print(chr(10) + '— shader attributes —')
        # A vertex shader can declare `attribute float li` while the geometry
        # never sets it: WebGL reads 0 for every vertex, nothing errors, and the
        # object silently collapses. That is how the graph's connecting lines
        # disappeared — every segment pinned to node 0, so zero length. Compare
        # what each shader asks for against what its geometry actually has.
        missing = pg.evaluate("""(()=>{
          const out=[];
          for(const w of Object.keys(ST.worlds||{})){
            ST.world=w; applyTheme(ST.theme);
            if(!STAGE._sc) continue;
            STAGE._sc.scene.traverse(o=>{
              if(!o.material||!o.material.vertexShader||!o.geometry)return;
              const want=[...o.material.vertexShader.matchAll(
                /^\s*attribute\s+\w+\s+(\w+)\s*;/gm)].map(m=>m[1]);
              const have=Object.keys(o.geometry.attributes);
              const builtin=['position','normal','uv','color'];
              for(const a of want)
                if(!have.includes(a)&&!builtin.includes(a))
                  out.push(w+':'+o.type+':'+a);
            });
          }
          ST.world=''; applyTheme(ST.theme); return out;})()""")
        check('no shader reads an attribute its geometry never set',
              missing == [], missing)

        br.close()
    srv.shutdown()

    print('\nJS errors:', errs if errs else 'none')
    print('FAILURES:', fails if fails else 'none')
    return 1 if (fails or errs) else 0


if __name__ == '__main__':
    raise SystemExit(main())
