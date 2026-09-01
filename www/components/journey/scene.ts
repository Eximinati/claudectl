/**
 * The journey scene.
 *
 * Ported from claudectl's own `graph` background world (claude_sessions/web/stage.js).
 * Same vocabulary, same reasons:
 *   - wireframe dodecahedra (20 vertices, 30 edges) spinning on two axes at
 *     T*0.5 and T*0.37 with a per-node phase, exactly as connections.py's
 *     drawDodec does;
 *   - a lit joint at every vertex;
 *   - hairline links carrying packets;
 *   - deterministic golden-angle placement (i * 2.399963, no Math.random) so the
 *     constellation is identical on every reload;
 *   - geometry MERGED into a handful of draw calls and animated entirely in the
 *     vertex shader. Merged rather than InstancedMesh on purpose: whether three
 *     injects `attribute mat4 instanceMatrix` into a raw ShaderMaterial's prefix
 *     has moved between versions.
 *
 * Everything a station "does" is one uniform driven by scroll. No CPU work per
 * frame beyond writing those uniforms and the camera.
 */
import * as THREE from 'three';

export const STATION_COUNT = 6;

/** Station centres. Spread in x/y and stepping back in z, so the finale camera
 *  can pull back far enough to hold all six in one frame. */
const P = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

const STATIONS = [
  P(0, 0, 0),
  P(-9.5, -3.4, -6),
  P(9.0, 3.6, -12.5),
  P(-8.2, 4.4, -20),
  P(8.6, -4.6, -27.5),
  P(0, -0.8, -36),
];

const RADII = [2.35, 1.5, 1.75, 1.5, 1.45, 1.3];

/** Where the camera parks for each station. The last one is the pull-back. */
const CAM = [
  P(0.7, 0.9, 7.6),
  P(-7.0, -2.4, 0.4),
  P(6.2, 2.8, -6.4),
  P(-5.9, 3.2, -14.2),
  P(6.0, -3.0, -21.4),
  P(0, 2.2, 22),
];

/** What the camera looks at. The finale looks at the constellation's middle. */
const LOOK = [...STATIONS.slice(0, 5), P(0, 0.2, -17)];

const CURVE = new THREE.CatmullRomCurve3(STATIONS, false, 'catmullrom', 0.4);
const CAM_CURVE = new THREE.CatmullRomCurve3(CAM, false, 'catmullrom', 0.5);
const LOOK_CURVE = new THREE.CatmullRomCurve3(LOOK, false, 'catmullrom', 0.5);

/* Rotate about the solid's own centre, exactly as drawDodec does: ay around Y,
   then ax around X. */
const SPIN = /* glsl */ `
  vec3 spin(vec3 local, float ph, float t){
    float ax = t * 0.5 + ph, ay = t * 0.37 + ph * 1.7;
    float ca = cos(ax), sa = sin(ax), cb = cos(ay), sb = sin(ay);
    float x = local.x * cb + local.z * sb;
    float z = -local.x * sb + local.z * cb;
    float y2 = local.y * ca - z * sa;
    float z2 = local.y * sa + z * ca;
    return vec3(x, y2, z2);
  }`;

/** Node hues, from connections.TYPE_COLORS. */
const HUES = ['#7dcfff', '#9d7bff', '#f7768e', '#73daca', '#e0af68', '#7ee787'];

/* No shader below declares its own `precision` line. three injects one into BOTH
   stages from the renderer's capabilities; a hand-written `precision mediump
   float;` in a fragment shader only overrides that half, and every uniform these
   materials SHARE between the two stages then differs in precision and the
   program fails to link — silently, on the hardware that reports highp. */
type U = Record<string, { value: unknown }>;

const uniforms = (): U => ({
  u_t: { value: 0 },
  u_prog: { value: 0 },
  u_lit: { value: 0 },
  u_frag: { value: 0 },
  u_mem: { value: 0 },
  u_shot: { value: 0 },
  u_pkt: { value: 0 },
  u_web: { value: 0 },
  u_res: { value: new THREE.Vector2(1, 1) },
  u_acc: { value: new THREE.Color(HUES[0]) },
  u_acc2: { value: new THREE.Color(HUES[1]) },
});

/** The 20 distinct vertices of a dodecahedron, deduplicated from the triangle
 *  soup three hands back — the joints have to light in a stable order, and 108
 *  overlapping points cannot give one. */
function dodecVertices(): THREE.Vector3[] {
  const g = new THREE.DodecahedronGeometry(1, 0);
  const pos = g.getAttribute('position');
  const seen = new Map<string, THREE.Vector3>();
  for (let i = 0; i < pos.count; i++) {
    const v = new THREE.Vector3().fromBufferAttribute(pos, i);
    const k = `${v.x.toFixed(3)}|${v.y.toFixed(3)}|${v.z.toFixed(3)}`;
    if (!seen.has(k)) seen.set(k, v);
  }
  g.dispose();
  // Deterministic order: by height, so "lighting one by one" reads as a sweep.
  return [...seen.values()].sort((a, b) => a.y - b.y || a.x - b.x);
}

export type Journey = {
  group: THREE.Group;
  /** Writes every uniform and the camera. The only per-frame CPU work. */
  update(camera: THREE.PerspectiveCamera, t: number, progress: number, lit: number): void;
  resize(w: number, h: number): void;
  dispose(): void;
};

export function buildJourney(): Journey {
  const u = uniforms();
  const group = new THREE.Group();
  const disposables: { dispose(): void }[] = [];
  const track = <T extends { dispose(): void }>(x: T) => (disposables.push(x), x);

  /* ── 1. the six solids, one merged LineSegments ─────────────────────────── */
  const base = new THREE.DodecahedronGeometry(1, 0);
  const wire = new THREE.EdgesGeometry(base);
  const wp = wire.getAttribute('position');
  base.dispose();

  const ePos: number[] = [], eCtr: number[] = [], eNd: number[] = [], eMid: number[] = [];
  for (let s = 0; s < STATION_COUNT; s++) {
    const c = STATIONS[s], r = RADII[s], ph = (s * 1.7) % 6.283, tone = s / STATION_COUNT;
    for (let v = 0; v < wp.count; v += 2) {
      const a = new THREE.Vector3().fromBufferAttribute(wp, v).multiplyScalar(r);
      const b = new THREE.Vector3().fromBufferAttribute(wp, v + 1).multiplyScalar(r);
      // The direction an edge flies off in when the solid fragments: outward
      // from the centre, along its own midpoint.
      const mid = a.clone().add(b).multiplyScalar(0.5).normalize();
      for (const q of [a, b]) {
        ePos.push(q.x, q.y, q.z);
        eCtr.push(c.x, c.y, c.z);
        eNd.push(ph, tone, s);
        eMid.push(mid.x, mid.y, mid.z);
      }
    }
  }
  wire.dispose();

  const gEdges = track(new THREE.BufferGeometry());
  gEdges.setAttribute('position', new THREE.Float32BufferAttribute(ePos, 3));
  gEdges.setAttribute('ctr', new THREE.Float32BufferAttribute(eCtr, 3));
  gEdges.setAttribute('nd', new THREE.Float32BufferAttribute(eNd, 3));
  gEdges.setAttribute('emid', new THREE.Float32BufferAttribute(eMid, 3));

  const mEdges = new THREE.LineSegments(
    gEdges,
    track(new THREE.ShaderMaterial({
      uniforms: u,
      transparent: true,
      depthWrite: false,
      vertexShader: /* glsl */ `
        attribute vec3 ctr; attribute vec3 nd; attribute vec3 emid;
        varying vec2 vN; varying float vD; varying float vS;
        uniform float u_t, u_frag;
        ${SPIN}
        void main(){
          vN = nd.xy; vS = nd.z;
          // Station 02 is the one that comes apart: its edges fly outward and
          // the solid stops being a solid.
          float fr = (abs(nd.z - 1.0) < 0.5) ? u_frag : 0.0;
          vec3 local = position + emid * fr * 2.6;
          vec3 p = ctr + spin(local, nd.x, u_t * (1.0 - 0.55 * fr));
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vD = clamp(1.0 - (-mv.z) / 46.0, 0.0, 1.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        varying vec2 vN; varying float vD; varying float vS;
        uniform vec3 u_acc, u_acc2;
        uniform float u_frag, u_web;
        void main(){
          float fr = (abs(vS - 1.0) < 0.5) ? u_frag : 0.0;
          vec3 col = mix(u_acc, u_acc2, vN.y);
          float a = (0.30 + 0.44 * vD) * (1.0 - 0.62 * fr) * (0.86 + 0.30 * u_web);
          gl_FragColor = vec4(col, a);
        }`,
    })),
  );
  mEdges.frustumCulled = false;
  mEdges.renderOrder = 2;
  group.add(mEdges);

  /* ── 2. the lit joint at every vertex ───────────────────────────────────── */
  const verts = dodecVertices();
  const jPos: number[] = [], jCtr: number[] = [], jNd: number[] = [], jOrd: number[] = [];
  for (let s = 0; s < STATION_COUNT; s++) {
    const c = STATIONS[s], r = RADII[s], ph = (s * 1.7) % 6.283, tone = s / STATION_COUNT;
    verts.forEach((v, k) => {
      jPos.push(v.x * r, v.y * r, v.z * r);
      jCtr.push(c.x, c.y, c.z);
      jNd.push(ph, tone, s);
      jOrd.push(k / verts.length);
    });
  }
  const gJoint = track(new THREE.BufferGeometry());
  gJoint.setAttribute('position', new THREE.Float32BufferAttribute(jPos, 3));
  gJoint.setAttribute('ctr', new THREE.Float32BufferAttribute(jCtr, 3));
  gJoint.setAttribute('nd', new THREE.Float32BufferAttribute(jNd, 3));
  gJoint.setAttribute('ord', new THREE.Float32BufferAttribute(jOrd, 1));

  const mJoint = new THREE.Points(
    gJoint,
    track(new THREE.ShaderMaterial({
      uniforms: u,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */ `
        attribute vec3 ctr; attribute vec3 nd; attribute float ord;
        varying vec2 vN; varying float vD; varying float vA;
        uniform float u_t, u_lit, u_frag, u_web; uniform vec2 u_res;
        ${SPIN}
        void main(){
          vN = nd.xy;
          vec3 p = ctr + spin(position, nd.x, u_t);
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          vD = clamp(1.0 - (-mv.z) / 46.0, 0.0, 1.0);
          // Station 01 lights its joints one by one on arrival; station 02 loses
          // them as it comes apart; the finale brings every one back up.
          float lit = (abs(nd.z) < 0.5) ? smoothstep(ord, ord + 0.22, u_lit) : 1.0;
          float dim = (abs(nd.z - 1.0) < 0.5) ? (1.0 - 0.88 * u_frag) : 1.0;
          vA = lit * dim * (0.85 + 0.45 * u_web);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = (2.2 + 3.4 * vD) * (u_res.y / 900.0 + 0.6);
        }`,
      fragmentShader: /* glsl */ `
        varying vec2 vN; varying float vD; varying float vA;
        uniform vec3 u_acc, u_acc2;
        void main(){
          float d = length(gl_PointCoord - 0.5);
          if (d > 0.5) discard;
          vec3 col = mix(u_acc, u_acc2, vN.y);
          // the white highlight drawDodec puts in the middle of each joint
          col = mix(col, vec3(1.0), smoothstep(0.28, 0.0, d) * 0.45);
          float a = (1.0 - smoothstep(0.30, 0.5, d)) * (0.30 + 0.42 * vD) * vA;
          gl_FragColor = vec4(col, a);
        }`,
    })),
  );
  mJoint.frustumCulled = false;
  mJoint.renderOrder = 3;
  group.add(mJoint);

  /* ── 3. the link: a tube along the same curve, drawn by scroll ───────────
     TubeGeometry parameterises by ARC LENGTH, but scroll progress is in
     station space (station i at i/5). getUtoTmapping is the inverse, so every
     vertex carries the station-space t of its ring and the reveal compares
     like with like. Getting this wrong makes the link lag the camera by a
     different amount on every segment. */
  const TUBULAR = 320;
  const gTube = track(new THREE.TubeGeometry(CURVE, TUBULAR, 0.05, 6, false));
  const uv = gTube.getAttribute('uv');
  const tMap = new Map<number, number>();
  const aT = new Float32Array(uv.count);
  for (let i = 0; i < uv.count; i++) {
    const uu = uv.getX(i);
    let t = tMap.get(uu);
    if (t === undefined) { t = CURVE.getUtoTmapping(uu, 0); tMap.set(uu, t); }
    aT[i] = t;
  }
  gTube.setAttribute('aT', new THREE.BufferAttribute(aT, 1));

  const mTube = new THREE.Mesh(
    gTube,
    track(new THREE.ShaderMaterial({
      uniforms: u,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */ `
        attribute float aT;
        varying float vT; varying float vD;
        void main(){
          vT = aT;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vD = clamp(1.0 - (-mv.z) / 46.0, 0.0, 1.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        varying float vT; varying float vD;
        uniform vec3 u_acc, u_acc2;
        uniform float u_t, u_prog, u_pkt, u_web;
        // a bright head with a short tail behind it, like the particles
        // connections.py runs along its edges
        float packet(float at, float head, float w){
          float d = at - head;
          float dot_ = pow(max(0.0, 1.0 - abs(d) * (34.0 / w)), 2.0);
          float tail = d < 0.0 ? pow(max(0.0, 1.0 + d * (9.0 / w)), 3.0) * 0.35 : 0.0;
          return dot_ + tail;
        }
        void main(){
          // The dash: the link only exists behind the camera's progress.
          float drawn = smoothstep(u_prog + 0.002, u_prog - 0.03, vT);
          // …with the bright packet riding the drawing front.
          float head = pow(max(0.0, 1.0 - abs(vT - u_prog) * 26.0), 2.0);
          // Station 05 is about what the links carry, so the packets fatten there.
          float w = 1.0 + 2.2 * u_pkt;
          float sp = 0.055;
          float data = packet(vT, fract(u_t * sp), w)
                     + packet(vT, fract(u_t * sp * 0.63 + 0.47), w) * 0.7;
          data *= drawn;
          vec3 col = mix(u_acc, mix(u_acc2, vec3(1.0), 0.5), clamp(data + head, 0.0, 1.0));
          float a = drawn * (0.10 + 0.10 * vD + 0.62 * data) + head * 0.5;
          a *= (0.9 + 0.5 * u_web);
          gl_FragColor = vec4(col, a);
        }`,
    })),
  );
  mTube.frustumCulled = false;
  mTube.renderOrder = 1;
  group.add(mTube);

  /* ── 4. station 03: the node blooms into a live graph ────────────────────
     Children on the deterministic golden-angle spiral, links solving into
     place — the same layout rule as the app's own field, for the same reason:
     a layout that reshuffles on reload reads as noise. */
  const MEM_N = 26;
  const memC = STATIONS[2];
  const kids: THREE.Vector3[] = [];
  for (let i = 0; i < MEM_N; i++) {
    const ang = i * 2.399963;
    const rad = 2.6 + 3.4 * Math.sqrt(i / MEM_N);
    kids.push(new THREE.Vector3(
      memC.x + Math.cos(ang) * rad,
      memC.y + Math.sin(ang) * rad * 0.74,
      memC.z + ((i * 7) % 9) * 0.42 - 1.6,
    ));
  }

  const memVert = /* glsl */ `
    attribute vec3 home; attribute float kid;
    varying float vK; varying float vD;
    // u_res is used only by the Points variant's appended gl_PointSize line, but
    // it has to be declared here — that line is concatenated onto this source.
    uniform float u_mem, u_t; uniform vec2 u_res;
    void main(){
      vK = kid;
      // each child arrives in turn, travelling out from the parent node
      float g = clamp((u_mem - kid * 0.42) / 0.58, 0.0, 1.0);
      g = g * g * (3.0 - 2.0 * g);
      vec3 base = vec3(${memC.x.toFixed(3)}, ${memC.y.toFixed(3)}, ${memC.z.toFixed(3)});
      vec3 p = mix(base, home, g);
      p.y += sin(u_t * 0.5 + kid * 6.0) * 0.12 * g;
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      vD = clamp(1.0 - (-mv.z) / 46.0, 0.0, 1.0);
      gl_Position = projectionMatrix * mv;`;

  const kp: number[] = [], kh: number[] = [], kk: number[] = [];
  kids.forEach((k, i) => { kp.push(0, 0, 0); kh.push(k.x, k.y, k.z); kk.push(i / MEM_N); });
  const gMem = track(new THREE.BufferGeometry());
  gMem.setAttribute('position', new THREE.Float32BufferAttribute(kp, 3));
  gMem.setAttribute('home', new THREE.Float32BufferAttribute(kh, 3));
  gMem.setAttribute('kid', new THREE.Float32BufferAttribute(kk, 1));
  const mMem = new THREE.Points(gMem, track(new THREE.ShaderMaterial({
    uniforms: u,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `${memVert}
      gl_PointSize = (3.0 + 4.0 * vD) * (u_res.y / 900.0 + 0.6);
    }`,
    fragmentShader: /* glsl */ `
      varying float vK; varying float vD;
      uniform vec3 u_acc, u_acc2; uniform float u_mem;
      void main(){
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        vec3 col = mix(u_acc, u_acc2, vK);
        col = mix(col, vec3(1.0), smoothstep(0.26, 0.0, d) * 0.5);
        gl_FragColor = vec4(col, (1.0 - smoothstep(0.30, 0.5, d)) * 0.75 * vD * u_mem);
      }`,
  })));
  mMem.frustumCulled = false;
  mMem.renderOrder = 4;
  group.add(mMem);

  // links: parent→child, plus a chord to a near neighbour, so the field reads
  // as a graph rather than a starburst
  const lp: number[] = [], lh: number[] = [], lk: number[] = [];
  const pushEnd = (v: THREE.Vector3, i: number) => {
    lp.push(0, 0, 0); lh.push(v.x, v.y, v.z); lk.push(i / MEM_N);
  };
  kids.forEach((k, i) => {
    lp.push(0, 0, 0); lh.push(memC.x, memC.y, memC.z); lk.push(i / MEM_N);
    pushEnd(k, i);
    const j = (i + 3) % MEM_N;
    pushEnd(k, i); pushEnd(kids[j], Math.max(i, j));
  });
  const gMemLink = track(new THREE.BufferGeometry());
  gMemLink.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
  gMemLink.setAttribute('home', new THREE.Float32BufferAttribute(lh, 3));
  gMemLink.setAttribute('kid', new THREE.Float32BufferAttribute(lk, 1));
  const mMemLink = new THREE.LineSegments(gMemLink, track(new THREE.ShaderMaterial({
    uniforms: u,
    transparent: true, depthWrite: false,
    vertexShader: `${memVert} }`,
    fragmentShader: /* glsl */ `
      varying float vK; varying float vD;
      uniform vec3 u_acc, u_acc2; uniform float u_mem;
      void main(){
        gl_FragColor = vec4(mix(u_acc, u_acc2, vK), 0.30 * vD * u_mem);
      }`,
  })));
  mMemLink.frustumCulled = false;
  mMemLink.renderOrder = 3;
  group.add(mMemLink);

  /* ── 5. station 04: a node face becomes a framed screenshot ──────────────── */
  const shotC = STATIONS[3];
  const shotMat = track(new THREE.MeshBasicMaterial({
    transparent: true, opacity: 0, depthWrite: false, toneMapped: false,
  }));
  const loader = new THREE.TextureLoader();
  loader.load('/img/tui-sessions.png', (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    shotMat.map = tex;
    shotMat.needsUpdate = true;
    disposables.push(tex);
  });
  const SW = 6.4, SH = 4.0;
  const gShot = track(new THREE.PlaneGeometry(SW, SH));
  const mShot = new THREE.Mesh(gShot, shotMat);
  mShot.position.set(shotC.x + 0.4, shotC.y - 0.2, shotC.z + 2.4);
  mShot.renderOrder = 5;
  group.add(mShot);

  const fr = [
    [-SW / 2, -SH / 2], [SW / 2, -SH / 2], [SW / 2, SH / 2], [-SW / 2, SH / 2],
  ];
  const fp: number[] = [];
  for (let i = 0; i < 4; i++) {
    const a = fr[i], b = fr[(i + 1) % 4];
    fp.push(a[0], a[1], 0, b[0], b[1], 0);
  }
  const gFrame = track(new THREE.BufferGeometry());
  gFrame.setAttribute('position', new THREE.Float32BufferAttribute(fp, 3));
  const mFrame = new THREE.LineSegments(gFrame, track(new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false,
    vertexShader: `void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: /* glsl */ `
      uniform vec3 u_acc; uniform float u_shot;
      void main(){ gl_FragColor = vec4(u_acc, 0.85 * u_shot); }`,
  })));
  mFrame.position.copy(mShot.position);
  mFrame.renderOrder = 6;
  group.add(mFrame);

  /* ── 6. the finale: chords between every station, resolving ──────────────── */
  const cp: number[] = [], ct: number[] = [];
  for (let i = 0; i < STATION_COUNT; i++) {
    for (let j = i + 2; j < STATION_COUNT; j++) {
      const a = STATIONS[i], b = STATIONS[j];
      cp.push(a.x, a.y, a.z, b.x, b.y, b.z);
      ct.push(0, 1);
    }
  }
  const gWeb = track(new THREE.BufferGeometry());
  gWeb.setAttribute('position', new THREE.Float32BufferAttribute(cp, 3));
  gWeb.setAttribute('lt', new THREE.Float32BufferAttribute(ct, 1));
  const mWeb = new THREE.LineSegments(gWeb, track(new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      attribute float lt; varying float vT; varying float vD;
      void main(){
        vT = lt;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vD = clamp(1.0 - (-mv.z) / 46.0, 0.0, 1.0);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */ `
      varying float vT; varying float vD;
      uniform vec3 u_acc, u_acc2; uniform float u_web, u_t;
      void main(){
        float pk = pow(max(0.0, 1.0 - abs(vT - fract(u_t * 0.09)) * 12.0), 2.0);
        vec3 col = mix(u_acc, u_acc2, vT);
        gl_FragColor = vec4(col, (0.10 + 0.34 * pk) * vD * u_web);
      }`,
  })));
  mWeb.frustumCulled = false;
  mWeb.renderOrder = 1;
  group.add(mWeb);

  /* ── driving it ─────────────────────────────────────────────────────────── */
  const smooth = (x: number) => x * x * (3 - 2 * x);
  const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

  /** Progress 0..1 → position in station space, with a HOLD at each station.
   *  A continuous glide reads as a library demo; arriving and settling reads as
   *  an exhibition. The camera travels over the middle 56% of each segment and
   *  is parked for the rest, which is what gives that section's DOM content the
   *  screen to itself. */
  function stationSpace(p: number): number {
    const seg = clamp01(p) * (STATION_COUNT - 1);
    const i = Math.min(STATION_COUNT - 2, Math.floor(seg));
    const local = seg - i;
    return i + smooth(clamp01((local - 0.22) / 0.56));
  }

  /** 1 when parked at station k, falling off as the camera leaves. */
  const near = (s: number, k: number) => smooth(clamp01(1 - Math.abs(s - k) / 0.9));

  const camPos = new THREE.Vector3();
  const lookAt = new THREE.Vector3();
  const set = (k: string, v: number) => { u[k].value = v; };

  return {
    group,
    update(camera, t, progress, lit) {
      const s = stationSpace(progress);
      const tt = s / (STATION_COUNT - 1);

      CAM_CURVE.getPoint(tt, camPos);
      LOOK_CURVE.getPoint(tt, lookAt);
      camera.position.copy(camPos);
      camera.lookAt(lookAt);

      set('u_t', t);
      set('u_prog', tt);
      set('u_lit', lit);
      set('u_frag', near(s, 1));
      set('u_mem', near(s, 2));
      set('u_shot', near(s, 3));
      set('u_pkt', near(s, 4));
      set('u_web', near(s, 5));

      const shot = near(s, 3);
      shotMat.opacity = 0.92 * shot;
      mShot.visible = shot > 0.01;
      mFrame.visible = mShot.visible;
      // the plane turns to face the camera as it resolves
      mShot.rotation.y = (1 - shot) * 1.25;
      mFrame.rotation.y = mShot.rotation.y;
    },
    resize(w, h) {
      (u.u_res.value as THREE.Vector2).set(w, h);
    },
    dispose() {
      for (const d of disposables) d.dispose();
    },
  };
}
