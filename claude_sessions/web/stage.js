'use strict';
/* ── stage: the background ──────────────────────────────────────────────────
   ONE canvas, full viewport, behind everything, for the whole app.

   Read the history before changing this, because it looks like a rule this
   project already broke once. The layer that was deleted was 26 generative
   renderers mounted into ~30 places — a band above every page PLUS a micro
   canvas in every sidebar row, nav item, header chip and quota meter — each
   looping at 6-30fps whether or not anything had happened. The complaint was
   "animated everywhere", and it was correct.

   This is the opposite shape:

     ONE surface, not thirty.   Nothing inside a row, card or chip animates.
     Behind, not between.       z-index:-1, pointer-events:none, aria-hidden.
     Driven by state, not free. Idle crawls; a running job accelerates it; a
                                launch shocks it; navigation ripples it. The
                                motion means something or it does not happen.
     It stops.                  Hidden, blurred (Qt minimise), motion:off,
                                stage:off, reduced-motion, context lost.

   Cost discipline, given that QtWebEngine composites through a GPU hardware
   surface and this adds a second one:

     · Opaque canvas (alpha:false). A transparent surface has to be blended with
       the page underneath on every composite; an opaque one is a straight blit,
       and the scene clears to --bg so the result is identical.
     · No CSS filter / backdrop-filter / mix-blend-mode anywhere near it. All
       glow is done in GL, which is precisely why bloom is affordable here and a
       CSS blur never was (tests/test_gui_flicker.py forbids the CSS form).
     · Render scale below 1 and devicePixelRatio deliberately IGNORED. A soft
       full-screen field does not need 4x the fill on a 4K panel — unlike the
       instruments' hairline arcs, which is why those clamp to 2 instead.
     · Every scene is ONE or TWO draw calls over a pre-built merged geometry,
       animated entirely in the vertex/fragment shader. Per frame the CPU sets a
       handful of uniforms and nothing else. No per-object matrix updates, no
       per-particle JS, no allocation.
     · Instancing is done by merging rather than InstancedMesh, on purpose: a
       raw ShaderMaterial plus InstancedMesh puts you at the mercy of whether
       three injects `attribute mat4 instanceMatrix` into your prefix, which has
       moved between versions. A merged buffer is one draw call either way.
     · No second rAF chain. The stage registers into MO.frame like everything
       else, and MO.frame is also what drives anime's engine.

   Fail-open at every step: no vendor bundle, no WebGL, or a lost context all
   land on the static CSS gradient (html.stage-off) with the app untouched. */

const STAGE_SCALE = 0.75;      // render scale; scenes may raise it for crisp lines
const STAGE_FPS_IDLE = 20;     // nothing is happening — a crawl is enough
const STAGE_FPS_BUSY = 34;     // a job is running
const STAGE_ENERGY_TAU = 0.9;  // seconds for energy to close ~63% of a change
const STAGE_SHOCK_S = 1.15;    // launch shockwave decay
const STAGE_PULSE_S = 0.8;     // navigation ripple decay

/* Per-page character. The canvas is global and never restarts across
   navigation — that is what makes it one stage rather than seven wallpapers —
   but each page tilts it. `d` is density/intensity, `c` biases the camera. */
const STAGE_PAGES = {
  home:     {d: 1.00, c: 0.00},
  sessions: {d: 0.82, c: 0.35},
  usage:    {d: 0.70, c: -0.30},
  memory:   {d: 0.55, c: 0.15},
  plan:     {d: 0.90, c: 0.55},
  settings: {d: 0.34, c: -0.55},
  help:     {d: 0.30, c: -0.20},
};
function stagePage(name) { return STAGE_PAGES[name] || {d: 0.62, c: 0.1}; }

/* Shared vertex shader for the screen-filling backdrop each scene sits on.
   Writes clip space directly, so it fills the viewport whatever the camera is
   doing, and never needs to be positioned or culled. */
const SV_FULL = `
varying vec2 vUv;
void main(){ vUv = uv; gl_Position = vec4(position.xy * 2.0, 0.999, 1.0); }`;

/* Small GLSL toolbox shared by the scenes. Value noise rather than simplex:
   a background does not need the quality and this compiles fast everywhere. */
const SF_LIB = `
float h11(float p){ return fract(sin(p * 127.1) * 43758.5453123); }
float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1,0)), u.x),
             mix(h21(i + vec2(0,1)), h21(i + vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5;
  for(int i = 0; i < 4; i++){ v += a * vnoise(p); p *= 2.03; a *= 0.5; }
  return v;
}`;

const STAGE = {
  /* cinematic | lite | off. `lite` drops bloom (and with it two extra render
     targets), which is the first thing to try if the Qt shell ever tears. */
  tier: 'cinematic',
  scene: 'hud',
  ok: false,          // a live GL scene is mounted
  failed: false,      // gave up for this page load; never retry in a loop

  _pal: null, _pageKey: 'home',
  _E: 0, _Etgt: 0, _shock: 0, _pulse: 0, _dens: 1, _densTgt: 1, _cam: 0, _camTgt: 0,
  _T: 0, _acc: 0, _job: null,
  _th: null, _ren: null, _post: null, _sc: null, _canvas: null,

  /* ── lifecycle ────────────────────────────────────────────────────────── */
  boot() {
    if (this.failed || this.ok) return;
    const TH = window.THREE;
    const cv = document.getElementById('stage');
    if (!TH || !cv) return;
    if (this.tier === 'off' || !MO.on) { this._static(); return; }
    try {
      const ren = new TH.WebGLRenderer({
        canvas: cv, alpha: false, antialias: false, depth: true, stencil: false,
        powerPreference: 'high-performance', preserveDrawingBuffer: false,
        failIfMajorPerformanceCaveat: false,
      });
      ren.setPixelRatio(STAGE_SCALE);
      ren.autoClear = true;
      this._th = TH; this._ren = ren; this._canvas = cv;
      // QtWebEngine does lose contexts (tab suspend, driver reset). Losing the
      // background must never take the app with it.
      cv.addEventListener('webglcontextlost', e => {
        e.preventDefault(); this._giveUp('context lost');
      }, {once: true});
      this.ok = true;
      this.build();
    } catch (e) {
      console.warn('[stage] WebGL unavailable', e);
      this._giveUp('no webgl');
    }
  },

  /* the fallback is not a degraded stage, it is the static gradient the app
     shipped with — body::before/::after, still in app.css for exactly this.

     Those washes are the DEFAULT, not the exception: they paint from first
     byte, and `stage-on` is only added once GL has actually rendered a frame.
     That ordering is deliberate — the vendor bundle is deferred, so the
     alternative is a second of flat --bg before the scene appears. */
  _static() {
    const r = document.documentElement;
    r.classList.remove('stage-on'); r.classList.add('stage-off');
  },
  _live() {
    const r = document.documentElement;
    r.classList.remove('stage-off'); r.classList.add('stage-on');
  },
  _giveUp(why) {
    this.failed = true; this.ok = false;
    this._teardown();
    if (this._ren) { try { this._ren.dispose(); } catch (e) {} this._ren = null; }
    this._static();
    if (why !== 'off') console.warn('[stage] disabled:', why);
  },

  _teardown() {
    if (this._sc && this._sc.dispose) { try { this._sc.dispose(); } catch (e) {} }
    this._sc = null;
    if (this._post) { try { this._post.dispose(); } catch (e) {} this._post = null; }
  },

  /* (re)build for the current skin + palette. Called on theme change, skin
     change and tier change — i.e. every time the picker is hovered, so the
     teardown above has to actually free the GPU buffers. */
  build() {
    if (!this.ok || !this._ren) return;
    const TH = this._th;
    this._teardown();
    const mk = STAGE_SCENES[this.scene] || STAGE_SCENES.hud;
    try {
      this._sc = mk(TH, this._colors());
    } catch (e) { this._giveUp('scene build failed: ' + e.message); return; }
    this._ren.setPixelRatio(this._sc.scale || STAGE_SCALE);
    this._ren.setClearColor(this._colors().bg, 1);
    this.resize();
    this._mkPost();
    this.kick();
  },

  /* bloom, cinematic tier only. Two extra render targets, so `lite` skips the
     composer entirely rather than setting its strength to zero.

     The threshold matters more than the strength. At 0.2 essentially every lit
     pixel blooms, and a neon scene turns into an undifferentiated colour spill —
     you can see the glow but not the city. At 0.55 only the genuinely bright
     things (window rows, rooftop edges, the radar sweep) bleed, which is what
     bloom is for. */
  _mkPost() {
    this._post = null;
    const P = window.THREE_POST, sc = this._sc;
    if (!P || this.tier !== 'cinematic' || !sc) return;
    // the skin's value wins: themes.py owns how hot each look runs
    const strength = this.bloomOf != null ? this.bloomOf : sc.bloom;
    if (!strength) return;
    try {
      const TH = this._th, r = this._ren;
      const sz = new TH.Vector2(); r.getSize(sz);
      const c = new P.EffectComposer(r);
      c.addPass(new P.RenderPass(sc.scene, sc.camera));
      c.addPass(new P.UnrealBloomPass(sz, strength, 0.5, 0.55));
      c.addPass(new P.OutputPass());
      c.setSize(sz.x, sz.y);
      this._post = c;
    } catch (e) { console.warn('[stage] bloom unavailable', e); this._post = null; }
  },

  _colors() {
    const TH = this._th, p = this._pal || {};
    const C = h => new TH.Color(h || '#7dcfff');
    return {
      acc: C(p.accent), acc2: C(p.accent2), glow: C(p.glow || p.accent),
      bg: C(p.bg), panel: C(p.panel || p.bg), warn: C(p.warn),
      light: p.mode === 'light',
    };
  },

  /* ── inputs from the app ──────────────────────────────────────────────── */
  setTheme(pal) { this._pal = pal; if (this.ok) this.build(); },
  setSkin(name, skin) {
    const next = (skin && skin.stage) || 'hud';
    this.bloomOf = skin ? skin.bloom : 1;
    if (next === this.scene && this.ok) return;
    this.scene = next;
    if (this.ok) this.build();
  },
  setTier(tier) {
    this.tier = tier || 'cinematic';
    if (this.tier === 'off') {
      this.stop(); this._teardown(); this.ok = false; this._painted = false;
      this._static();
      return;
    }
    document.documentElement.classList.remove('stage-off');
    // an explicit re-enable clears a previous give-up: the user is asking again,
    // and the reason (a lost context, a driver hiccup) may well have passed
    this.failed = false;
    if (!this.ok) this.boot(); else { this._mkPost(); this.kick(); }
  },

  /* 0..1, how busy the workspace is. Pushed by the renderers that already have
     the numbers — the stage never issues a request of its own, same rule the
     instruments follow. */
  energy(n) {
    n = Math.max(0, Math.min(1, Number(n) || 0));
    if (Math.abs(n - this._Etgt) < 0.01) return;
    this._Etgt = n;
    this.kick();
  },
  /* the launch moment */
  shock() { this._shock = 1; this.kick(); },
  /* navigation */
  impulse() { this._pulse = 1; this.kick(); },
  page(name) {
    const p = stagePage(name);
    this._pageKey = name; this._densTgt = p.d; this._camTgt = p.c;
    this.kick();
  },

  /* ── the frame job ────────────────────────────────────────────────────────
     Registered into MO.frame and kept there while the stage is on. It does NOT
     unregister on blur — MO's own loop already refuses to reschedule while
     hidden or !vis, so the chain parks and resumes without the stage knowing.
     It returns false only when the stage genuinely stops. */
  kick() {
    if (!this.ok || this._job || !MO.on || this.tier === 'off') return;
    this._job = MO.frame(dt => this._tick(dt));
  },
  stop() {
    if (this._job) { MO.unframe(this._job); this._job = null; }
  },

  _tick(dt) {
    if (!this.ok || !this._ren || !this._sc || this.tier === 'off' || !MO.on) {
      this._job = null; return false;
    }
    // energy first: it sets the frame cap, so a burst of work speeds up the
    // very frame that notices it
    const k = 1 - Math.exp(-dt / STAGE_ENERGY_TAU);
    this._E += (this._Etgt - this._E) * k;
    this._dens += (this._densTgt - this._dens) * k;
    this._cam += (this._camTgt - this._cam) * k;
    if (this._shock > 0) this._shock = Math.max(0, this._shock - dt / STAGE_SHOCK_S);
    if (this._pulse > 0) this._pulse = Math.max(0, this._pulse - dt / STAGE_PULSE_S);

    const fps = STAGE_FPS_IDLE + (STAGE_FPS_BUSY - STAGE_FPS_IDLE) * this._E;
    this._acc += dt;
    if (this._acc < 1 / fps) return true;
    const fdt = this._acc; this._acc = 0;

    // scene time runs slow when idle and fast when busy — this, not opacity, is
    // what makes "the workspace is working" legible at a glance
    this._T += fdt * (0.3 + 1.7 * this._E + 1.2 * this._shock);

    const sc = this._sc;
    try {
      sc.update({t: this._T, dt: fdt, e: this._E, shock: this._shock,
                 pulse: this._pulse, dens: this._dens, cam: this._cam});
      if (this._post) this._post.render(fdt);
      else this._ren.render(sc.scene, sc.camera);
    } catch (e) { this._giveUp('render failed: ' + e.message); return false; }
    // only now is it safe to drop the static wash — a frame has landed
    if (!this._painted) { this._painted = true; this._live(); }
    return true;
  },

  resize() {
    if (!this.ok || !this._ren || !this._sc) return;
    const w = window.innerWidth, h = window.innerHeight;
    this._ren.setSize(w, h, false);
    if (this._sc.resize) this._sc.resize(w, h);
    if (this._post) {
      const sz = new this._th.Vector2(); this._ren.getSize(sz);
      this._post.setSize(sz.x, sz.y);
    }
  },
};

/* ── scene toolkit ────────────────────────────────────────────────────────── */

/* One draw call, screen-filling, always behind. Every scene lays its
   foreground over one of these rather than showing the flat clear colour. */
function sBackdrop(TH, frag, uniforms) {
  const m = new TH.ShaderMaterial({
    vertexShader: SV_FULL, fragmentShader: frag, uniforms,
    depthTest: false, depthWrite: false,
  });
  const q = new TH.Mesh(new TH.PlaneGeometry(1, 1), m);
  q.frustumCulled = false;
  q.renderOrder = -10;
  return q;
}

/* Merge n copies of a template geometry into one buffer, tagging each copy with
   per-copy attributes. This is how every "instanced" scene here is built: one
   draw call, and the per-copy data lives in attributes the vertex shader reads,
   so animating 4000 boxes costs one uniform write. */
function sMerge(TH, tmpl, n, attrs, place) {
  const pos = tmpl.getAttribute('position');
  const nrm = tmpl.getAttribute('normal');
  const idx = tmpl.getIndex();
  const vc = pos.count;
  const iCount = idx ? idx.count : 0;
  const P = new Float32Array(vc * n * 3);
  const N = nrm ? new Float32Array(vc * n * 3) : null;
  const I = iCount ? new Uint32Array(iCount * n) : null;
  const A = {};
  for (const k in attrs) A[k] = new Float32Array(vc * n * attrs[k]);

  const o = {p: [0, 0, 0], s: [1, 1, 1], a: {}};
  for (let i = 0; i < n; i++) {
    o.p[0] = o.p[1] = o.p[2] = 0; o.s[0] = o.s[1] = o.s[2] = 1; o.a = {};
    place(i, o);
    for (let v = 0; v < vc; v++) {
      const d = (i * vc + v) * 3;
      P[d]     = pos.getX(v) * o.s[0] + o.p[0];
      P[d + 1] = pos.getY(v) * o.s[1] + o.p[1];
      P[d + 2] = pos.getZ(v) * o.s[2] + o.p[2];
      if (N) { N[d] = nrm.getX(v); N[d + 1] = nrm.getY(v); N[d + 2] = nrm.getZ(v); }
      for (const k in attrs) {
        const w = attrs[k], src = o.a[k];
        for (let c = 0; c < w; c++) A[k][(i * vc + v) * w + c] = src ? src[c] : 0;
      }
    }
    if (I) for (let e = 0; e < iCount; e++) I[i * iCount + e] = idx.getX(e) + i * vc;
  }
  const g = new TH.BufferGeometry();
  g.setAttribute('position', new TH.BufferAttribute(P, 3));
  if (N) g.setAttribute('normal', new TH.BufferAttribute(N, 3));
  for (const k in attrs) g.setAttribute(k, new TH.BufferAttribute(A[k], attrs[k]));
  if (I) g.setIndex(new TH.BufferAttribute(I, 1));
  return g;
}

/* every scene returns this shape; dispose() has to free everything it made,
   because the settings picker rebuilds on hover */
function sScene(TH, camera, bloom, scale) {
  const scene = new TH.Scene();
  const bag = [];
  return {
    scene, camera, bloom, scale,
    add(o) { scene.add(o); bag.push(o); return o; },
    dispose() {
      for (const o of bag) {
        scene.remove(o);
        if (o.geometry) o.geometry.dispose();
        if (o.material) o.material.dispose();
      }
      bag.length = 0;
    },
  };
}
function sU(TH, c) {
  return {
    u_t: {value: 0}, u_e: {value: 0}, u_shock: {value: 0}, u_pulse: {value: 0},
    u_dens: {value: 1}, u_res: {value: new TH.Vector2(1, 1)},
    u_acc: {value: c.acc}, u_acc2: {value: c.acc2}, u_glow: {value: c.glow},
    u_bg: {value: c.bg}, u_panel: {value: c.panel}, u_warn: {value: c.warn},
    u_light: {value: c.light ? 1 : 0},
  };
}
function sFeed(u, f) {
  u.u_t.value = f.t; u.u_e.value = f.e; u.u_shock.value = f.shock;
  u.u_pulse.value = f.pulse; u.u_dens.value = f.dens;
}

/* ── the seven scenes ─────────────────────────────────────────────────────── */

const STAGE_SCENES = {

  /* HUD — an instrument horizon. A wireframe ground plane racing to a vanishing
     point, concentric range rings, and a radar sweep that comes round faster
     the busier the workspace is. */
  hud(TH, c) {
    // 1.0 scale: this scene is all 1px lines, which is the one case where the
    // reduced render scale is visible as mush
    const cam = new TH.PerspectiveCamera(62, 1, 0.1, 90);
    const S = sScene(TH, cam, 0.55, 1.0);
    const u = sU(TH, c);

    S.add(sBackdrop(TH, `
      ${SF_LIB}
      varying vec2 vUv; uniform vec3 u_bg,u_acc,u_acc2; uniform float u_t,u_e,u_light;
      void main(){
        vec2 p = vUv - 0.5;
        float sky = smoothstep(-0.05, 0.55, vUv.y);
        vec3 col = mix(u_bg, mix(u_bg, u_acc2, 0.16), sky);
        // horizon bloom, brighter when there is work happening
        col += u_acc * (0.14 + 0.22 * u_e) * exp(-abs(vUv.y - 0.5) * 9.0);
        col += u_acc2 * 0.05 * fbm(p * 3.0 + u_t * 0.03);
        gl_FragColor = vec4(col, 1.0);
      }`, u));

    // ground grid — one LineSegments, scrolled in the vertex shader
    const N = 46, EXT = 34;
    const gp = [];
    for (let i = 0; i <= N; i++) {
      const x = -EXT + (2 * EXT) * (i / N);
      gp.push(x, 0, -EXT, x, 0, EXT);
      const z = -EXT + (2 * EXT) * (i / N);
      gp.push(-EXT, 0, z, EXT, 0, z);
    }
    const gg = new TH.BufferGeometry();
    gg.setAttribute('position', new TH.Float32BufferAttribute(gp, 3));
    const grid = new TH.LineSegments(gg, new TH.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false,
      vertexShader: `
        varying float vF; varying vec3 vP;
        uniform float u_t,u_e;
        void main(){
          vec3 p = position;
          p.z = mod(p.z + u_t * (1.4 + 5.0 * u_e) + 34.0, 68.0) - 34.0;
          vP = p;
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vF = clamp(1.0 - (-mv.z) / 34.0, 0.0, 1.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        varying float vF; varying vec3 vP;
        uniform vec3 u_acc,u_acc2; uniform float u_e,u_shock;
        void main(){
          float a = pow(vF, 2.2) * (0.42 + 0.3 * u_e);
          // the shockwave: a bright ring expanding out of the origin
          float r = length(vP.xz);
          a += u_shock * exp(-abs(r - (1.0 - u_shock) * 30.0) * 0.8) * 1.4;
          vec3 col = mix(u_acc, u_acc2, clamp(vP.x * 0.02 + 0.5, 0.0, 1.0));
          gl_FragColor = vec4(col * (1.0 + u_shock), a);
        }`,
    }));
    grid.position.y = -1.5;
    S.add(grid);

    // range rings + sweep, lying on the plane ahead
    const rp = [];
    for (let k = 1; k <= 5; k++) {
      const rad = k * 2.6, seg = 96;
      for (let i = 0; i < seg; i++) {
        const a0 = (i / seg) * Math.PI * 2, a1 = ((i + 1) / seg) * Math.PI * 2;
        rp.push(Math.cos(a0) * rad, 0, Math.sin(a0) * rad,
                Math.cos(a1) * rad, 0, Math.sin(a1) * rad);
      }
    }
    const rg = new TH.BufferGeometry();
    rg.setAttribute('position', new TH.Float32BufferAttribute(rp, 3));
    const rings = new TH.LineSegments(rg, new TH.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false,
      vertexShader: `
        varying vec3 vP; void main(){ vP = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `
        varying vec3 vP; uniform vec3 u_acc; uniform float u_t,u_e,u_dens;
        void main(){
          // the sweep: a bright arc rotating round the rings
          float ang = atan(vP.z, vP.x);
          float sweep = fract((ang + 3.14159) / 6.28318 + u_t * (0.05 + 0.16 * u_e));
          float lit = pow(1.0 - sweep, 7.0);
          float a = (0.13 + 0.75 * lit) * u_dens;
          gl_FragColor = vec4(u_acc * (0.8 + lit), a);
        }`,
    }));
    rings.position.set(0, -1.48, -9);
    S.add(rings);

    S.update = f => {
      sFeed(u, f);
      cam.position.set(Math.sin(f.t * 0.05) * 1.6 + f.cam * 2.4, 1.1 + f.cam * 0.5, 7.5);
      cam.lookAt(0, -0.9, -12);
    };
    S.resize = (w, h) => {
      u.u_res.value.set(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    return S;
  },

  /* Sakura — a drifting petal field. Every petal's whole trajectory is a
     function of its seed and the clock, computed in the vertex shader, so 1800
     of them cost one uniform write per frame and no JS at all. */
  sakura(TH, c) {
    const cam = new TH.PerspectiveCamera(60, 1, 0.1, 60);
    cam.position.set(0, 0, 10);
    const S = sScene(TH, cam, 0.5, STAGE_SCALE);
    const u = sU(TH, c);

    S.add(sBackdrop(TH, `
      ${SF_LIB}
      varying vec2 vUv; uniform vec3 u_bg,u_acc,u_acc2; uniform float u_t,u_e,u_light;
      void main(){
        vec2 p = vUv;
        // two slow blooms crossing, the wash those soft dashboards sit on
        float a = fbm(p * 1.7 + vec2(u_t * 0.035, u_t * 0.02));
        float b = fbm(p * 2.3 - vec2(u_t * 0.025, u_t * 0.04) + 5.0);
        vec3 col = u_bg;
        col = mix(col, u_acc,  a * (0.20 + 0.14 * u_e));
        col = mix(col, u_acc2, b * (0.16 + 0.12 * u_e));
        col += u_acc * 0.10 * pow(1.0 - distance(p, vec2(0.5, 0.75)), 3.0);
        gl_FragColor = vec4(col, 1.0);
      }`, u));

    const N = 1800;
    const seed = new Float32Array(N * 4);
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      seed[i * 4] = Math.random();          // x lane
      seed[i * 4 + 1] = Math.random();      // fall phase
      seed[i * 4 + 2] = Math.random();      // sway rate
      seed[i * 4 + 3] = 0.4 + Math.random() * 0.9;  // size
      pos[i * 3 + 2] = -1 - Math.random() * 16;     // depth
    }
    const pg = new TH.BufferGeometry();
    pg.setAttribute('position', new TH.BufferAttribute(pos, 3));
    pg.setAttribute('seed', new TH.BufferAttribute(seed, 4));
    const pts = new TH.Points(pg, new TH.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false,
      blending: TH.AdditiveBlending,
      vertexShader: `
        attribute vec4 seed; varying float vA; varying float vS;
        uniform float u_t,u_e,u_dens,u_shock; uniform vec2 u_res;
        void main(){
          float sp = 0.35 + 0.9 * u_e + 2.2 * u_shock;
          float fall = fract(seed.y + u_t * sp * (0.05 + seed.z * 0.05));
          float x = (seed.x - 0.5) * 26.0 + sin(u_t * seed.z * 0.7 + seed.x * 20.0) * 1.6;
          float y = 9.0 - fall * 20.0;
          vec3 p = vec3(x, y, position.z);
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          vS = seed.w;
          gl_PointSize = seed.w * (140.0 / max(1.0, -mv.z)) * (u_res.y / 900.0 + 0.55);
          // fade in at the top, out at the bottom — nothing pops
          vA = smoothstep(0.0, 0.12, fall) * (1.0 - smoothstep(0.75, 1.0, fall)) * u_dens;
        }`,
      fragmentShader: `
        varying float vA; varying float vS;
        uniform vec3 u_acc,u_acc2;
        void main(){
          vec2 q = gl_PointCoord - 0.5;
          // petal: a soft lens shape, not a round dot
          float d = length(vec2(q.x * 1.5, q.y));
          float m = smoothstep(0.5, 0.06, d);
          if(m < 0.01) discard;
          vec3 col = mix(u_acc, u_acc2, vS * 0.7);
          gl_FragColor = vec4(col, m * vA * 0.55);
        }`,
    }));
    S.add(pts);

    S.update = f => {
      sFeed(u, f);
      cam.position.x = f.cam * 1.8;
      cam.position.y = Math.sin(f.t * 0.06) * 0.4;
      cam.lookAt(0, 0, 0);
    };
    S.resize = (w, h) => {
      u.u_res.value.set(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    return S;
  },

  /* Mecha — a hexagonal panel wall that lights in hard blocks. No easing
     anywhere: cells snap between states, which is the whole personality. */
  mecha(TH, c) {
    const cam = new TH.PerspectiveCamera(52, 1, 0.1, 70);
    cam.position.set(0, 0, 13);
    const S = sScene(TH, cam, 0.35, STAGE_SCALE);
    const u = sU(TH, c);

    S.add(sBackdrop(TH, `
      varying vec2 vUv; uniform vec3 u_bg,u_warn; uniform float u_t,u_e,u_shock;
      void main(){
        vec2 p = vUv * vec2(2.4, 1.0);
        // hazard stripes scrolling behind the wall, stepped not smooth
        float s = step(0.5, fract((p.x + p.y) * 6.0 - u_t * (0.06 + 0.3 * u_e)));
        vec3 col = mix(u_bg, mix(u_bg, u_warn, 0.10), s);
        col = mix(col, u_warn, u_shock * 0.18 * s);
        gl_FragColor = vec4(col, 1.0);
      }`, u));

    // hex-packed grid of flat hexagons, merged into one buffer
    const COLS = 26, ROWS = 16, R = 0.62;
    const tmpl = new TH.CircleGeometry(R * 0.92, 6);
    const g = sMerge(TH, tmpl, COLS * ROWS, {cell: 2}, (i, o) => {
      const cx = i % COLS, cy = (i / COLS) | 0;
      o.p[0] = (cx - COLS / 2) * R * 1.74 + (cy % 2 ? R * 0.87 : 0);
      o.p[1] = (cy - ROWS / 2) * R * 1.5;
      o.p[2] = 0;
      o.a.cell = [cx / COLS, cy / ROWS];
    });
    const wall = new TH.Mesh(g, new TH.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false,
      vertexShader: `
        attribute vec2 cell; varying vec2 vC;
        void main(){ vC = cell;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `
        ${SF_LIB}
        varying vec2 vC;
        uniform vec3 u_acc,u_acc2,u_warn,u_panel;
        uniform float u_t,u_e,u_shock,u_pulse,u_dens;
        void main(){
          float id = h21(floor(vC * vec2(26.0, 16.0)));
          // hard stepped activation: a cell is on or off, never in between
          float beat = step(0.62 - 0.32 * u_e, fract(id * 7.13 + floor(u_t * (0.9 + 2.4 * u_e)) * 0.37));
          // a scan column marching across the wall
          float col_ = step(0.93, fract(vC.x - u_t * 0.11));
          float sh = u_shock * step(abs(distance(vC, vec2(0.5)) - (1.0 - u_shock) * 0.8), 0.06);
          vec3 base = mix(u_panel, u_acc, 0.10);
          vec3 col = mix(base, u_acc, beat * 0.55);
          col = mix(col, u_acc2, col_ * 0.8);
          col = mix(col, u_warn, sh);
          // most cells sit near-dark so the lit ones read as an event; a wall
          // where every cell is half-on is a texture, not a console
          float a = (0.14 + 0.34 * beat + 0.45 * col_ + sh) * u_dens;
          gl_FragColor = vec4(col, a);
        }`,
    }));
    S.add(wall);

    S.update = f => {
      sFeed(u, f);
      // the camera steps rather than glides — quantised to the beat
      cam.position.x = Math.round(f.cam * 3.0 + Math.sin(f.t * 0.08) * 2.0);
      cam.position.z = 13 - f.e * 1.5;
      cam.lookAt(0, 0, 0);
    };
    S.resize = (w, h) => {
      u.u_res.value.set(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    return S;
  },

  /* Neon City — an endless flythrough. Boxes are merged once and scrolled by
     the vertex shader with a modulo, so the tunnel is infinite for free. */
  'neon-city'(TH, c) {
    const cam = new TH.PerspectiveCamera(72, 1, 0.1, 130);
    const S = sScene(TH, cam, 1.35, STAGE_SCALE);
    const u = sU(TH, c);
    const SPAN = 120;

    S.add(sBackdrop(TH, `
      ${SF_LIB}
      varying vec2 vUv; uniform vec3 u_bg,u_acc,u_acc2; uniform float u_t,u_e;
      void main(){
        // deliberately dim: the sky is a backdrop for the skyline, not a light
        // source. Everything bright in this scene should be geometry.
        vec3 col = mix(u_bg, mix(u_bg, u_acc2, 0.13), pow(vUv.y, 1.8));
        col += u_acc * 0.05 * exp(-abs(vUv.y - 0.42) * 9.0);
        col += u_acc2 * 0.025 * fbm(vUv * 4.0 + vec2(0.0, -u_t * 0.05));
        gl_FragColor = vec4(col, 1.0);
      }`, u));

    const N = 260;
    const tmpl = new TH.BoxGeometry(1, 1, 1);
    const g = sMerge(TH, tmpl, N, {bx: 4}, (i, o) => {
      const side = i % 2 ? 1 : -1;
      const lane = 5.5 + Math.random() * 16;
      const hgt = 3 + Math.pow(Math.random(), 1.7) * 26;
      o.s[0] = 1.6 + Math.random() * 3.2;
      o.s[1] = hgt;
      o.s[2] = 1.6 + Math.random() * 3.2;
      o.p[0] = side * lane;
      o.p[1] = hgt / 2 - 6;
      o.p[2] = -Math.random() * SPAN;
      o.a.bx = [Math.random(), hgt, Math.random(), side];
    });
    const city = new TH.Mesh(g, new TH.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: true,
      vertexShader: `
        attribute vec4 bx; varying vec4 vB; varying vec3 vL; varying float vFog;
        uniform float u_t,u_e,u_shock,u_dens;
        void main(){
          vec3 p = position;
          float sp = u_t * (3.0 + 14.0 * u_e + 26.0 * u_shock);
          p.z = mod(p.z + sp, ${SPAN}.0) - ${SPAN}.0 + 8.0;
          vB = bx;
          vL = position;                       // local, for the window rows
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vFog = clamp(1.0 - (-mv.z) / ${SPAN}.0, 0.0, 1.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        ${SF_LIB}
        varying vec4 vB; varying vec3 vL; varying float vFog;
        uniform vec3 u_acc,u_acc2,u_bg; uniform float u_t,u_e,u_dens;
        void main(){
          // lit window rows up the face — what actually reads as a city
          float rows = step(0.55, fract(vL.y * 2.6));
          float cols = step(0.45, fract(vL.x * 3.1 + vB.x * 10.0));
          float lit = rows * cols * step(0.35, h11(floor(vL.y * 2.6) * 13.0 + vB.z * 91.0));
          vec3 neon = mix(u_acc, u_acc2, vB.w * 0.5 + 0.5);
          // The face stays DARK. A city at night is mostly unlit concrete with
          // bright windows punched through it — make the whole face glow and
          // bloom turns the scene into one coloured smear with no buildings in
          // it, which is exactly what the first cut looked like.
          vec3 col = u_bg * 0.7;
          col = mix(col, neon, lit * (0.7 + 0.3 * u_e));
          // rooftop edge: a thin bright rim, the one thing bloom should catch
          col += neon * smoothstep(0.46, 0.5, vL.y) * (0.9 + 0.7 * u_e);
          float a = pow(vFog, 1.3) * u_dens;
          gl_FragColor = vec4(col, a);
        }`,
    }));
    S.add(city);

    S.update = f => {
      sFeed(u, f);
      cam.position.set(f.cam * 3.0, 1.6 + Math.sin(f.t * 0.11) * 0.7, 6);
      cam.rotation.z = Math.sin(f.t * 0.07) * 0.03 + f.pulse * 0.05;
      cam.lookAt(f.cam * 1.2, 1.0, -40);
    };
    S.resize = (w, h) => {
      u.u_res.value.set(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    return S;
  },

  /* Terminal — a curved phosphor screen. This one genuinely is a single
     full-screen shader: barrel distortion, scanlines, a rolling refresh bar,
     grain and a vignette, all of which are per-pixel by nature. */
  crt(TH, c) {
    const cam = new TH.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const S = sScene(TH, cam, 0, 1.0);
    const u = sU(TH, c);
    S.add(sBackdrop(TH, `
      ${SF_LIB}
      varying vec2 vUv;
      uniform vec3 u_bg,u_acc,u_acc2; uniform vec2 u_res;
      uniform float u_t,u_e,u_shock,u_pulse,u_dens,u_light;
      void main(){
        // barrel: the glass is curved, so the raster is too
        vec2 p = vUv * 2.0 - 1.0;
        p *= 1.0 + 0.055 * dot(p, p);
        vec2 uv = p * 0.5 + 0.5;
        if(uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0){
          gl_FragColor = vec4(u_bg * 0.35, 1.0); return;
        }
        vec3 col = u_bg;
        // drifting phosphor field — what the tube shows with no signal. This
        // has to be genuinely visible: a CRT you can only see in a screenshot
        // if you know where to look is not a CRT, it is a dark rectangle.
        float f = fbm(uv * vec2(3.0, 8.0) + vec2(u_t * 0.05, u_t * 0.11));
        col = mix(col, u_acc, f * (0.30 + 0.22 * u_e) * u_dens);
        // aperture grille: the vertical triads a real tube is made of
        col *= 0.72 + 0.28 * sin(uv.x * u_res.x * 1.05);
        // character-cell ghosts, marching a row at a time
        float cells = step(0.72 , fract(uv.x * 90.0)) * step(0.55, fract(uv.y * 42.0));
        col += u_acc * cells * 0.22 * u_dens
             * step(0.55, h21(floor(uv * vec2(90.0, 42.0)) + floor(u_t * 3.0)));
        // scanlines
        col *= 0.72 + 0.28 * sin(uv.y * u_res.y * 1.4);
        // rolling refresh bar — one pass down the tube, faster when busy
        float roll = fract(uv.y + u_t * (0.06 + 0.22 * u_e));
        col += u_acc * (0.22 + 0.2 * u_e) * pow(1.0 - roll, 9.0);
        // the launch shock: the whole raster overbrightens and snaps back
        col += u_acc2 * u_shock * 0.45;
        col += u_acc * u_pulse * 0.18 * step(0.5, fract(uv.y * 3.0 - u_t));
        // grain + vignette
        col += (h21(uv * u_res + fract(u_t) * 300.0) - 0.5) * 0.05;
        col *= 1.0 - 0.45 * pow(length(p) * 0.62, 3.0);
        gl_FragColor = vec4(col, 1.0);
      }`, u));
    S.update = f => sFeed(u, f);
    S.resize = (w, h) => u.u_res.value.set(w, h);
    return S;
  },

  /* Brutalist — a monochrome halftone grid. No colour, no bloom, no easing.
     Dots scale from a rippling field; an impulse throws a hard ring across it. */
  brutal(TH, c) {
    const cam = new TH.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const S = sScene(TH, cam, 0, 1.0);
    const u = sU(TH, c);
    S.add(sBackdrop(TH, `
      varying vec2 vUv;
      uniform vec3 u_bg,u_acc; uniform vec2 u_res;
      uniform float u_t,u_e,u_shock,u_pulse,u_dens,u_light;
      void main(){
        float asp = u_res.x / max(1.0, u_res.y);
        vec2 p = vec2(vUv.x * asp, vUv.y);
        float grid = 34.0;
        vec2 cell = fract(p * grid) - 0.5;
        vec2 id = floor(p * grid);
        // radius per dot: a slow wave, a shock ring, a nav pulse. All stepped —
        // this skin does not ease anything.
        float wave = sin(id.x * 0.4 + u_t * (0.5 + 1.6 * u_e))
                   * cos(id.y * 0.35 - u_t * (0.4 + 1.2 * u_e));
        float r = 0.22 + 0.17 * wave;
        vec2 ctr = vec2(asp * 0.5, 0.5);
        float d = distance(p, ctr);
        r += u_shock * 0.34 * exp(-abs(d - (1.0 - u_shock) * 0.9) * 9.0);
        r += u_pulse * 0.18 * step(fract(d * 6.0 - u_t), 0.4);
        r *= u_dens;
        float dot_ = step(length(cell), r);
        // hard two-tone at real contrast: brutalism is not a whisper. No
        // gradient, no antialiasing on the dot edge, one ink colour.
        vec3 ink = mix(u_acc, vec3(1.0) - u_bg, 0.35);
        gl_FragColor = vec4(mix(u_bg, ink, dot_ * 0.62), 1.0);
      }`, u));
    S.update = f => sFeed(u, f);
    S.resize = (w, h) => u.u_res.value.set(w, h);
    return S;
  },

  /* Glass — flowing caustics and thin-film iridescence on a displaced plane.
     Note what is NOT here: backdrop-filter. The refraction is computed in the
     fragment shader, so there is no framebuffer readback and nothing for the Qt
     compositor to tear on. See the Glass note in themes.py. */
  glass(TH, c) {
    const cam = new TH.PerspectiveCamera(48, 1, 0.1, 40);
    cam.position.set(0, 0, 6.2);
    const S = sScene(TH, cam, 0.75, STAGE_SCALE);
    const u = sU(TH, c);

    S.add(sBackdrop(TH, `
      ${SF_LIB}
      varying vec2 vUv; uniform vec3 u_bg,u_acc,u_acc2; uniform float u_t,u_e;
      void main(){
        float a = fbm(vUv * 2.1 + u_t * 0.02);
        vec3 col = mix(u_bg, mix(u_acc, u_acc2, a), 0.10 + 0.06 * u_e);
        gl_FragColor = vec4(col, 1.0);
      }`, u));

    const plane = new TH.Mesh(new TH.PlaneGeometry(16, 10, 120, 80),
      new TH.ShaderMaterial({
        uniforms: u, transparent: true, depthWrite: false,
        vertexShader: `
          ${SF_LIB}
          varying vec2 vUv; varying float vH;
          uniform float u_t,u_e,u_shock;
          void main(){
            vUv = uv;
            vec3 p = position;
            float w = fbm(uv * 3.0 + vec2(u_t * 0.06, -u_t * 0.04));
            float w2 = sin(uv.x * 9.0 + u_t * 0.5) * cos(uv.y * 7.0 - u_t * 0.4);
            vH = w + w2 * 0.15;
            p.z += vH * (0.5 + 0.5 * u_e) + u_shock * sin(length(uv - 0.5) * 22.0 - u_t * 6.0);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
          }`,
        fragmentShader: `
          ${SF_LIB}
          varying vec2 vUv; varying float vH;
          uniform vec3 u_acc,u_acc2,u_glow; uniform float u_t,u_e,u_dens,u_light;
          void main(){
            // caustics: the sharp bright creases where the surface focuses
            float c1 = fbm(vUv * 5.0 + vec2(u_t * 0.05, u_t * 0.03));
            float c2 = fbm(vUv * 5.0 + vec2(u_t * 0.05, u_t * 0.03) + vec2(0.06));
            float caus = pow(1.0 - abs(c1 - c2) * 26.0, 4.0);
            caus = clamp(caus, 0.0, 1.0);
            // thin-film: hue shifts with the surface slope, the way an oil film does
            float film = fract(vH * 0.8 + u_t * 0.02);
            vec3 iri = 0.5 + 0.5 * cos(6.28318 * (film + vec3(0.0, 0.33, 0.67)));
            vec3 col = mix(u_acc, u_acc2, film);
            col = mix(col, iri * u_glow, 0.35);
            float a = (0.05 + caus * 0.5 + smoothstep(0.2, 1.0, vH) * 0.12) * u_dens;
            gl_FragColor = vec4(col, a * (0.55 + 0.45 * u_e));
          }`,
      }));
    plane.rotation.x = -0.55;
    S.add(plane);

    S.update = f => {
      sFeed(u, f);
      cam.position.x = f.cam * 1.4;
      cam.position.y = -0.6 + Math.sin(f.t * 0.05) * 0.3;
      cam.lookAt(0, -0.4, 0);
    };
    S.resize = (w, h) => {
      u.u_res.value.set(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    return S;
  },
};

/* ── wiring ───────────────────────────────────────────────────────────────
   The stage only exists once the deferred module bootstrap in index.html has
   resolved. Until then (and forever, if it never does) the static CSS gradient
   is the background and nothing here has run. */
window.addEventListener('vendor-ready', () => {
  if (window.STAGE_WANT !== false) STAGE.boot();
});
window.addEventListener('vendor-failed', () => STAGE._static());
window.addEventListener('resize', () => STAGE.resize());

window.STAGE = STAGE;
