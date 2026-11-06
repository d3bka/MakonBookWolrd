/* MakonBook V64.1 local — interaction-only brand transition.
 * Never creates an overlay on initial load. Never waits for external resources.
 * Does not hide or disable the document, and always cleans up on errors.
 */
(function () {
  'use strict';
  if (!document.querySelector('.mb56-nav-wrap')) return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const TOTAL_MS = 730;
  const ACTION_MS = 270;
  let current = null;
  let routePending = false;

  function createVeil() {
    const veil = document.createElement('div');
    veil.className = 'mb641-brand-veil';
    veil.setAttribute('aria-hidden', 'true');

    const brand = document.createElement('div');
    brand.className = 'mb641-brand-lockup';
    const mark = document.createElement('span');
    mark.className = 'mb641-brand-mark';
    const image = document.createElement('img');
    image.alt = '';
    image.decoding = 'async';
    // Use the existing local asset; no Google Fonts or new network dependency.
    const existing = document.querySelector('.mb56-nav .mb56-brand-mark img');
    if (existing) {
      // The transition logo is fixed white on the same purple background in every theme.
      // Resolve next to the existing icon to respect custom STATIC_URL/CDN paths.
      image.src = new URL('white-icon-nobg.png', existing.currentSrc || existing.src).href;
    }
    mark.appendChild(image);
    const title = document.createElement('strong');
    title.textContent = 'MakonBook';
    const subtitle = document.createElement('small');
    subtitle.textContent = 'BY SATMAKON';
    brand.append(mark, title, subtitle);
    veil.appendChild(brand);
    document.body.appendChild(veil);
    return veil;
  }

  function run(action, overrideDelay) {
    if (typeof action !== 'function') return Promise.resolve();
    if (reduce.matches || document.hidden || !document.body) {
      return Promise.resolve().then(action);
    }
    // Never create a stack of full-screen animations when clicks happen rapidly.
    if (current) return Promise.resolve().then(action);

    let veil;
    try { veil = createVeil(); }
    catch (error) {
      console.warn('[MakonBook] Brand transition unavailable:', error);
      return Promise.resolve().then(action);
    }
    let cleanupTimeout;
    let actionTimeout;
    let executed = false;
    const close = () => {
      if (actionTimeout) window.clearTimeout(actionTimeout);
      if (cleanupTimeout) window.clearTimeout(cleanupTimeout);
      if (veil.isConnected) veil.remove();
      if (current === veil) current = null;
    };
    current = veil;
    // CSS does all animation. The action runs after the logo becomes visible.
    veil.classList.add('is-playing');
    veil.addEventListener('animationend', event => {
      if (event.target === veil) close();
    }, {once: true});
    cleanupTimeout = window.setTimeout(close, TOTAL_MS + 240);

    return new Promise((resolve, reject) => {
      actionTimeout = window.setTimeout(() => {
        if (executed) return;
        executed = true;
        try {
          resolve(action());
        } catch (error) {
          reject(error);
        }
      }, Number.isFinite(overrideDelay) ? overrideDelay : ACTION_MS);
    }).finally(() => {
      // The veil is still fading for a moment; the hard timeout removes it
      // even if an animation event is never delivered.
    });
  }


  function closeMobileMenu() {
    const menu = document.querySelector('[data-nav-menu]');
    const toggle = document.querySelector('[data-nav-toggle]');
    if (menu) menu.classList.remove('is-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  }

  function commitAnchor(target, hash) {
    closeMobileMenu();
    target.scrollIntoView({behavior: reduce.matches ? 'auto' : 'smooth', block:'start'});
    if (window.location.hash !== hash) window.history.pushState(null, '', hash);
  }

  // Between documents the source cover STAYS visible until the browser swaps
  // documents. An early <head> script activates the matching destination cover,
  // which reveals the already-rendered page. No initial-load splash.
  function navigate(url) {
    if (routePending) return;
    routePending = true;
    closeMobileMenu();
    if (reduce.matches || document.hidden) { window.location.assign(url.href); return; }
    let veil;
    try {
      veil = createVeil();
      current = veil;
      veil.classList.add('mb645-departing');
    } catch (error) {
      routePending = false;
      window.location.assign(url.href);
      return;
    }
    let navigated = false;
    const destination = url.pathname + url.search + url.hash;
    const leave = () => {
      if (navigated) return;
      navigated = true;
      try {
        sessionStorage.setItem('mb645-route-intent', JSON.stringify({
          to: destination, time: Date.now(), version: 645
        }));
      } catch (_) { /* private mode: navigation still works */ }
      window.location.assign(url.href);
    };
    window.setTimeout(leave, 285);
    // Browser navigation can fail or be cancelled; never trap the current page.
    window.setTimeout(() => {
      if (veil.isConnected) veil.remove();
      if (current === veil) current = null;
      routePending = false;
    }, 4500);
  }

  // All same-document anchors (including /#id from the public header) keep
  // the familiar scrolling transition and do NOT force a full page refresh.
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest && event.target.closest('a[href]');
    if (!link || !document.body.contains(link) || link.hasAttribute('download') || link.target && link.target !== '_self') return;
    const raw = link.getAttribute('href') || '';
    if (!raw || raw.startsWith('javascript:')) return;
    let url;
    try { url = new URL(link.href, location.href); } catch (_) { return; }
    if (!/^https?:$/.test(url.protocol) || url.origin !== location.origin) return;
    const sameDocument = url.pathname === location.pathname && url.search === location.search;
    const target = sameDocument && url.hash && document.getElementById(decodeURIComponent(url.hash.slice(1)));
    if (target) {
      event.preventDefault();
      event.stopPropagation();
      const commit = () => commitAnchor(target, url.hash);
      run(commit).catch(() => commit());
      return;
    }
    if (sameDocument) return;
    // Apply navigation effect to every header-bearing public page, not just
    // Landing <-> Parents. Also keep the existing parent/footer links covered.
    const inHeader = Boolean(link.closest('.mb56-nav-wrap'));
    const decorated = link.matches('[data-mb642-parent-link], [data-mb645-transition]');
    const inFooter = Boolean(link.closest('.mkp-footer'));
    if (!inHeader && !decorated && !inFooter) return;
    if (routePending) { event.preventDefault(); event.stopPropagation(); return; }
    if (link.matches('[data-mb642-parent-link]')) {
      const locale = (document.documentElement.lang || 'en').split('-')[0];
      if (['en', 'ru', 'uz'].includes(locale)) url.searchParams.set('lang', locale);
    }
    event.preventDefault();
    event.stopPropagation();
    navigate(url);
  }, true);

  // Restore a browser back/forward-cached page without a stranded overlay.
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    document.querySelectorAll('.mb641-brand-veil').forEach(node => node.remove());
    current = null;
    routePending = false;
  });

  window.MakonBookLandingTransition = {run, navigate};
})();
