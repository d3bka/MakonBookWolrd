(function () {
  'use strict';

  var root = document.querySelector('[data-student-chat]');
  if (!root) return;

  var form = root.querySelector('[data-chat-form]');
  var list = root.querySelector('[data-chat-messages]');
  var text = root.querySelector('[data-chat-text]');
  var file = root.querySelector('[data-chat-file]');
  var fileName = root.querySelector('[data-chat-file-name]');
  var panel = root.querySelector('[data-chat-emoji-panel]');
  var toggle = root.querySelector('[data-chat-emoji-toggle]');
  var stickerId = root.querySelector('[data-chat-sticker-id]');
  var selectedSticker = root.querySelector('[data-chat-selected-sticker]');
  var stickerUpload = root.querySelector('[data-chat-sticker-upload]');
  var stickerGrid = root.querySelector('[data-chat-custom-stickers]');
  var stickerStatus = root.querySelector('[data-chat-sticker-status]');
  var themeToggle = root.querySelector('[data-chat-theme-toggle]');
  var themePanel = root.querySelector('[data-chat-theme-panel]');
  var stickerConfirm = root.querySelector('[data-sticker-confirm]');
  var pendingStickerFile = null;
  var lastId = parseInt(root.dataset.lastId || '0', 10) || 0;
  var sending = false;

  function csrf() {
    var match = document.cookie.match(/(?:^|; )makonbook_csrftoken_v35=([^;]+)/) || document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value || '';
    return div.innerHTML;
  }

  function safeLocalGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function safeLocalSet(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  var chatThemeKey = 'makonbook.chat.theme.' + (root.dataset.chatUserId || 'user') + '.' + (root.dataset.classroomId || 'room');
  function applyTheme(config) {
    var parsed = config;
    if (typeof config === 'string') {
      try { parsed = JSON.parse(config); } catch (e) { parsed = {name: config}; }
    }
    parsed = parsed || {name:'makon'};
    root.dataset.chatTheme = parsed.name || 'makon';
    root.style.removeProperty('--v524-chat-custom-base');
    root.style.removeProperty('--v524-chat-custom-accent');
    if (parsed.name === 'custom') {
      root.style.setProperty('--v524-chat-custom-base', parsed.base || '#f5f1ff');
      root.style.setProperty('--v524-chat-custom-accent', parsed.accent || '#7c3aed');
    }
    root.querySelectorAll('[data-chat-theme]').forEach(function(btn){btn.classList.toggle('is-active', btn.dataset.chatTheme === parsed.name);});
  }
  applyTheme(safeLocalGet(chatThemeKey) || JSON.stringify({name:'makon'}));

  function scrollBottom(smooth) {
    if (!list) return;
    list.scrollTo({ top: list.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }

  function render(message) {
    if (!list || !message || root.querySelector('[data-message-id="' + message.id + '"]')) return;
    var article = document.createElement('article');
    article.className = 'v523-chat-message' + (message.is_mine ? ' is-mine' : '');
    article.dataset.messageId = message.id;
    var fileHtml = message.file_url
      ? '<a class="v523-chat-file" href="' + escapeHtml(message.file_url) + '" target="_blank" rel="noopener"><i class="bi bi-paperclip"></i>' + escapeHtml(message.file_name || 'Attachment') + '</a>'
      : '';
    var stickerHtml = message.sticker_url
      ? '<img class="v523-chat-sticker-message" src="' + escapeHtml(message.sticker_url) + '" alt="' + escapeHtml(message.sticker_title || 'Sticker') + '">'
      : '';
    article.innerHTML = '<span class="v523-chat-bubble-avatar">' + escapeHtml(message.initials || '?') + '</span><div><small>' +
      escapeHtml(message.author || 'User') + ' · ' + escapeHtml((message.created_at || '').split(' ').pop()) + '</small>' +
      (message.text ? '<p>' + escapeHtml(message.text).replace(/\n/g, '<br>') + '</p>' : '') + stickerHtml + fileHtml + '</div>';
    list.appendChild(article);
    lastId = Math.max(lastId, parseInt(message.id || 0, 10) || 0);
    root.dataset.lastId = lastId;
  }

  function setSelectedSticker(id, url, title) {
    if (!stickerId || !selectedSticker) return;
    stickerId.value = id || '';
    if (!id) {
      selectedSticker.hidden = true;
      selectedSticker.innerHTML = '';
      return;
    }
    selectedSticker.hidden = false;
    selectedSticker.innerHTML = '<img src="' + escapeHtml(url || '') + '" alt=""><span>' + escapeHtml(title || 'Sticker selected') + '</span><button type="button" aria-label="Remove sticker" data-chat-clear-sticker><i class="bi bi-x"></i></button>';
  }

  function customStickerMarkup(sticker) {
    var wrap = document.createElement('div');
    wrap.className = 'v523-custom-sticker';
    wrap.dataset.customStickerWrap = sticker.id;
    wrap.innerHTML = '<button type="button" data-chat-custom-sticker="' + escapeHtml(String(sticker.id)) + '" data-sticker-url="' + escapeHtml(sticker.url) + '" data-sticker-title="' + escapeHtml(sticker.title || '') + '"><img src="' + escapeHtml(sticker.url) + '" alt="' + escapeHtml(sticker.title || 'Custom sticker') + '"></button><button type="button" class="v523-sticker-delete" data-chat-sticker-delete="' + escapeHtml(String(sticker.id)) + '" aria-label="Delete sticker"><i class="bi bi-x"></i></button>';
    return wrap;
  }

  if (list) scrollBottom(false);
  if (toggle && panel) toggle.addEventListener('click', function () { panel.hidden = !panel.hidden; });
  root.querySelectorAll('[data-chat-sticker-panel-close]').forEach(function (button) {
    button.addEventListener('click', function () { if (panel) panel.hidden = true; });
  });
  root.querySelectorAll('[data-chat-sticker]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (!text) return;
      text.value += (text.value ? ' ' : '') + button.dataset.chatSticker;
      text.focus();
      if (panel) panel.hidden = true;
    });
  });

  root.addEventListener('click', function (event) {
    var clear = event.target.closest('[data-chat-clear-sticker]');
    if (clear) {
      setSelectedSticker('', '', '');
      return;
    }
    var custom = event.target.closest('[data-chat-custom-sticker]');
    if (custom) {
      setSelectedSticker(custom.dataset.chatCustomSticker, custom.dataset.stickerUrl, custom.dataset.stickerTitle);
      if (panel) panel.hidden = true;
      return;
    }
    var remove = event.target.closest('[data-chat-sticker-delete]');
    if (!remove) return;
    event.preventDefault();
    event.stopPropagation();
    var id = remove.dataset.chatStickerDelete;
    var template = root.dataset.stickerDeleteTemplate || '';
    if (!template || !id) return;
    remove.disabled = true;
    fetch(template.replace('__id__', encodeURIComponent(id)), {
      method: 'POST', credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (response) {
      if (!response.ok) throw new Error('Could not delete sticker.');
      var wrap = root.querySelector('[data-custom-sticker-wrap="' + id + '"]');
      if (wrap) wrap.remove();
      if (stickerId && stickerId.value === String(id)) setSelectedSticker('', '', '');
      if (stickerStatus) stickerStatus.textContent = 'Sticker removed.';
    }).catch(function (error) {
      if (stickerStatus) stickerStatus.textContent = error.message || 'Could not delete sticker.';
      remove.disabled = false;
    });
  });

  function closeStickerConfirm() {
    if (!stickerConfirm) return;
    stickerConfirm.hidden = true;
    stickerConfirm.classList.remove('is-open');
    var preview = stickerConfirm.querySelector('[data-sticker-confirm-preview]');
    if (preview && preview.dataset.objectUrl) { URL.revokeObjectURL(preview.dataset.objectUrl); preview.dataset.objectUrl = ''; }
    pendingStickerFile = null;
    if (stickerUpload) stickerUpload.value = '';
  }

  if (stickerUpload) stickerUpload.addEventListener('change', function () {
    var uploaded = stickerUpload.files && stickerUpload.files[0];
    if (!uploaded || !root.dataset.stickerUploadUrl || !stickerConfirm) return;
    pendingStickerFile = uploaded;
    var preview = stickerConfirm.querySelector('[data-sticker-confirm-preview]');
    var titleField = stickerConfirm.querySelector('[data-sticker-confirm-title]');
    if (preview) {
      var objectUrl = URL.createObjectURL(uploaded);
      preview.src = objectUrl; preview.dataset.objectUrl = objectUrl;
    }
    if (titleField) titleField.value = uploaded.name.replace(/\.[^.]+$/, '').slice(0,80);
    stickerConfirm.hidden = false;
    requestAnimationFrame(function(){stickerConfirm.classList.add('is-open');});
  });
  if (stickerConfirm) {
    stickerConfirm.querySelectorAll('[data-sticker-confirm-cancel]').forEach(function(btn){btn.addEventListener('click',closeStickerConfirm);});
    var confirmSave = stickerConfirm.querySelector('[data-sticker-confirm-save]');
    if (confirmSave) confirmSave.addEventListener('click', function () {
      if (!pendingStickerFile) return;
      confirmSave.disabled = true;
      if (stickerStatus) stickerStatus.textContent = 'Uploading…';
      var data = new FormData(); data.append('sticker', pendingStickerFile);
      var titleField = stickerConfirm.querySelector('[data-sticker-confirm-title]');
      if (titleField) data.append('title', titleField.value || '');
      fetch(root.dataset.stickerUploadUrl, {method:'POST', body:data, credentials:'same-origin', headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}})
        .then(function(response){return response.json().then(function(payload){return {ok:response.ok,payload:payload};});})
        .then(function(result){if(!result.ok)throw new Error(result.payload.error||'Could not upload sticker.');var empty=root.querySelector('[data-chat-sticker-empty]');if(empty)empty.remove();if(stickerGrid)stickerGrid.prepend(customStickerMarkup(result.payload.sticker));setSelectedSticker(result.payload.sticker.id,result.payload.sticker.url,result.payload.sticker.title);if(stickerStatus)stickerStatus.textContent='Sticker added and selected.';if(panel)panel.hidden=true;closeStickerConfirm();})
        .catch(function(error){if(stickerStatus)stickerStatus.textContent=error.message||'Could not upload sticker.';})
        .finally(function(){confirmSave.disabled=false;});
    });
  }

  if (file) file.addEventListener('change', function () {
    if (fileName) fileName.textContent = file.files && file.files[0] ? file.files[0].name : '';
  });

  if (themeToggle && themePanel) themeToggle.addEventListener('click', function () { themePanel.hidden = !themePanel.hidden; if (!themePanel.hidden) requestAnimationFrame(function(){themePanel.classList.add('is-open');}); else themePanel.classList.remove('is-open'); });
  root.querySelectorAll('[data-chat-theme-close]').forEach(function(btn){btn.addEventListener('click',function(){if(themePanel){themePanel.classList.remove('is-open');setTimeout(function(){themePanel.hidden=true;},180);}});});
  root.querySelectorAll('[data-chat-theme]').forEach(function(btn){btn.addEventListener('click',function(){var value={name:btn.dataset.chatTheme};safeLocalSet(chatThemeKey,JSON.stringify(value));applyTheme(value);});});
  var customTheme = root.querySelector('[data-chat-theme-custom]');
  if (customTheme) customTheme.addEventListener('click',function(){var base=root.querySelector('[data-chat-custom-base]'),accent=root.querySelector('[data-chat-custom-accent]');var value={name:'custom',base:base?base.value:'#f5f1ff',accent:accent?accent.value:'#7c3aed'};safeLocalSet(chatThemeKey,JSON.stringify(value));applyTheme(value);});

  var filter = root.querySelector('[data-chat-filter]');
  if (filter) filter.addEventListener('input', function () {
    var query = filter.value.trim().toLowerCase();
    root.querySelectorAll('[data-chat-room]').forEach(function (room) {
      room.hidden = !!query && ((room.dataset.search || '').indexOf(query) === -1);
    });
  });

  if (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (sending) return;
      var data = new FormData(form);
      var hasText = !!String(data.get('message') || '').trim();
      var hasFile = !!(file && file.files && file.files[0]);
      var hasSticker = !!String(data.get('sticker_id') || '').trim();
      if (!hasText && !hasFile && !hasSticker) return;
      sending = true;
      form.classList.add('is-sending');
      fetch(root.dataset.sendUrl, {
        method: 'POST', body: data, credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).then(function (response) {
        return response.json().then(function (payload) { if (!response.ok) throw new Error(payload.error || 'Send failed'); return payload; });
      }).then(function (payload) {
        if (payload.message) render(payload.message);
        form.reset();
        setSelectedSticker('', '', '');
        if (fileName) fileName.textContent = '';
        if (text) text.style.height = 'auto';
        scrollBottom(true);
      }).catch(function (error) {
        form.classList.add('has-error');
        if (stickerStatus) stickerStatus.textContent = error.message || 'Could not send message.';
        window.setTimeout(function () { form.classList.remove('has-error'); }, 600);
      }).finally(function () {
        sending = false;
        form.classList.remove('is-sending');
      });
    });
    if (text) {
      text.addEventListener('input', function () {
        text.style.height = 'auto';
        text.style.height = Math.min(text.scrollHeight, 130) + 'px';
      });
      text.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          if (form.requestSubmit) form.requestSubmit(); else form.submit();
        }
      });
    }
  }

  var pollTimer = null;
  function schedulePoll(delay) {
    if (pollTimer) window.clearTimeout(pollTimer);
    pollTimer = window.setTimeout(poll, delay);
  }
  function poll() {
    if (!root.dataset.fetchUrl) return;
    if (document.hidden) { schedulePoll(12000); return; }
    fetch(root.dataset.fetchUrl + '?last_id=' + encodeURIComponent(lastId), { credentials: 'same-origin', cache: 'no-store' })
      .then(function (response) { if (!response.ok) throw new Error('poll'); return response.json(); })
      .then(function (payload) {
        var had = (payload.messages || []).length;
        (payload.messages || []).forEach(render);
        if (had) scrollBottom(true);
      }).catch(function () {}).finally(function () { schedulePoll(3500); });
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && root.dataset.fetchUrl) schedulePoll(120);
  });
  if (root.dataset.fetchUrl) schedulePoll(1800);
})();
