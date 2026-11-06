/* MakonBook V64.2: parent header locale dropdown; server remains source of translations. */
(function () {
  'use strict';
  const root = document.querySelector('[data-mb642-parent-locale]');
  if (!root) return;
  const trigger = root.querySelector('[data-mb63-lang-trigger]');
  const label = root.querySelector('[data-mb63-lang-current]');
  const choices = Array.from(root.querySelectorAll('[data-mb63-lang-option]'));
  const current = (document.documentElement.lang || 'en').toLowerCase().split('-')[0];
  if (!trigger || !label) return;
  const available = ['en','ru','uz'];
  const text = {
    en:{platform:'Platform',results:'Results',parents:'Parents',faq:'FAQ',mock:'Mock exams',login:'Log in'},
    ru:{platform:'Платформа',results:'Результаты',parents:'Родителям',faq:'Вопросы и ответы',mock:'Пробные экзамены',login:'Войти'},
    uz:{platform:'Platforma',results:'Natijalar',parents:'Ota-onalarga',faq:'Savol-javob',mock:'Sinov imtihonlari',login:'Kirish'}
  }[current] || null;
  if (text) {
    const links = document.querySelectorAll('.mb56-nav-wrap .mb56-nav-links a');
    ['platform','results','parents','faq'].forEach((key,i) => {
      if (links[i]) links[i].textContent = text[key];
    });
    const mock = document.querySelector('.mb56-nav-wrap .mb56-btn-quiet');
    const login = document.querySelector('.mb56-nav-wrap .mb56-btn-login');
    if (mock) mock.textContent = text.mock;
    if (login) login.innerHTML = text.login + ' <span aria-hidden="true">↗</span>';
  }
  label.textContent = current.toUpperCase();
  choices.forEach(c => c.setAttribute('aria-selected', c.dataset.mb63LangOption === current ? 'true' : 'false'));
  const close = () => {root.classList.remove('is-open');trigger.setAttribute('aria-expanded','false')};
  trigger.addEventListener('click', () => {
    const open = !root.classList.contains('is-open');
    root.classList.toggle('is-open',open);
    trigger.setAttribute('aria-expanded',open ? 'true' : 'false');
    if (open) (choices.find(c => c.dataset.mb63LangOption===current)||choices[0])?.focus();
  });
  choices.forEach(c => c.addEventListener('click', () => {
    const next = c.dataset.mb63LangOption;
    close();
    if (!available.includes(next) || next === current) return;
    try {localStorage.setItem('makonbook.public.language.v62',next)} catch (_) {}
    const url = new URL(location.href);
    url.searchParams.set('lang',next);
    // Keep existing URL parameters such as report pagination.
    const animator = window.MakonBookLandingTransition;
    if (animator) animator.run(() => location.assign(url.href),520).catch(() => location.assign(url.href));
    else location.assign(url.href);
  }));
  document.addEventListener('pointerdown', e => {if (!root.contains(e.target)) close()});
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && root.classList.contains('is-open')) {close();trigger.focus()}
  });
})();
