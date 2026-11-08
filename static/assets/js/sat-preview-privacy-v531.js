(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var body = document.body;
    if (!body || !body.classList.contains('sat531-page')) return;

    var watermarkText = (body.dataset.previewWatermark || 'student').trim();
    var layer = document.querySelector('[data-preview-watermarks]');

    if (layer && watermarkText) {
      var viewportW = Math.max(window.innerWidth, 900);
      var viewportH = Math.max(window.innerHeight, 700);
      var cols = Math.ceil(viewportW / 320);
      var rows = Math.ceil(viewportH / 210);

      for (var y = 0; y < rows; y += 1) {
        for (var x = 0; x < cols; x += 1) {
          var mark = document.createElement('span');
          mark.className = 'sat531-watermark';
          mark.textContent = watermarkText + ' · MakonBook';
          mark.style.left = (x * 320 + 30 + (y % 2) * 90) + 'px';
          mark.style.top = (y * 210 + 70) + 'px';
          layer.appendChild(mark);
        }
      }
    }

    var cover = document.createElement('div');
    cover.className = 'sat531-privacy-cover';
    cover.innerHTML = '<div><strong>Test overview hidden</strong><span>Return to this tab to continue.</span></div>';
    document.body.appendChild(cover);

    function showCover() {
      cover.classList.add('is-visible');
    }
    function hideCover() {
      cover.classList.remove('is-visible');
    }

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) showCover();
      else hideCover();
    });

    window.addEventListener('blur', showCover);
    window.addEventListener('focus', hideCover);

    document.addEventListener('contextmenu', function (event) {
      event.preventDefault();
    });

    document.addEventListener('copy', function (event) {
      var target = event.target;
      if (target && /^(INPUT|TEXTAREA)$/i.test(target.tagName)) return;
      event.preventDefault();
    });

    document.addEventListener('dragstart', function (event) {
      event.preventDefault();
    });

    document.addEventListener('keydown', function (event) {
      var key = String(event.key || '').toLowerCase();

      if ((event.ctrlKey || event.metaKey) && (key === 'p' || key === 's')) {
        event.preventDefault();
        showCover();
        window.setTimeout(hideCover, 900);
      }

      /* Browsers cannot reliably block OS screenshots/PrintScreen.
         When the browser exposes the key event, obscure the preview immediately. */
      if (key === 'printscreen') {
        showCover();
        window.setTimeout(hideCover, 1200);
      }
    });
  });
})();
