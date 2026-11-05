(function () {
  'use strict';

  // The test screen's layout (sat-runner-mb-v60.css), as in the MakonBook web
  // app: the Directions popover under the header, and for Reading and Writing
  // the passage beside its question only when the question has one. The
  // runner itself (sat-test-core-v13.js, test-eng.js, test-math.js) is
  // unchanged; this only watches what it renders.

  function setupDirections() {
    const toggle = document.querySelector('[data-mbr-directions-toggle]');
    const panel = document.getElementById('mbr-directions');
    if (!toggle || !panel) return;
    const setOpen = (open) => {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open) panel.querySelector('[data-mbr-directions-close]')?.focus({ preventScroll: true });
    };
    toggle.addEventListener('click', (event) => {
      event.stopPropagation();
      setOpen(panel.hidden);
    });
    panel.querySelectorAll('[data-mbr-directions-close]').forEach((button) => {
      button.addEventListener('click', () => {
        setOpen(false);
        toggle.focus({ preventScroll: true });
      });
    });
    document.addEventListener('click', (event) => {
      if (!panel.hidden && !panel.contains(event.target) && event.target !== toggle) setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !panel.hidden) setOpen(false);
    });
  }

  function hasContent(node) {
    if (!node) return false;
    if ((node.textContent || '').trim()) return true;
    return Boolean(node.querySelector('img, svg, table, canvas'));
  }

  function setupColumns() {
    const main = document.querySelector('[data-mbr-main]');
    const questionText = document.getElementById('question-text');
    if (!main || !questionText) return;
    const passagePane = main.querySelector('[data-mbr-passage-pane]');

    const refresh = () => {
      // Reading and Writing: two panes only for a question with a passage or a
      // figure beside it. Math never has a passage pane (attempt_math.html).
      if (passagePane) {
        const two = hasContent(passagePane);
        main.classList.toggle('is-two', two);
        passagePane.hidden = !two;
      }
      const passage = document.getElementById('passage');
      if (passage && !passagePane) passage.hidden = !hasContent(passage);
      // A new question starts at its top.
      main.scrollTop = 0;
      main.querySelectorAll('.mbr-passage-pane, .mbr-question').forEach((pane) => {
        pane.scrollTop = 0;
      });
    };

    let queued = false;
    const schedule = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        refresh();
      });
    };
    new MutationObserver(schedule).observe(questionText, { childList: true, characterData: true, subtree: true });
    refresh();
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupDirections();
    setupColumns();
  });
})();
