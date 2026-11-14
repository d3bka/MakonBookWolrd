/* MakonBook V50.6 — MakonRoom: tabs, instant preview, auto-save, Mako reactions. */
(() => {
  'use strict';
  const page = document.querySelector('[data-room]');
  if (!page) return;
  const scene = page.querySelector('[data-room-scene]');
  const toast = page.querySelector('[data-room-toast]');
  const csrf = page.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  const mako = () => window.MakonPanda?.of(page.querySelector('.mr-mako [data-panda]'));
  let toastTimer = 0;

  function say(message, isError = false, ms = 2600) {
    toast.textContent = message;
    toast.classList.toggle('is-error', isError);
    toast.classList.add('is-open');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-open'), ms);
  }

  // ---- tabs
  const tabs = Array.from(page.querySelectorAll('[data-room-tab]'));
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    tabs.forEach((t) => { const on = t === tab; t.classList.toggle('is-active', on); t.setAttribute('aria-selected', on ? 'true' : 'false'); });
    page.querySelectorAll('[data-room-panel]').forEach((panel) => { panel.hidden = panel.dataset.roomPanel !== tab.dataset.roomTab; });
  }));

  // ---- show one item per slot in the scene
  function show(slot, code) {
    scene.querySelectorAll(`[data-room-slot="${slot}"]`).forEach((el) => {
      const mine = (el.dataset.roomItem || el.dataset.roomGlow) === code;
      if (mine) {
        el.removeAttribute('display');
        if (el.dataset.roomItem) { el.classList.remove('is-entering'); void el.getBoundingClientRect(); el.classList.add('is-entering'); }
      } else {
        el.setAttribute('display', 'none');
      }
    });
  }

  function markCards(slot, code) {
    page.querySelectorAll(`[data-room-pick][data-room-slot="${slot}"]`).forEach((card) => {
      const on = card.dataset.roomPick === code;
      card.classList.toggle('is-equipped', on);
      card.setAttribute('aria-pressed', on ? 'true' : 'false');
      const state = card.querySelector('.mr-state');
      if (state && card.dataset.unlocked === '1') state.innerHTML = on ? '<i class="bi bi-check-circle-fill"></i>' : '';
    });
  }

  function current(slot) {
    return page.querySelector(`[data-room-pick][data-room-slot="${slot}"].is-equipped`)?.dataset.roomPick;
  }

  page.querySelectorAll('[data-room-pick]').forEach((card) => card.addEventListener('click', async () => {
    const slot = card.dataset.roomSlot;
    const code = card.dataset.roomPick;
    const name = card.querySelector('strong')?.childNodes[0]?.textContent.trim() || 'Item';
    if (card.dataset.unlocked !== '1') {
      card.classList.remove('is-shake'); void card.offsetWidth; card.classList.add('is-shake');
      mako()?.set('thinking', 1800);
      say(`Locked — ${card.dataset.requirement}`);
      return;
    }
    const previous = current(slot);
    if (previous === code) { mako()?.set('happy', 900); return; }
    show(slot, code); markCards(slot, code);
    card.classList.remove('is-new'); card.querySelector('em')?.remove();
    mako()?.set(Math.random() < .3 ? 'love' : 'happy', 1500);
    try {
      const body = new URLSearchParams({ slot, item: code });
      const response = await fetch(page.dataset.equipUrl, {
        method: 'POST', body, credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || 'Could not save.');
      say(`${name} placed in your room.`);
    } catch (error) {
      if (previous) { show(slot, previous); markCards(slot, previous); }
      mako()?.set('worried', 1800);
      say(error.message || 'Could not save — try again.', true, 3200);
    }
  }));

  // ---- something new was unlocked since the last visit
  if (page.dataset.roomNew) {
    setTimeout(() => {
      mako()?.set('celebrate', 2400);
      const panda = page.querySelector('.mr-mako');
      if (window.MakonSeason && panda) {
        const r = panda.getBoundingClientRect();
        window.MakonSeason.burst(26, { x: r.left + r.width / 2, y: r.top + r.height / 3 });
      }
    }, 500);
  } else {
    setTimeout(() => mako()?.set('greet', 1800), 500);
  }
})();
