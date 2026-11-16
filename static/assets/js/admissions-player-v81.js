/* V81: SATMakon premium lesson player.
   - Plays AES-128 encrypted HLS from access-checked endpoints (hls.js; native HLS on Safari).
   - The video URL is never an mp4 and every request needs this student's login session.
   - A watermark with the student's name moves around the picture, also in fullscreen
     (fullscreen is applied to the player box, not to the bare <video>).
   - No download button, no picture-in-picture, no context menu. */
(function () {
  'use strict';
  var box = document.querySelector('[data-adm-player]');
  if (!box) return;
  var video = box.querySelector('video');
  var start = box.querySelector('[data-adm-start]');
  var mark = box.querySelector('[data-adm-mark]');
  var errorBox = box.querySelector('[data-adm-error]');
  var src = box.dataset.src;
  var hls = null;
  var loaded = false;

  function showError() { if (errorBox) errorBox.hidden = false; }

  function load(autoplay) {
    if (loaded) return;
    loaded = true;
    if (window.Hls && window.Hls.isSupported()) {
      hls = new window.Hls({
        maxBufferLength: 30,            // keep only a short buffer: nothing worth saving sits in memory
        maxMaxBufferLength: 60,
        backBufferLength: 30,
        enableWorker: true,
        xhrSetup: function (xhr) { xhr.withCredentials = true; }
      });
      hls.on(window.Hls.Events.ERROR, function (event, data) {
        if (!data || !data.fatal) return;
        if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR && !data._retried) { data._retried = true; hls.startLoad(); return; }
        if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) { hls.recoverMediaError(); return; }
        showError();
      });
      hls.loadSource(src);
      hls.attachMedia(video);
      if (autoplay) hls.on(window.Hls.Events.MANIFEST_PARSED, function () { video.play().catch(function () {}); });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src;
      if (autoplay) video.play().catch(function () {});
    } else {
      showError();
    }
  }

  if (start) {
    start.addEventListener('click', function () { start.hidden = true; load(true); });
  }
  video.addEventListener('play', function () { if (start) start.hidden = true; load(false); });

  /* No saving, no picture-in-picture, no casting. */
  ['contextmenu', 'dragstart'].forEach(function (name) { box.addEventListener(name, function (e) { e.preventDefault(); }); });
  video.disablePictureInPicture = true;
  try { video.disableRemotePlayback = true; } catch (e) { /* older browsers */ }

  /* Moving watermark. */
  function moveMark() {
    if (!mark) return;
    var x = 6 + Math.random() * 58;
    var y = 8 + Math.random() * 74;
    mark.style.left = x + '%';
    mark.style.top = y + '%';
  }
  moveMark();
  setInterval(moveMark, 9000);

  /* Fullscreen on the box keeps the watermark visible. */
  function boxFullscreen() {
    var request = box.requestFullscreen || box.webkitRequestFullscreen;
    if (request) request.call(box);
  }
  document.addEventListener('fullscreenchange', function () {
    if (document.fullscreenElement === video) {
      document.exitFullscreen().then(boxFullscreen).catch(function () {});
    }
    box.classList.toggle('is-fullscreen', document.fullscreenElement === box);
  });
  video.addEventListener('dblclick', function (event) {
    event.preventDefault();
    if (document.fullscreenElement) document.exitFullscreen().catch(function () {}); else boxFullscreen();
  });

  /* Stop and drop the stream when the tab is closed. */
  window.addEventListener('pagehide', function () { if (hls) { hls.destroy(); hls = null; } });
})();
