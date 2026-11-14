/* MakonBook V50.7 — duel challenges reach students on any page (World pages have their own popover). */
(() => {
  'use strict';
  const toast = document.querySelector('[data-challenge-toast]');
  if (!toast || document.querySelector('[data-world-shell]')) return;
  const csrf = toast.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
  const set = (sel, value) => { const el = toast.querySelector(sel); if (el) el.textContent = value; };
  let current = null, timer = 0, dismissed = new Set();

  async function poll() {
    if (document.hidden) return;
    try {
      const res = await fetch(toast.dataset.incomingUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' }, credentials: 'same-origin' });
      const data = await res.json();
      const invite = data && data.ok ? data.invite : null;
      if (!invite || dismissed.has(invite.id)) { if (!invite) hide(); return; }
      if (current && current.id === invite.id) return;
      current = invite;
      set('[data-challenge-initials]', invite.initials || '?');
      set('[data-challenge-name]', invite.requester);
      set('[data-challenge-kind]', invite.friend_challenge ? 'FRIEND CHALLENGE' : 'REMATCH REQUEST');
      set('[data-challenge-format]', `${invite.subject} · ${invite.mode}`);
      toast.hidden = false;
      requestAnimationFrame(() => toast.classList.add('is-open'));
      window.MakonMako?.react('surprised', `${invite.requester} challenged you!`, 2400);
    } catch (e) { /* offline or World closed: stay quiet */ }
  }

  function hide() { toast.classList.remove('is-open'); setTimeout(() => { toast.hidden = true; }, 250); current = null; }

  async function act(kind) {
    if (!current) return;
    const url = kind === 'accept' ? current.accept_url : current.decline_url;
    const id = current.id;
    try {
      const res = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await res.json().catch(() => ({}));
      if (kind === 'accept' && data.ok && data.room_url) { window.location.href = data.room_url; return; }
      if (kind === 'accept' && !data.ok) window.MakonMako?.react('worried', data.error || 'That challenge expired.', 2800);
    } catch (e) { /* keep the page usable */ }
    dismissed.add(id);
    hide();
  }

  toast.querySelector('[data-challenge-accept]').addEventListener('click', () => act('accept'));
  toast.querySelector('[data-challenge-decline]').addEventListener('click', () => act('decline'));
  poll();
  timer = setInterval(poll, 20000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
})();
