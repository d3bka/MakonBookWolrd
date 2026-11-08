(function () {
  'use strict';

  function setupNav() {
    var wrap = document.querySelector('[data-nav]');
    var btn = document.querySelector('[data-nav-toggle]');
    var menu = document.querySelector('[data-nav-menu]');
    if (!wrap || !btn || !menu) return;
    btn.addEventListener('click', function () {
      var open = wrap.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    menu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        wrap.classList.remove('is-open');
        btn.setAttribute('aria-expanded', 'false');
      });
    });
  }

  function setupFAQ() {
    var list = document.querySelector('[data-faq-list]');
    if (!list) return;
    list.querySelectorAll('.mb597-faq-question').forEach(function (button) {
      button.addEventListener('click', function () {
        var item = button.closest('.mb597-faq-item');
        var willOpen = button.getAttribute('aria-expanded') !== 'true';
        list.querySelectorAll('.mb597-faq-item').forEach(function (other) {
          var otherButton = other.querySelector('.mb597-faq-question');
          if (!otherButton) return;
          otherButton.setAttribute('aria-expanded', 'false');
          other.classList.remove('is-open');
        });
        if (willOpen) {
          button.setAttribute('aria-expanded', 'true');
          item.classList.add('is-open');
        }
      });
    });
  }

  function setupGoUp() {
    var button = document.querySelector('[data-go-up]');
    if (!button) return;
    var sync = function () {
      button.classList.toggle('is-visible', window.scrollY > 520);
    };
    window.addEventListener('scroll', sync, { passive: true });
    sync();
    button.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    });
  }

  function setupInteractiveCards() {
    if (!window.matchMedia('(pointer:fine)').matches || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.querySelectorAll('[data-interactive-card]').forEach(function (card) {
      card.addEventListener('pointermove', function (event) {
        var rect = card.getBoundingClientRect();
        var x = (event.clientX - rect.left) / rect.width;
        var y = (event.clientY - rect.top) / rect.height;
        card.style.setProperty('--card-rx', ((0.5 - y) * 3.5).toFixed(2) + 'deg');
        card.style.setProperty('--card-ry', ((x - 0.5) * 4.5).toFixed(2) + 'deg');
        card.style.setProperty('--card-x', (x * 100).toFixed(1) + '%');
        card.style.setProperty('--card-y', (y * 100).toFixed(1) + '%');
        card.classList.add('is-pointed');
      });
      card.addEventListener('pointerleave', function () {
        card.classList.remove('is-pointed');
        card.style.removeProperty('--card-rx');
        card.style.removeProperty('--card-ry');
        card.style.removeProperty('--card-x');
        card.style.removeProperty('--card-y');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupNav();
    setupFAQ();
    setupGoUp();
    setupInteractiveCards();
  });
})();
