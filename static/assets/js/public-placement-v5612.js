(function () {
  'use strict';

  function digitsOnly(value) {
    return String(value || '').replace(/\D/g, '');
  }

  function formatUzbekPhone(value) {
    var digits = digitsOnly(value);
    if (digits.indexOf('998') === 0) digits = digits.slice(3);
    digits = digits.slice(0, 9);
    var out = '+998';
    if (digits.length) out += ' ' + digits.slice(0, 2);
    if (digits.length > 2) out += ' ' + digits.slice(2, 5);
    if (digits.length > 5) out += ' ' + digits.slice(5, 7);
    if (digits.length > 7) out += ' ' + digits.slice(7, 9);
    return out;
  }

  function phoneComplete(value) {
    var digits = digitsOnly(value);
    return digits.length === 12 && digits.indexOf('998') === 0;
  }

  function initPhone() {
    document.querySelectorAll('[data-pp-phone]').forEach(function (input) {
      if (input.value) input.value = formatUzbekPhone(input.value);
      input.addEventListener('focus', function () {
        if (!input.value) input.value = '+998 ';
      });
      input.addEventListener('input', function () {
        input.value = formatUzbekPhone(input.value);
        var wrap = input.closest('.pp12-phone-wrap');
        if (wrap) wrap.classList.toggle('is-valid', phoneComplete(input.value));
        updateForm(input.form);
      });
      input.addEventListener('blur', function () {
        if (digitsOnly(input.value) === '998') input.value = '';
      });
    });
  }

  function updateForm(form) {
    if (!form) return;
    var required = Array.prototype.slice.call(form.querySelectorAll('[data-pp-required]'));
    var consent = form.querySelector('[data-pp-consent]');
    var progress = document.querySelector('[data-pp-form-progress]');
    var complete = 0;

    required.forEach(function (field) {
      var valid = field.matches('[data-pp-phone]') ? phoneComplete(field.value) : field.value.trim().length >= 2;
      field.classList.toggle('is-valid', valid);
      if (valid) complete += 1;
    });
    if (consent && consent.checked) complete += 1;
    var total = required.length + (consent ? 1 : 0);
    if (progress) progress.style.width = (total ? Math.round((complete / total) * 100) : 0) + '%';
    var submit = form.querySelector('[data-pp-submit]');
    if (submit) submit.classList.toggle('is-ready', complete === total);
  }

  function initForm() {
    document.querySelectorAll('[data-pp-form]').forEach(function (form) {
      form.addEventListener('input', function () { updateForm(form); });
      form.addEventListener('change', function () { updateForm(form); });
      form.addEventListener('submit', function () {
        var submit = form.querySelector('[data-pp-submit]');
        if (!submit || submit.disabled) return;
        submit.disabled = true;
        submit.setAttribute('aria-busy', 'true');
        var label = submit.querySelector('span');
        if (label) label.textContent = 'Starting test…';
      });
      updateForm(form);
    });
  }

  function initReveal() {
    var nodes = document.querySelectorAll('[data-pp-reveal]');
    if (!nodes.length) return;
    if (!('IntersectionObserver' in window)) {
      nodes.forEach(function (node) { node.classList.add('is-visible'); });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    nodes.forEach(function (node) { observer.observe(node); });
  }

  function toast(message) {
    var node = document.querySelector('[data-pp-toast]');
    if (!node) return;
    node.textContent = message;
    node.classList.add('is-visible');
    window.setTimeout(function () { node.classList.remove('is-visible'); }, 1800);
  }

  function initShare() {
    var button = document.querySelector('[data-pp-share]');
    if (!button) return;
    button.addEventListener('click', function () {
      var text = button.getAttribute('data-share-text') || document.title;
      if (navigator.share) {
        navigator.share({ title: 'MakonBook placement result', text: text, url: window.location.href }).catch(function () {});
        return;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text + ' ' + window.location.href).then(function () { toast('Result link copied'); });
      } else {
        toast('Copy the page link to share your result');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initPhone();
    initForm();
    initReveal();
    initShare();
  });
})();
