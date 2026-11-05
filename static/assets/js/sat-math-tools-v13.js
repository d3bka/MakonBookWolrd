(function () {
  'use strict';

  // The Math section's Desmos calculator and reference sheet, as in the
  // MakonBook web app (makonbook-web's practice test screen):
  // - on a laptop-sized window the calculator is a pane docked beside the
  //   question; its right edge is a handle (drag it, or focus it and use the
  //   arrow keys) and the width is remembered in this browser;
  // - narrower windows float it: dragged by its bar, resized from its corner;
  // - it stays mounted while closed, and the student's work is one state for
  //   the whole module, kept in this browser as it changes, so it survives
  //   closing the panel, moving between questions or reloading the page.

  const WIDE_QUERY = '(min-width: 900px)';
  const WIDTH_KEY = 'mb.calc.width';
  const CALC_MIN = 300;
  const QUESTION_ROOM = 420; // the question keeps at least this much beside the pane
  const FLOAT_MIN_W = 300;
  const FLOAT_MIN_H = 320;
  const MARGIN = 8;

  const configNode = document.getElementById('sat-test-config');
  let config = {};
  try { config = JSON.parse(configNode?.textContent || '{}'); } catch (error) { config = {}; }

  // The script's URL, with the key from DESMOS_API_KEY (.env), comes from the
  // page (runner_tags.desmos_calculator_src).
  const DESMOS_SRC = config.desmosSrc || '';

  const stateKey = [
    'sat-desmos-v60',
    config.storageScope || 'unknown',
    config.attemptId || 'attempt',
    config.classroomId || 'regular',
    config.sectionName || 'math',
    config.moduleName || 'module',
  ].join(':');

  let calculator = null;
  let loadingPromise = null;
  let savedState = '';
  let saveTimer = null;
  let open = false;
  let floatBox = null;
  let paneWidth = 0;

  const pane = () => document.querySelector('[data-mbr-calc-pane]');
  const popup = () => document.getElementById('calculator-popup');
  const toolButton = () => document.getElementById('open-calculator');
  const referenceOverlay = () => document.getElementById('reference-overlay');
  const isWide = () => window.matchMedia(WIDE_QUERY).matches;

  function dragging(on) {
    document.documentElement.classList.toggle('mb-dragging', on);
  }

  // ---- the student's work ----

  function save() {
    if (!calculator) return;
    try {
      const state = JSON.stringify(calculator.getState());
      if (state !== savedState) {
        localStorage.setItem(stateKey, state);
        savedState = state;
      }
    } catch (error) {
      // Storage full or blocked: the work stays on screen for now.
    }
  }

  function saveSoon() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(save, 300);
  }

  function restore() {
    if (!calculator) return;
    try {
      const raw = localStorage.getItem(stateKey);
      if (raw) {
        calculator.setState(JSON.parse(raw), { allowUndo: false });
        savedState = raw;
      }
    } catch (error) {
      // A state Desmos can't read (or no storage): start empty.
    }
  }

  // ---- loading Desmos ----

  function setPanelState(state) {
    const loading = document.getElementById('calculator-loading');
    const node = document.getElementById('calculator');
    const fallback = document.getElementById('calculator-fallback');
    if (loading) loading.hidden = state !== 'loading';
    if (node) node.hidden = state === 'error';
    if (fallback) fallback.hidden = state !== 'error';
  }

  function loadDesmosScript(force = false) {
    if (window.Desmos?.GraphingCalculator) return Promise.resolve(true);
    if (!DESMOS_SRC) return Promise.resolve(false);
    if (force) {
      loadingPromise = null;
      document.querySelectorAll('script[data-sat-desmos-loader]').forEach((script) => script.remove());
    }
    if (loadingPromise) return loadingPromise;
    loadingPromise = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = DESMOS_SRC;
      script.async = true;
      script.dataset.satDesmosLoader = '1';
      let settled = false;
      const finish = (result) => {
        if (settled) return;
        settled = true;
        resolve(result);
      };
      // The API may finish setting itself up after its script has run.
      script.onload = () => {
        const began = Date.now();
        const wait = () => {
          if (typeof window.Desmos?.GraphingCalculator === 'function') finish(true);
          else if (Date.now() - began > 15000) finish(false);
          else window.setTimeout(wait, 100);
        };
        wait();
      };
      script.onerror = () => finish(false);
      document.head.appendChild(script);
      window.setTimeout(() => finish(Boolean(window.Desmos?.GraphingCalculator)), 20000);
    });
    return loadingPromise;
  }

  function resizeSoon() {
    [0, 60, 240].forEach((delay) => window.setTimeout(() => {
      try { calculator?.resize(); } catch (error) {}
    }, delay));
  }

  async function ensureCalculator(force = false) {
    if (calculator) {
      setPanelState('ready');
      resizeSoon();
      return true;
    }
    setPanelState('loading');
    const loaded = await loadDesmosScript(force);
    const element = document.getElementById('calculator');
    if (!loaded || !element) {
      setPanelState('error');
      return false;
    }
    try {
      calculator = window.Desmos.GraphingCalculator(element, {
        keypad: true,
        expressionsCollapsed: false,
        settingsMenu: false,
        zoomButtons: true,
        border: false,
      });
      restore();
      calculator.observeEvent?.('change', saveSoon);
      // Also now and then, in case a change slipped by.
      window.setInterval(save, 3000);
      setPanelState('ready');
      resizeSoon();
      if (window.ResizeObserver) new ResizeObserver(() => calculator?.resize()).observe(element);
      return true;
    } catch (error) {
      console.error('Desmos could not start:', error);
      calculator = null;
      setPanelState('error');
      return false;
    }
  }

  // ---- docked pane (laptop) ----

  const clampWidth = (w) => Math.round(Math.min(Math.max(w, CALC_MIN), Math.max(CALC_MIN, window.innerWidth - QUESTION_ROOM)));

  function initialWidth() {
    let stored = 0;
    try { stored = Number(localStorage.getItem(WIDTH_KEY)) || 0; } catch (error) {}
    return clampWidth(stored || window.innerWidth * 0.42);
  }

  function setPaneWidth(width, remember = false) {
    paneWidth = clampWidth(width);
    const node = pane();
    if (node) node.style.setProperty('--mbr-calc-width', `${paneWidth}px`);
    const handle = document.querySelector('[data-mbr-calc-resizer]');
    if (handle) {
      handle.setAttribute('aria-valuenow', String(paneWidth));
      handle.setAttribute('aria-valuemin', String(CALC_MIN));
    }
    if (remember) {
      try { localStorage.setItem(WIDTH_KEY, String(paneWidth)); } catch (error) {}
    }
    resizeSoon();
  }

  function setupResizer() {
    const handle = document.querySelector('[data-mbr-calc-resizer]');
    if (!handle) return;
    handle.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = paneWidth;
      let last = startWidth;
      handle.setPointerCapture?.(event.pointerId);
      dragging(true);
      const move = (ev) => {
        last = startWidth + ev.clientX - startX;
        setPaneWidth(last);
      };
      const up = () => {
        dragging(false);
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        handle.removeEventListener('pointercancel', up);
        setPaneWidth(last, true);
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
      handle.addEventListener('pointercancel', up);
    });
    handle.addEventListener('keydown', (event) => {
      const step = event.key === 'ArrowLeft' ? -24 : event.key === 'ArrowRight' ? 24 : 0;
      if (!step) return;
      event.preventDefault();
      setPaneWidth(paneWidth + step, true);
    });
  }

  // ---- floating panel (narrower windows) ----

  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi));

  function defaultBox() {
    const w = Math.min(380, window.innerWidth - MARGIN * 2);
    const h = Math.min(460, window.innerHeight - MARGIN * 2);
    return { x: Math.max(MARGIN, window.innerWidth - w - 24), y: 72, w, h };
  }

  function placeFloat(box) {
    const w = clamp(box.w, Math.min(FLOAT_MIN_W, window.innerWidth - MARGIN * 2), window.innerWidth - MARGIN * 2);
    const h = clamp(box.h, Math.min(FLOAT_MIN_H, window.innerHeight - MARGIN * 2), window.innerHeight - MARGIN * 2);
    floatBox = {
      w,
      h,
      x: clamp(box.x, MARGIN, window.innerWidth - w - MARGIN),
      y: clamp(box.y, MARGIN, window.innerHeight - h - MARGIN),
    };
    const node = popup();
    if (!node) return;
    node.style.left = `${floatBox.x}px`;
    node.style.top = `${floatBox.y}px`;
    node.style.width = `${floatBox.w}px`;
    node.style.height = `${floatBox.h}px`;
    resizeSoon();
  }

  function floatGesture(kind) {
    return (event) => {
      if (isWide()) return;
      if (kind === 'move' && event.target.closest('button')) return;
      event.preventDefault();
      const start = { x: event.clientX, y: event.clientY, box: { ...floatBox } };
      const target = event.currentTarget;
      target.setPointerCapture?.(event.pointerId);
      dragging(true);
      const move = (ev) => {
        const dx = ev.clientX - start.x;
        const dy = ev.clientY - start.y;
        const b = start.box;
        if (kind === 'move') placeFloat({ ...b, x: b.x + dx, y: b.y + dy });
        else placeFloat({ ...b, w: b.w + dx, h: b.h + dy });
      };
      const up = () => {
        dragging(false);
        target.removeEventListener('pointermove', move);
        target.removeEventListener('pointerup', up);
        target.removeEventListener('pointercancel', up);
      };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up);
      target.addEventListener('pointercancel', up);
    };
  }

  // ---- open / close ----

  function applyLayout() {
    const node = popup();
    if (!node) return;
    const docked = isWide();
    document.body.classList.toggle('mbr-calc-docked', docked);
    document.body.classList.toggle('mbr-calc-floating', !docked);
    if (docked) {
      node.style.left = node.style.top = node.style.width = node.style.height = '';
      setPaneWidth(paneWidth || initialWidth());
    } else {
      placeFloat(floatBox || defaultBox());
    }
  }

  function setCalculatorOpen(next) {
    open = Boolean(next);
    document.body.classList.toggle('mbr-calc-open', open);
    const node = popup();
    if (node) node.setAttribute('aria-hidden', String(!open));
    const button = toolButton();
    if (button) {
      button.setAttribute('aria-pressed', String(open));
      button.classList.toggle('is-on', open);
    }
    if (open) {
      applyLayout();
      ensureCalculator(false).then(resizeSoon);
    } else {
      save();
    }
  }

  function openCalculator() { setCalculatorOpen(true); }
  function closeCalculator() { setCalculatorOpen(false); }

  function setReferenceOpen(next) {
    const overlay = referenceOverlay();
    if (!overlay) return;
    overlay.classList.toggle('active', Boolean(next));
    const button = document.getElementById('open-reference');
    if (button) {
      button.setAttribute('aria-pressed', String(Boolean(next)));
      button.classList.toggle('is-on', Boolean(next));
    }
    if (next) overlay.querySelector('.reference-close-btn')?.focus({ preventScroll: true });
  }

  function openReference() { setReferenceOpen(true); }
  function closeReference() { setReferenceOpen(false); }
  const referenceOpen = () => Boolean(referenceOverlay()?.classList.contains('active'));

  function isToolFocused() {
    if (referenceOpen()) return true;
    const node = popup();
    if (!open || !node) return false;
    const active = document.activeElement;
    return Boolean(active && (node.contains(active) || active.closest?.('[class*="dcg-"]')));
  }

  document.addEventListener('DOMContentLoaded', () => {
    paneWidth = initialWidth();
    toolButton()?.addEventListener('click', () => setCalculatorOpen(!open));
    document.getElementById('open-reference')?.addEventListener('click', () => setReferenceOpen(!referenceOpen()));
    document.getElementById('retry-calculator')?.addEventListener('click', () => ensureCalculator(true));
    referenceOverlay()?.addEventListener('click', (event) => {
      if (event.target === referenceOverlay()) closeReference();
    });
    document.getElementById('calculator-header')?.addEventListener('pointerdown', floatGesture('move'));
    document.getElementById('calculator-resize-handle')?.addEventListener('pointerdown', floatGesture('resize'));
    setupResizer();
    window.addEventListener('resize', () => {
      if (open) applyLayout();
      else if (paneWidth) setPaneWidth(paneWidth);
    });
    window.addEventListener('pagehide', save);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') save();
    });
  });

  window.openCalculator = openCalculator;
  window.closeCalculator = closeCalculator;
  window.openReference = openReference;
  window.closeReference = closeReference;
  window.SATMathTools = {
    // One calculator for the whole module, as on the SAT: moving between
    // questions keeps the work, so these only make sure it is saved.
    saveState() { save(); },
    loadState() {},
    isToolFocused,
    closeAll() {
      // Escape closes the reference sheet first, then the calculator.
      if (referenceOpen()) closeReference();
      else if (open) closeCalculator();
    },
    clear() {
      savedState = '';
      try { localStorage.removeItem(stateKey); } catch (error) {}
    },
  };
})();
