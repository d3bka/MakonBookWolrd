(() => {
  const form = document.querySelector('[data-audit-run-form]');
  const overlay = document.querySelector('[data-audit-overlay]');
  if (!form || !overlay) return;

  const button = form.querySelector('[data-audit-run-button]');
  const message = overlay.querySelector('[data-audit-message]');
  const detail = overlay.querySelector('[data-audit-detail]');
  const bar = overlay.querySelector('[data-audit-bar]');
  const inline = document.querySelector('[data-audit-inline]');
  const inlineBar = inline ? inline.querySelector('[data-audit-inline-bar]') : null;
  const inlineMessage = inline ? inline.querySelector('[data-audit-inline-message]') : null;
  const doneCounter = document.querySelector('[data-audit-done]');
  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]');
  let running = false;
  // V97: after an import the check starts by itself and reports progress inside
  // the card, so the reviewer can keep reading while the AI works.
  let quiet = false;

  const setProgress = (percent, text, subtext) => {
    const safe = Math.max(0, Math.min(100, Number(percent) || 0));
    if (quiet) {
      if (inlineBar) inlineBar.style.width = `${safe}%`;
      if (inlineMessage) inlineMessage.textContent = subtext ? `${text} · ${subtext}` : (text || 'Checking questions…');
      return;
    }
    if (bar) bar.style.width = `${safe}%`;
    if (message) message.textContent = text || 'Checking questions…';
    if (detail && subtext) detail.textContent = subtext;
  };

  const open = () => {
    if (quiet) {
      if (inline) inline.hidden = false;
      return;
    }
    overlay.classList.add('is-active');
    overlay.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('tic-upload-busy');
  };

  const close = () => {
    overlay.classList.remove('is-active');
    overlay.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('tic-upload-busy');
  };

  const requestBatch = async (restart) => {
    const body = new FormData();
    body.append('restart', restart ? '1' : '0');
    if (csrf) body.append('csrfmiddlewaretoken', csrf.value);
    const response = await fetch(form.action, {
      method: 'POST',
      body,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.detail || `AI check request failed (HTTP ${response.status}).`);
    return data;
  };

  const run = async () => {
    if (running) return;
    running = true;
    if (button) button.disabled = true;
    open();
    setProgress(2, 'Preparing the first AI batch…', quiet ? '' : 'No Redis or Celery worker is involved.');

    try {
      let first = true;
      const restartFirstBatch = form.dataset.auditRestart !== '0';
      while (true) {
        const data = await requestBatch(first && restartFirstBatch);
        first = false;
        if (doneCounter && data.done != null) doneCounter.textContent = data.done;
        setProgress(
          data.percent,
          data.message || `AI check: ${data.done || 0}/${data.total || 0}`,
          quiet ? '' : `Checked ${data.done || 0} of ${data.total || 0} questions.`
        );
        if (data.complete) break;
      }
      setProgress(100, 'AI answer check complete', quiet ? 'refreshing…' : 'Refreshing the review screen with the newest findings…');
      window.setTimeout(() => window.location.reload(), 650);
    } catch (error) {
      setProgress(0, 'AI answer check stopped', error.message || 'The AI provider could not complete the request.');
      if (button) button.disabled = false;
      running = false;
      if (!quiet) window.setTimeout(close, 3500);
    }
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    quiet = false;
    run();
  });

  if (form.hasAttribute('data-audit-autostart')) {
    quiet = true;
    run();
  }
})();
