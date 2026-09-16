(() => {
  const toggle = document.querySelector('[data-notice-toggle]');
  const layer = document.querySelector('[data-notice-layer]');
  if (!toggle || !layer) return;

  const closers = layer.querySelectorAll('[data-notice-close]');
  const badge = document.querySelector('[data-notice-badge]');
  let markedRead = false;

  const getCookie = (name) => {
    const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1')}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : '';
  };

  const csrfToken = () => {
    const field = layer.querySelector('[data-notice-csrf-form] input[name=csrfmiddlewaretoken]');
    if (field && field.value) return field.value;
    const custom = getCookie('makonbook_csrftoken_v35') || getCookie('csrftoken');
    if (custom) return custom;
    const pair = document.cookie.split(';').map((part) => part.trim()).find((part) => /csrftoken/i.test((part.split('=')[0] || '')));
    return pair ? decodeURIComponent(pair.split('=').slice(1).join('=')) : '';
  };

  const markRead = async () => {
    if (markedRead) return;
    const url = layer.dataset.readUrl;
    if (!url) return;
    const body = new URLSearchParams();
    layer.querySelectorAll('[data-notice-id]').forEach((item) => {
      if (item.dataset.noticeId) body.append('ids', item.dataset.noticeId);
    });
    if (!body.toString()) return;
    markedRead = true;
    try {
      const response = await fetch(url, {
        method: 'POST',
        body,
        headers: {
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
        credentials: 'same-origin',
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error('mark-read failed');
      const remaining = Math.max(0, Number(data.unread) || 0);
      if (badge) {
        if (remaining) badge.textContent = String(remaining);
        else badge.remove();
      }
      layer.querySelectorAll('.makon-notice-item.is-unread').forEach((item) => item.classList.remove('is-unread'));
    } catch (_) {
      markedRead = false;
    }
  };

  const open = () => {
    layer.classList.add('is-open');
    layer.setAttribute('aria-hidden', 'false');
    toggle.setAttribute('aria-expanded', 'true');
    document.body.classList.add('makon-notice-open');
    markRead();
    const closeButton = layer.querySelector('.makon-notice-close');
    if (closeButton) closeButton.focus({ preventScroll: true });
  };

  const close = () => {
    layer.classList.remove('is-open');
    layer.setAttribute('aria-hidden', 'true');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('makon-notice-open');
  };

  toggle.addEventListener('click', () => {
    if (layer.classList.contains('is-open')) close();
    else open();
  });
  closers.forEach((item) => item.addEventListener('click', close));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && layer.classList.contains('is-open')) close();
  });
})();
