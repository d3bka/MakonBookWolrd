/* MakonBook v5611: lightweight, accessible, draggable, seamless result/logo strips. */
(function () {
  'use strict';
  var root = document.querySelector('[data-mbst-section]');
  if (!root) return;
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function makeScroller(viewportSelector, setSelector, speed, startOffset) {
    var viewport = root.querySelector(viewportSelector);
    if (!viewport) return;
    var track = viewport.querySelector('[data-mbst-track], [data-mbst-logo-track]');
    var original = viewport.querySelector(setSelector);
    if (!track || !original || original.dataset.mbstReady) return;
    original.dataset.mbstReady = 'true';
    var duplicate = original.cloneNode(true);
    duplicate.removeAttribute('data-mbst-ready');
    duplicate.setAttribute('aria-hidden', 'true');
    duplicate.querySelectorAll('img').forEach(function (img) { img.alt = ''; });
    track.appendChild(duplicate);
    // Logo sets may be shorter than the viewport: add enough copies for a full loop.
    while (track.scrollWidth - viewport.clientWidth < original.getBoundingClientRect().width + 30) {
      track.appendChild(duplicate.cloneNode(true));
    }

    var paused = false, dragging = false, dragX = 0, scrollOnDown = 0;
    var lastTime = 0, frame = null, pauseUntil = 0, scrollRemainder = 0;
    var width = 0;
    function measure() { width = original.getBoundingClientRect().width; }
    measure();
    viewport.scrollLeft = startOffset === 'end' ? width : Math.min(startOffset || 0, Math.max(0, width - 1));

    function wrap() {
      if (!width) return;
      if (viewport.scrollLeft > width) viewport.scrollLeft -= width;
      if (viewport.scrollLeft < 0) viewport.scrollLeft += width;
    }
    function tick(timestamp) {
      if (lastTime && !paused && !dragging && !reducedMotion.matches && !document.hidden && timestamp > pauseUntil) {
        scrollRemainder += speed * Math.min((timestamp - lastTime) / 1000, 0.05);
        var wholePixels = Math.trunc(scrollRemainder);
        if (wholePixels) {
          viewport.scrollLeft += wholePixels;
          scrollRemainder -= wholePixels;
          wrap();
        }
      }
      lastTime = timestamp;
      frame = window.requestAnimationFrame(tick);
    }
    frame = window.requestAnimationFrame(tick);
    viewport.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') paused = true; });
    viewport.addEventListener('pointerleave', function () { if (!dragging && !viewport.matches(':focus-within')) paused = false; });
    viewport.addEventListener('focusin', function () { paused = true; });
    viewport.addEventListener('focusout', function () { paused = viewport.matches(':hover'); });
    viewport.addEventListener('wheel', function () { pauseUntil = performance.now() + 3000; }, { passive: true });
    viewport.addEventListener('keydown', function () { pauseUntil = performance.now() + 3000; });
    viewport.addEventListener('scroll', function () { if (!dragging) wrap(); }, { passive: true });
    viewport.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      dragging = true;
      dragX = e.clientX;
      scrollOnDown = viewport.scrollLeft;
      paused = true;
      viewport.classList.add('is-dragging');
      viewport.setPointerCapture(e.pointerId);
    });
    viewport.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      viewport.scrollLeft = scrollOnDown - (e.clientX - dragX);
      if (width && (viewport.scrollLeft < 0 || viewport.scrollLeft >= width)) {
        wrap();
        scrollOnDown = viewport.scrollLeft;
        dragX = e.clientX;
      }
    });
    function stopDrag() {
      dragging = false;
      viewport.classList.remove('is-dragging');
      paused = viewport.matches(':hover') || viewport.matches(':focus-within');
      pauseUntil = performance.now() + 1300;
    }
    viewport.addEventListener('pointerup', stopDrag);
    viewport.addEventListener('pointercancel', stopDrag);
    viewport.addEventListener('lostpointercapture', stopDrag);
    if ('ResizeObserver' in window) {
      var resizeObserver = new ResizeObserver(function () { measure(); wrap(); });
      resizeObserver.observe(original);
    } else {
      window.addEventListener('resize', function () { measure(); wrap(); }, { passive: true });
    }
    window.addEventListener('pagehide', function () {
      if (frame !== null) window.cancelAnimationFrame(frame);
    }, { once: true });
  }
  makeScroller('[data-mbst-viewport]', '[data-mbst-set]', 27, 250);
  makeScroller('[data-mbst-logo-viewport]', '[data-mbst-logo-set]', -23, 'end');
})();
