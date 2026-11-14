/* V50.5 Mako — small interactions only. Everything Mako says is server-rendered. */
(function () {
  'use strict';
  var card = document.querySelector('[data-mako]');
  if (!card) return;

  var KEY = 'makonbook.mako.seen';
  var eventKey = card.getAttribute('data-mako-event') || '';

  function readSeen() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
  }
  function writeSeen(list) {
    try { localStorage.setItem(KEY, JSON.stringify(list.slice(-30))); } catch (e) { /* private mode */ }
  }

  // Play an event's entrance animation once; afterwards Mako stays calm for it.
  var seen = readSeen();
  if (eventKey && seen.indexOf(eventKey) !== -1) {
    card.setAttribute('data-mako-seen', '1');
  } else if (eventKey) {
    seen.push(eventKey);
    window.setTimeout(function () { writeSeen(seen); }, 1500);
  }

  // Tapping Mako walks through its next steps.
  var buddy = card.querySelector('[data-mako-buddy]');
  var steps = Array.prototype.slice.call(card.querySelectorAll('[data-mako-step]'));
  var index = -1;
  if (!buddy) return;
  buddy.addEventListener('click', function () {
    buddy.classList.remove('is-poked');
    void buddy.getBoundingClientRect();
    buddy.classList.add('is-poked');
    if (!steps.length) return;
    steps.forEach(function (step) { step.classList.remove('is-spotlight'); });
    index = (index + 1) % steps.length;
    var step = steps[index];
    step.classList.add('is-spotlight');
    var link = step.querySelector('a');
    if (link && typeof link.focus === 'function') link.focus({ preventScroll: true });
  });
})();
