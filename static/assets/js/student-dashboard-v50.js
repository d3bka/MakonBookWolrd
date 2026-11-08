(function () {
  'use strict';

  var dashboard = document.getElementById('studentDashboardV50');
  var layer = document.querySelector('[data-dashboard-customize]');
  if (!dashboard || !layer || dashboard.dataset.v50Ready === '1') return;
  dashboard.dataset.v50Ready = '1';

  var openButton = document.querySelector('[data-dashboard-customize-open]');
  var closeButtons = layer.querySelectorAll('[data-dashboard-customize-close]');
  var toggles = Array.prototype.slice.call(layer.querySelectorAll('[data-dashboard-widget-toggle]'));
  var saveButton = layer.querySelector('[data-dashboard-customize-save]');
  var resetButton = layer.querySelector('[data-dashboard-customize-reset]');
  var storageKey = 'makonbook.dashboard.hiddenWidgets.v50';
  var previousFocus = null;

  function readHidden() {
    try {
      var value = JSON.parse(window.localStorage.getItem(storageKey) || '[]');
      return Array.isArray(value) ? value.filter(function (item) { return typeof item === 'string'; }) : [];
    } catch (error) {
      return [];
    }
  }

  function writeHidden(hidden) {
    try { window.localStorage.setItem(storageKey, JSON.stringify(hidden)); } catch (error) { /* preferences are optional */ }
  }

  function applyHidden(hidden) {
    document.querySelectorAll('[data-dashboard-widget]').forEach(function (widget) {
      var key = widget.getAttribute('data-dashboard-widget');
      widget.classList.toggle('is-dashboard-hidden', hidden.indexOf(key) !== -1);
    });
  }

  function syncToggles(hidden) {
    toggles.forEach(function (toggle) {
      toggle.checked = hidden.indexOf(toggle.value) === -1;
    });
  }

  function stagedHidden() {
    return toggles.filter(function (toggle) { return !toggle.checked; }).map(function (toggle) { return toggle.value; });
  }

  function openPanel() {
    previousFocus = document.activeElement;
    syncToggles(readHidden());
    layer.classList.add('is-open');
    layer.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('mb50-customize-open');
    var focusTarget = layer.querySelector('[data-dashboard-widget-toggle]');
    if (focusTarget) focusTarget.focus();
  }

  function closePanel() {
    layer.classList.remove('is-open');
    layer.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('mb50-customize-open');
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
  }

  applyHidden(readHidden());

  function revealHashTarget(hash) {
    if (!hash || hash.charAt(0) !== '#') return;
    var target = document.getElementById(hash.slice(1));
    if (!target) return;
    var widget = target.hasAttribute('data-dashboard-widget') ? target : target.closest('[data-dashboard-widget]');
    if (!widget || !widget.classList.contains('is-dashboard-hidden')) return;
    var key = widget.getAttribute('data-dashboard-widget');
    var hidden = readHidden().filter(function (item) { return item !== key; });
    writeHidden(hidden);
    applyHidden(hidden);
  }

  document.querySelectorAll('a[href*="#"]').forEach(function (link) {
    link.addEventListener('click', function () {
      try {
        var url = new URL(link.href, window.location.href);
        if (url.pathname === window.location.pathname) revealHashTarget(url.hash);
      } catch (error) { /* ignore malformed/non-local links */ }
    });
  });
  revealHashTarget(window.location.hash);

  if (openButton) openButton.addEventListener('click', openPanel);
  closeButtons.forEach(function (button) { button.addEventListener('click', closePanel); });

  if (saveButton) {
    saveButton.addEventListener('click', function () {
      var hidden = stagedHidden();
      writeHidden(hidden);
      applyHidden(hidden);
      closePanel();
    });
  }

  if (resetButton) {
    resetButton.addEventListener('click', function () {
      toggles.forEach(function (toggle) { toggle.checked = true; });
      writeHidden([]);
      applyHidden([]);
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && layer.classList.contains('is-open')) closePanel();
  });
})();
