/* V81/V82: SATMakon premium lesson player.
   - Plays AES-128 encrypted HLS from access-checked endpoints (hls.js; native HLS on Safari).
     Segments may come from a private R2 bucket through short-lived redirects.
   - A watermark with the student's name, ID and masked phone moves around the picture. If it
     is removed or hidden (DevTools), the video pauses and the watermark comes back.
   - Fullscreen always wraps the player box, so the watermark stays visible; on iPhone the
     native fullscreen is replaced by a CSS fullscreen.
   - No download button, no picture-in-picture, no casting, no context menu. */
(function () {
  'use strict';
  var box = document.querySelector('[data-adm-player]');
  if (!box) return;
  var video = box.querySelector('video');
  var start = box.querySelector('[data-adm-start]');
  var errorBox = box.querySelector('[data-adm-error]');
  var errorText = errorBox ? errorBox.querySelector('span') : null;
  var markText = (box.querySelector('[data-adm-mark]') || {}).textContent || '';
  var src = box.dataset.src;
  var hls = null;
  var loaded = false;

  var MESSAGES = {
    device: 'This account started watching on another device. Reload the page to watch here.',
    limit: 'Too many video requests in a short time. Take a short break and reload the page.',
    access: 'This lesson is not available for your account.',
    generic: 'The video could not load. Refresh the page and try again.'
  };

  function showError(kind) {
    if (!errorBox) return;
    if (errorText) errorText.textContent = MESSAGES[kind] || MESSAGES.generic;
    errorBox.hidden = false;
    try { video.pause(); } catch (e) { /* ignore */ }
  }

  function errorKind(data) {
    var code = data && data.response && data.response.code;
    if (code === 409) return 'device';
    if (code === 429) return 'limit';
    if (code === 403 || code === 404) return 'access';
    return 'generic';
  }

  function load(autoplay) {
    if (loaded) return;
    loaded = true;
    if (window.Hls && window.Hls.isSupported()) {
      hls = new window.Hls({
        maxBufferLength: 30,            // keep only a short buffer: nothing worth saving sits in memory
        maxMaxBufferLength: 60,
        backBufferLength: 30,
        enableWorker: true
        // No withCredentials: our endpoints are same-origin (cookies go anyway) and the
        // redirect to the private bucket must be a plain CORS request.
      });
      hls.on(window.Hls.Events.ERROR, function (event, data) {
        if (!data || !data.fatal) return;
        var kind = errorKind(data);
        if (kind !== 'generic') { showError(kind); hls.stopLoad(); return; }
        if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR && !hls._makonRetried) { hls._makonRetried = true; hls.startLoad(); return; }
        if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) { hls.recoverMediaError(); return; }
        showError('generic');
      });
      hls.loadSource(src);
      hls.attachMedia(video);
      if (autoplay) hls.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play().catch(function () {}); });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      video.addEventListener('error', function () { showError('generic'); });
      if (autoplay) video.play().catch(function () {});
    } else {
      showError('generic');
    }
  }

  if (start) start.addEventListener('click', function () { start.hidden = true; load(true); });
  video.addEventListener('play', function () { if (start) start.hidden = true; load(false); });

  /* No saving, no picture-in-picture, no casting. */
  ['contextmenu', 'dragstart'].forEach(function (name) { box.addEventListener(name, function (e) { e.preventDefault(); }); });
  video.disablePictureInPicture = true;
  try { video.disableRemotePlayback = true; } catch (e) { /* older browsers */ }

  /* Moving watermark that defends itself. */
  function ensureMark() {
    var mark = box.querySelector('[data-adm-mark]');
    if (!mark) {
      mark = document.createElement('div');
      mark.setAttribute('data-adm-mark', '');
      mark.setAttribute('aria-hidden', 'true');
      mark.className = 'mk80-player-mark';
      box.appendChild(mark);
    }
    if (mark.textContent !== markText) mark.textContent = markText;
    mark.removeAttribute('style');
    return mark;
  }
  function moveMark() {
    var mark = ensureMark();
    mark.style.left = (6 + Math.random() * 58) + '%';
    mark.style.top = (8 + Math.random() * 74) + '%';
  }
  function markTampered() {
    var mark = box.querySelector('[data-adm-mark]');
    if (!mark || mark.textContent !== markText) return true;
    if (start && !start.hidden) return false;   // hidden on purpose behind the start screen
    var cs = window.getComputedStyle(mark);
    return cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.15;
  }
  var guarding = false;
  function guard() {
    if (guarding || !markTampered()) return;
    guarding = true;
    try { video.pause(); } catch (e) { /* ignore */ }
    moveMark();
    guarding = false;
  }
  moveMark();
  setInterval(moveMark, 15000 + Math.floor(Math.random() * 10000));
  setInterval(guard, 2000);
  if (window.MutationObserver) {
    new MutationObserver(guard).observe(box, { childList: true, subtree: true, attributes: true, characterData: true, attributeFilter: ['style', 'class', 'hidden'] });
  }

  /* Fullscreen on the box keeps the watermark visible; iPhone gets a CSS fullscreen. */
  function setPseudo(on) {
    box.classList.toggle('is-pseudo-fullscreen', on);
    document.documentElement.classList.toggle('mk80-player-lock', on);
  }
  function boxFullscreen() {
    var request = box.requestFullscreen || box.webkitRequestFullscreen;
    if (request) { request.call(box); } else { setPseudo(true); }
  }
  document.addEventListener('fullscreenchange', function () {
    if (document.fullscreenElement === video) {
      document.exitFullscreen().then(boxFullscreen).catch(function () {});
    }
    box.classList.toggle('is-fullscreen', document.fullscreenElement === box);
  });
  video.addEventListener('webkitbeginfullscreen', function () {
    try { video.webkitExitFullscreen(); } catch (e) { /* ignore */ }
    setPseudo(true);
  });
  video.addEventListener('dblclick', function (event) {
    event.preventDefault();
    if (box.classList.contains('is-pseudo-fullscreen')) { setPseudo(false); return; }
    if (document.fullscreenElement) document.exitFullscreen().catch(function () {}); else boxFullscreen();
  });
  var closePseudo = box.querySelector('[data-adm-exit]');
  if (closePseudo) closePseudo.addEventListener('click', function () { setPseudo(false); });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') setPseudo(false); });

  /* Stop and drop the stream when the tab is closed. */
  window.addEventListener('pagehide', function () { if (hls) { hls.destroy(); hls = null; } });
})();
