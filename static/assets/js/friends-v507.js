/* MakonBook V50.7 — Friends page: copy the code, tidy code input, confirm removal. */
(() => {
  'use strict';
  const page = document.querySelector('[data-friends]');
  if (!page) return;

  const codeBtn = page.querySelector('[data-friend-code]');
  const status = page.querySelector('[data-friend-code-status]');
  codeBtn?.addEventListener('click', async () => {
    const code = codeBtn.dataset.friendCode;
    try {
      await navigator.clipboard.writeText(code);
      codeBtn.classList.add('is-copied');
      if (status) status.textContent = 'Copied! Send it to a friend.';
      window.MakonMako?.react('happy', 'Code copied — now send it to a friend!', 2400);
    } catch (e) {
      if (status) status.textContent = `Your code: ${code}`;
    }
  });

  // ABCD2345 / abcd 2345 -> ABCD-2345 while typing
  const input = page.querySelector('[data-friend-code-input]');
  input?.addEventListener('input', () => {
    const body = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8);
    input.value = body.length > 4 ? `${body.slice(0, 4)}-${body.slice(4)}` : body;
  });

  page.querySelectorAll('[data-friend-remove]').forEach((form) => form.addEventListener('submit', (event) => {
    if (!window.confirm(`Remove ${form.dataset.friendRemove} from your friends?`)) event.preventDefault();
  }));
})();
