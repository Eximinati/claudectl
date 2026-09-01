'use client';

/**
 * Mounts the journey scene behind the copy.
 *
 * Three rules shape the whole file, and this project has paid for each one:
 *
 *  1. ONE requestAnimationFrame chain, and it PARKS. A loop that runs while
 *     nothing is visible is a bug, not a feature. Parking destroys the Lenis
 *     instance first — a smooth-scroll driver that stops being ticked has
 *     preventDefault-ed the wheel and left you with a frozen page, so a parked
 *     page always falls back to native scrolling.
 *  2. It fails open. No WebGL, a thrown context, a lost context or
 *     prefers-reduced-motion hides the canvas and the static wash in
 *     globals.css is the page's background. `journey-on` goes on <html> only
 *     once GL has actually painted, so a deferred import is never a second of
 *     blank.
 *  3. Progress is derived from window.scrollY and measured panel offsets, never
 *     from Lenis. Lenis smooths what the browser reports; if it fails to load,
 *     is asleep, or is destroyed, the journey is still exactly right.
 *
 * three and lenis are imported inside the effect so neither is in the initial
 * bundle. Every import here is `import type` for the same reason.
 */
import { useEffect, useRef } from 'react';
import type * as THREE from 'three';
import type Lenis from 'lenis';
import type { Journey } from './scene';

/** How fast progress chases the scroll, in e-folds per second. */
const DAMP = 6.5;
/** Seconds the station-01 joint sweep takes on arrival. */
const LIT_SECONDS = 1.4;

/**
 * `journey` is the landing page: scroll drives the camera from station to
 * station. `ambient` is every other route: the same constellation parked at the
 * finale's pull-back, turning slowly, with no scroll coupling and no Lenis.
 *
 * One scene, one branch. The alternative was eleven static pages — the site
 * stopped moving the moment you clicked Features, which is the opposite of the
 * point. It stays quiet on purpose: this project has already learned that drama
 * belongs in the interface and the background has a luminance ceiling.
 */
export function JourneyCanvas({ mode = 'journey' }: { mode?: 'journey' | 'ambient' }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const html = document.documentElement;
    const ambient = mode === 'ambient';

    /** Fail open: a canvas we cannot drive is worse than no canvas. */
    const drop = () => {
      html.classList.remove('journey-on');
      canvas.style.display = 'none';
    };

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    // Reduced motion gets the scene STILL, not removed. Declining motion is not
    // the same as declining the picture, and removing the canvas left the whole
    // site looking like an unstyled document to anyone whose OS has animation
    // effects switched off — which on Windows 11 is one toggle in Accessibility,
    // and is not a rare setting.
    //
    // One frame is drawn and the loop never starts: `awake()` is false while
    // `still`, so nothing reschedules.
    let still = reduced.matches;

    let cancelled = false;
    let lost = false;
    // Optimistic: only a real blur event clears it. A page that happens to load
    // without focus (a screenshot runner, a restored window) still paints.
    let focused = true;
    let painted = false;
    let raf = 0;

    let renderer: THREE.WebGLRenderer | null = null;
    let scene: THREE.Scene | null = null;
    let camera: THREE.PerspectiveCamera | null = null;
    let journey: Journey | null = null;
    let LenisCtor: typeof Lenis | null = null;
    let lenis: Lenis | null = null;

    let progress = 0;
    let clock = 0;
    let lit = 0;
    let prev = 0;

    const awake = () =>
      !cancelled && !lost && !still && !document.hidden && focused;

    /** One frame, then nothing. The still path for reduced motion. */
    const paintOnce = () => {
      lit = 1;
      progress = targetProgress();
      frame(performance.now());
    };

    const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

    /* ── where the scroll is ────────────────────────────────────────────────
       Panel offsets, measured on resize and on reflow, never in the frame loop.
       A single division by the container's scroll height would assume the six
       panels are the same height — they are not, station 03 alone is worth two
       of station 02 — and the camera would arrive at a solid while you were
       still three paragraphs above it. */
    let tops: number[] = [];
    let end = 0;

    const measure = () => {
      const host = document.getElementById('journey-stations');
      const y = window.scrollY;
      const panels = host
        ? Array.from(host.querySelectorAll<HTMLElement>('[data-station]'))
        : [];
      tops = panels.map((el) => el.getBoundingClientRect().top + y);
      end = host ? host.getBoundingClientRect().bottom + y - window.innerHeight : 0;
    };

    /** Target progress in 0..1: which panel the viewport top sits in, and how
     *  far through it. Arriving at a panel parks the camera at its station. */
    const targetProgress = () => {
      // Ambient parks at the finale, where the camera holds the whole
      // constellation. Nothing to measure, nothing to chase.
      if (ambient) return 1;
      const y = window.scrollY;
      if (tops.length < 2) {
        // The panels moved or have not rendered: fall back to the document's
        // own scroll range, so the scene is never stuck at zero.
        const range = document.documentElement.scrollHeight - window.innerHeight;
        return range > 0 ? clamp01(y / range) : 0;
      }
      let i = 0;
      while (i < tops.length - 1 && y >= tops[i + 1]) i++;
      const stop = i + 1 < tops.length ? tops[i + 1] : end;
      const span = stop - tops[i];
      const local = span > 0 ? (y - tops[i]) / span : 0;
      return clamp01((i + local) / (tops.length - 1));
    };

    const resize = () => {
      if (!renderer || !camera || !journey) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const pr = Math.min(window.devicePixelRatio || 1, 1.75);
      renderer.setPixelRatio(pr);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      // Portrait crops the constellation horizontally, so the vertical fov opens
      // up as the frame narrows. A fixed fov loses the outer solids off the sides
      // of a phone in the finale — 1.5 is the cap that still holds station 02's
      // centre plus its radius at aspect 0.5, which is a 360px-wide viewport.
      camera.fov = 52 * Math.min(1.5, Math.max(1, Math.pow(w / h, -0.7)));
      camera.updateProjectionMatrix();
      // Drawing-buffer pixels, not CSS: gl_PointSize is in device pixels, so a
      // joint drawn from the CSS height shrinks physically on a dense display.
      journey.resize(w * pr, h * pr);
    };

    const frame = (now: number) => {
      raf = 0;
      if (!renderer || !camera || !scene || !journey) return;

      // A long frame is not a long time. Clamping keeps a tab that was throttled
      // from teleporting the scene on its first frame back.
      const dt = prev ? Math.min((now - prev) / 1000, 0.05) : 1 / 60;
      prev = now;

      lenis?.raf(now);

      // Frame-rate-independent damping: the camera settles into a station, it
      // never snaps to it.
      progress += (targetProgress() - progress) * (1 - Math.exp(-DAMP * dt));
      // Ambient runs the scene clock at a third speed. It is behind body copy on
      // a page somebody is reading, so it drifts rather than performs.
      clock += ambient ? dt * 0.34 : dt;
      // The station-01 joint sweep is an arrival, not a scroll position — you
      // are already parked at station 01 when the page loads. It is a uniform,
      // so CSS cannot own this one.
      lit = Math.min(1, lit + dt / LIT_SECONDS);

      journey.update(camera, clock, progress, lit * lit * (3 - 2 * lit));
      renderer.render(scene, camera);

      if (!painted) {
        painted = true;
        html.classList.add('journey-on');
      }
      if (awake()) raf = requestAnimationFrame(frame);
    };

    const sleep = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      lenis?.destroy();
      lenis = null;
    };

    const wake = () => {
      if (raf || !renderer || !awake()) return;
      // No smooth-scroll driver on a reading page: it would take the wheel over
      // for a scene that no longer answers to scroll.
      if (LenisCtor && !lenis && !ambient) lenis = new LenisCtor({ lerp: 0.09 });
      prev = 0;
      raf = requestAnimationFrame(frame);
    };

    /* ── every way this parks, and the way back ─────────────────────────────── */
    const off: (() => void)[] = [];
    const on = (t: EventTarget, ev: string, fn: EventListener) => {
      t.addEventListener(ev, fn);
      off.push(() => t.removeEventListener(ev, fn));
    };

    on(document, 'visibilitychange', () => (document.hidden ? sleep() : wake()));
    on(window, 'blur', () => {
      focused = false;
      sleep();
    });
    on(window, 'focus', () => {
      focused = true;
      wake();
    });
    on(window, 'resize', () => {
      resize();
      measure();
    });
    // three's own constructor already preventDefaults this one, so a restore
    // will follow and three re-uploads everything itself. Until it does, park
    // and fail open — a canvas with a dead context is a black rectangle.
    on(canvas, 'webglcontextlost', () => {
      lost = true;
      sleep();
      drop();
    });
    on(canvas, 'webglcontextrestored', () => {
      lost = false;
      painted = false;
      canvas.style.display = '';
      wake();
    });

    const onReduced = () => {
      still = reduced.matches;
      if (still) {
        sleep();
        paintOnce();
      } else {
        wake();
      }
    };
    reduced.addEventListener('change', onReduced);
    off.push(() => reduced.removeEventListener('change', onReduced));

    // Panels grow when a screenshot loads or the text rewraps; the offsets have
    // to follow or the camera drifts out of step with the copy.
    const host = document.getElementById('journey-stations');
    const ro = host ? new ResizeObserver(measure) : null;
    if (host && ro) {
      ro.observe(host);
      off.push(() => ro.disconnect());
    }

    void (async () => {
      let three: typeof THREE;
      let mod: typeof import('./scene');
      let lenisMod: { default: typeof Lenis } | null;
      try {
        [three, mod, lenisMod] = await Promise.all([
          import('three'),
          import('./scene'),
          // Smooth scroll is a nicety; native scrolling is a fine fallback.
          import('lenis').catch(() => null),
        ]);
      } catch {
        drop();
        return;
      }
      if (cancelled) return;

      try {
        // Opaque on purpose: a transparent surface costs a blend on every
        // composite, and there is nothing behind it worth seeing.
        renderer = new three.WebGLRenderer({ canvas, antialias: true, alpha: false });
      } catch {
        drop();
        return;
      }
      renderer.setClearColor(0x0a0c10, 1);

      scene = new three.Scene();
      camera = new three.PerspectiveCamera(52, 1, 0.1, 220);
      journey = mod.buildJourney();
      scene.add(journey.group);
      LenisCtor = lenisMod?.default ?? null;

      resize();
      measure();
      if (still) paintOnce();
      else wake();
    })();

    return () => {
      cancelled = true;
      sleep();
      for (const f of off) f();
      journey?.dispose();
      renderer?.dispose();
      journey = null;
      renderer = null;
      scene = null;
      camera = null;
      html.classList.remove('journey-on');
    };
    // Crossing between the landing page and the rest is the only thing that
    // rebuilds the scene. Inner-page to inner-page keeps the same canvas.
  }, [mode]);

  return <canvas id="journey" ref={ref} aria-hidden="true" />;
}
