/* MakonBook V70 — seasonal particles.
 *
 * spring: red-pink peach/apricot petals and the odd whole blossom
 * summer: golden pollen by day, fireflies by night (they rise, not fall)
 * autumn: tumbling chinar leaves
 * winter: soft snow, crystals and a few girih stars
 *
 * Two canvases: one behind the cards (inside .mbs-layer) and a sparse,
 * larger, blurred one in front for depth on desktop. Moving the pointer
 * makes wind. Off for prefers-reduced-motion, when the tab is hidden, and
 * when the viewer turns "Seasonal effects" off in Settings (localStorage).
 * Public API for the mascot: window.MakonSeason.burst(count).
 */
(() => {
  'use strict';
  const root = document.documentElement;
  const season = root.dataset.season;
  const layer = document.querySelector('[data-season-layer]');
  if (!season || !layer) return;

  const backCanvas = layer.querySelector('.mbs-particles');
  const frontCanvas = document.querySelector('[data-season-front]');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const FX_KEY = 'mb-season-fx';
  const TAU = Math.PI * 2;
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (list) => list[(Math.random() * list.length) | 0];
  const isDark = () => root.dataset.theme === 'dark';

  function fxEnabled() {
    try { return localStorage.getItem(FX_KEY) !== 'off'; } catch (e) { return true; }
  }

  // ---------- sprites (pre-rendered once; drawImage is cheap) ----------
  function sprite(size, draw, blur) {
    const c = document.createElement('canvas');
    const pad = blur ? Math.ceil(blur * 3) : 2;
    c.width = c.height = size + pad * 2;
    const g = c.getContext('2d');
    g.translate(c.width / 2, c.height / 2);
    if (blur && 'filter' in g) g.filter = `blur(${blur}px)`;
    draw(g, size / 2);
    return c;
  }

  const draw = {
    petal(color) {
      return (g, r) => {
        const grad = g.createLinearGradient(0, -r, 0, r);
        grad.addColorStop(0, '#ffe3ec');
        grad.addColorStop(1, color);
        g.fillStyle = grad;
        g.beginPath();
        g.moveTo(0, r);
        g.bezierCurveTo(r * .95, r * .45, r * .85, -r * .7, r * .18, -r * .92);
        g.lineTo(0, -r * .62); // the little notch of a peach petal
        g.lineTo(-r * .18, -r * .92);
        g.bezierCurveTo(-r * .85, -r * .7, -r * .95, r * .45, 0, r);
        g.fill();
        g.strokeStyle = 'rgba(194, 37, 92, .25)';
        g.lineWidth = Math.max(1, r * .06);
        g.beginPath(); g.moveTo(0, r * .8); g.lineTo(0, -r * .35); g.stroke();
      };
    },
    blossom() {
      return (g, r) => {
        for (let i = 0; i < 5; i++) {
          g.save(); g.rotate((i * TAU) / 5);
          g.fillStyle = '#fbb6ce';
          g.beginPath(); g.ellipse(0, -r * .5, r * .36, r * .5, 0, 0, TAU); g.fill();
          g.restore();
        }
        g.fillStyle = '#c2255c'; g.beginPath(); g.arc(0, 0, r * .2, 0, TAU); g.fill();
        g.fillStyle = '#ffd43b';
        for (let i = 0; i < 5; i++) { const a = (i * TAU) / 5; g.beginPath(); g.arc(Math.sin(a) * r * .3, -Math.cos(a) * r * .3, r * .07, 0, TAU); g.fill(); }
      };
    },
    chinar(color) {
      // palmate chinar (oriental plane) leaf, drawn in a 100x100 box
      const leaf = new Path2D('M50 94L48 75C40 79 28 81 17 78L24 68C13 64 5 56 3 47L16 47C11 39 11 29 15 20C24 27 30 31 34 34L31 17C38 21 43 13 50 3C57 13 62 21 69 17L66 34C70 31 76 27 85 20C89 29 89 39 84 47L97 47C95 56 87 64 76 68L83 78C72 81 60 79 52 75L50 94Z');
      const veins = new Path2D('M50 90L50 12M50 62L18 26M50 62L82 26M50 66L10 49M50 66L90 49');
      return (g, r) => {
        g.scale(r / 46, r / 46);
        g.translate(-50, -50);
        g.fillStyle = color;
        g.fill(leaf);
        g.strokeStyle = 'rgba(90, 40, 10, .32)';
        g.lineWidth = 2.2;
        g.stroke(veins);
      };
    },
    snow() {
      // white on dark; a cool blue-grey on light backgrounds so it stays visible
      const [core, mid] = isDark() ? ['rgba(255,255,255,1)', 'rgba(255,255,255,.85)'] : ['rgba(150,190,228,1)', 'rgba(176,208,238,.85)'];
      return (g, r) => {
        const grad = g.createRadialGradient(0, 0, 0, 0, 0, r);
        grad.addColorStop(0, core);
        grad.addColorStop(.55, mid);
        grad.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = grad; g.beginPath(); g.arc(0, 0, r, 0, TAU); g.fill();
      };
    },
    crystal(color) {
      return (g, r) => {
        g.strokeStyle = color; g.lineCap = 'round'; g.lineWidth = Math.max(1.2, r * .12);
        for (let i = 0; i < 6; i++) {
          g.save(); g.rotate((i * TAU) / 6);
          g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -r);
          g.moveTo(0, -r * .55); g.lineTo(r * .28, -r * .78); g.moveTo(0, -r * .55); g.lineTo(-r * .28, -r * .78);
          g.stroke(); g.restore();
        }
      };
    },
    girih(color) {
      return (g, r) => {
        g.fillStyle = color;
        g.beginPath();
        for (let i = 0; i < 16; i++) { const a = (i * TAU) / 16; const rr = i % 2 ? r * .52 : r; g.lineTo(Math.sin(a) * rr, -Math.cos(a) * rr); }
        g.closePath(); g.fill();
        g.fillStyle = 'rgba(255,255,255,.85)'; g.beginPath(); g.arc(0, 0, r * .22, 0, TAU); g.fill();
      };
    },
    glow(core, halo) {
      return (g, r) => {
        const grad = g.createRadialGradient(0, 0, 0, 0, 0, r);
        grad.addColorStop(0, core); grad.addColorStop(.25, core); grad.addColorStop(1, halo);
        g.fillStyle = grad; g.beginPath(); g.arc(0, 0, r, 0, TAU); g.fill();
      };
    },
  };

  // kind: fall | float.  flip: 3D tumble.  Each entry: [weight, size, drawer]
  function recipe() {
    if (season === 'spring') {
      return { kind: 'fall', flip: true, speed: [.35, .9], items: [
        ...['#f78fb3', '#f06595', '#ff8fab', '#fbb6ce', '#e64980'].map((c) => [17, 18, draw.petal(c)]),
        [10, 22, draw.blossom()],
      ] };
    }
    if (season === 'autumn') {
      return { kind: 'fall', flip: true, speed: [.5, 1.1], items:
        ['#e76f51', '#f4a261', '#e9c46a', '#bc4749', '#d68c45'].map((c) => [20, 26, draw.chinar(c)]) };
    }
    if (season === 'winter') {
      const ice = isDark() ? '#cfe8ff' : '#9ed2f5';
      return { kind: 'fall', flip: false, speed: [.3, .85], items: [
        [64, 10, draw.snow()],
        [26, 20, draw.crystal(isDark() ? 'rgba(220,238,255,.95)' : 'rgba(120,180,230,.9)')],
        [10, 16, draw.girih(ice)],
      ] };
    }
    // summer: pollen by day, fireflies by night
    return isDark()
      ? { kind: 'float', flip: false, speed: [.12, .35], items: [[100, 14, draw.glow('rgba(226,255,140,1)', 'rgba(190,255,90,0)')]] }
      : { kind: 'float', flip: false, speed: [.12, .3], items: [[100, 12, draw.glow('rgba(255,214,102,1)', 'rgba(255,190,60,0)')]] };
  }

  function buildSprites(blur) {
    const r = recipe();
    const total = r.items.reduce((s, it) => s + it[0], 0);
    const list = r.items.map(([w, size, fn]) => ({ w: w / total, size, img: sprite(size, fn, blur) }));
    return { ...r, list };
  }

  function choose(list) {
    let x = Math.random();
    for (const it of list) { x -= it.w; if (x <= 0) return it; }
    return list[list.length - 1];
  }

  // ---------- field ----------
  function Field(canvas, opts) {
    const ctx = canvas.getContext('2d');
    let W = 0, H = 0, dpr = 1, parts = [], spec = null;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const target = opts.count(W, H);
      while (parts.length < target) parts.push(spawn(true));
      parts.length = Math.min(parts.length, target);
    }

    function spawn(anywhere) {
      const it = choose(spec.list);
      const z = rand(opts.depth[0], opts.depth[1]);
      const floats = spec.kind === 'float';
      return {
        it, z,
        x: rand(-40, W + 40),
        y: anywhere ? rand(-H * .1, H) : (floats ? H + 30 : -30),
        vy: rand(spec.speed[0], spec.speed[1]) * z * (floats ? -1 : 1),
        vx: rand(-.15, .15),
        rot: rand(0, TAU), vr: rand(-.02, .02),
        flip: rand(0, TAU), vf: rand(.02, .05),
        sway: rand(.6, 1.6), phase: rand(0, TAU),
        scale: opts.scale * z * rand(.75, 1.15),
        tw: rand(0, TAU),
      };
    }

    function step(dt, wind, pointer) {
      ctx.clearRect(0, 0, W, H);
      const floats = spec.kind === 'float';
      for (let i = 0; i < parts.length; i++) {
        const p = parts[i];
        p.phase += .012 * dt;
        p.x += (p.vx + Math.sin(p.phase) * .35 * p.sway + wind * p.z) * dt;
        p.y += p.vy * dt;
        p.rot += p.vr * dt;
        p.flip += p.vf * dt;
        if (pointer.active) {
          const dx = p.x - pointer.x, dy = p.y - pointer.y, d2 = dx * dx + dy * dy;
          if (d2 < 9000) { const f = (1 - d2 / 9000) * 1.6; p.x += (dx / 95) * f * dt; p.y += (dy / 95) * f * dt * .5; }
        }
        if ((!floats && p.y > H + 40) || (floats && p.y < -40) || p.x < -80 || p.x > W + 80) {
          if (p.burst) { parts.splice(i, 1); i--; continue; }
          parts[i] = spawn(false);
          continue;
        }
        const img = p.it.img;
        const s = p.scale;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        if (spec.flip) ctx.scale(Math.cos(p.flip) * .85 + (Math.cos(p.flip) >= 0 ? .15 : -.15), 1);
        if (floats) { p.tw += .03 * dt; ctx.globalAlpha = .35 + .65 * Math.abs(Math.sin(p.tw)); }
        else ctx.globalAlpha = opts.alpha;
        ctx.drawImage(img, (-img.width / 2) * s, (-img.height / 2) * s, img.width * s, img.height * s);
        ctx.restore();
      }
    }

    function burst(n, origin) {
      for (let k = 0; k < n; k++) {
        const p = spawn(false);
        p.burst = true;
        if (origin) { p.x = origin.x + rand(-30, 30); p.y = origin.y + rand(-20, 20); p.vy = rand(-1.6, -.4); p.vx = rand(-1.4, 1.4); }
        else { p.y = rand(-60, 0); }
        parts.push(p);
      }
    }

    return {
      canvas,
      rebuild() { spec = buildSprites(opts.blur); parts = []; resize(); },
      resize, step, burst,
      clear() { ctx.clearRect(0, 0, W, H); parts = []; },
    };
  }

  const fields = [];
  if (backCanvas) {
    fields.push(Field(backCanvas, {
      depth: [.55, 1], scale: 1, alpha: .92, blur: 0,
      count: (w, h) => Math.round(Math.min(46, Math.max(12, (w * h) / 26000)) * (season === 'summer' ? .6 : 1)),
    }));
  }
  if (frontCanvas) {
    fields.push(Field(frontCanvas, {
      depth: [1.1, 1.5], scale: 1.45, alpha: .82, blur: 1.4,
      count: (w) => (w >= 1100 ? (season === 'summer' ? 4 : 6) : 0),
    }));
  }
  if (!fields.length) return;

  // ---------- loop ----------
  let running = false, last = 0, raf = 0, wind = 0, windTarget = 0;
  const pointer = { x: 0, y: 0, active: false, lastX: null };

  function frame(t) {
    if (!running) return;
    const dt = Math.min(3, (t - last) / 16.67 || 1);
    last = t;
    windTarget *= .96;
    wind += (windTarget - wind) * .05;
    fields.forEach((f) => f.step(dt, wind, pointer));
    raf = requestAnimationFrame(frame);
  }

  function shouldRun() { return fxEnabled() && !reduceMotion.matches && !document.hidden; }

  function start() {
    if (running || !shouldRun()) return;
    running = true; last = performance.now();
    raf = requestAnimationFrame(frame);
  }
  function stop(clear) {
    running = false; cancelAnimationFrame(raf);
    if (clear) fields.forEach((f) => f.clear());
  }
  function sync() {
    if (shouldRun()) { if (!fields[0].ready) { fields.forEach((f) => { f.rebuild(); f.ready = true; }); } start(); }
    else stop(!fxEnabled() || reduceMotion.matches);
    if (!fxEnabled() || reduceMotion.matches) fields.forEach((f) => { f.ready = false; });
  }

  window.addEventListener('pointermove', (e) => {
    pointer.x = e.clientX; pointer.y = e.clientY; pointer.active = true;
    if (pointer.lastX !== null) windTarget = Math.max(-2.4, Math.min(2.4, windTarget + (e.clientX - pointer.lastX) * .012));
    pointer.lastX = e.clientX;
  }, { passive: true });
  document.addEventListener('pointerleave', () => { pointer.active = false; pointer.lastX = null; });
  let resizeTimer = 0;
  window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => fields.forEach((f) => f.ready && f.resize()), 150); });
  document.addEventListener('visibilitychange', sync);
  reduceMotion.addEventListener?.('change', sync);
  window.addEventListener('storage', (e) => { if (e.key === FX_KEY) sync(); });
  window.addEventListener('makon:season-fx', sync);
  // light/dark swap changes summer's particles and winter's crystal colour
  new MutationObserver(() => fields.forEach((f) => { if (f.ready) f.rebuild(); })).observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  window.MakonSeason = {
    season,
    burst(count = 24, origin = null) { if (shouldRun() && fields[0].ready) fields[0].burst(count, origin); },
    setEnabled(on) {
      try { localStorage.setItem(FX_KEY, on ? 'on' : 'off'); } catch (e) { /* storage blocked: session-only */ }
      window.dispatchEvent(new Event('makon:season-fx'));
    },
    enabled: fxEnabled,
  };

  // Settings → Appearance → Seasonal effects (per viewer, this browser only)
  document.querySelectorAll('[data-season-fx-toggle]').forEach((btn) => {
    const label = btn.querySelector('[data-season-fx-label]');
    const paint = () => {
      const on = fxEnabled();
      btn.setAttribute('aria-checked', on ? 'true' : 'false');
      btn.classList.toggle('is-off', !on);
      if (label) label.textContent = reduceMotion.matches ? 'Reduced motion' : (on ? 'On' : 'Off');
    };
    btn.addEventListener('click', () => { window.MakonSeason.setEnabled(!fxEnabled()); paint(); if (fxEnabled()) window.MakonSeason.burst(18); });
    window.addEventListener('makon:season-fx', paint);
    paint();
  });

  sync();
})();
