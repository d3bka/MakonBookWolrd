(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var body = document.body;
    if (!body || !body.classList.contains('sat531-page')) return;

    function block(event) {
      event.preventDefault();
      event.stopPropagation();
      return false;
    }

    /* Mouse/touch text selection. */
    document.addEventListener('selectstart', block, true);

    /* Clipboard operations. */
    document.addEventListener('copy', block, true);
    document.addEventListener('cut', block, true);

    /* Dragging selected text/images. */
    document.addEventListener('dragstart', block, true);

    /* Common keyboard selection/copy shortcuts.
       This is a deterrent only: browser DevTools / OS-level capture cannot be
       completely disabled by a normal web page. */
    document.addEventListener('keydown', function (event) {
      var key = String(event.key || '').toLowerCase();
      var modifier = event.ctrlKey || event.metaKey;

      if (modifier && (key === 'c' || key === 'x' || key === 'a')) {
        block(event);
      }

      if (event.shiftKey && (key === 'arrowleft' || key === 'arrowright' ||
          key === 'arrowup' || key === 'arrowdown' || key === 'home' || key === 'end')) {
        block(event);
      }
    }, true);

    /* Remove any accidental selection created before handlers ran. */
    document.addEventListener('selectionchange', function () {
      var selection = window.getSelection ? window.getSelection() : null;
      if (selection && selection.rangeCount && !selection.isCollapsed) {
        selection.removeAllRanges();
      }
    });
  });
})();
