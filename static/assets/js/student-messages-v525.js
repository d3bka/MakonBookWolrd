(function () {
  'use strict';

  var root = document.querySelector('[data-student-chat]');
  if (!root) return;
  root.dataset.chatReady = '5265';

  var form = root.querySelector('[data-chat-form]');
  var list = root.querySelector('[data-chat-messages]');
  var text = root.querySelector('[data-chat-text]');
  var file = root.querySelector('[data-chat-file]');
  var fileName = root.querySelector('[data-chat-file-name]');
  var media = root.querySelector('[data-chat-emoji-panel]');
  var mediaToggle = root.querySelector('[data-chat-emoji-toggle]');
  var stickerId = root.querySelector('[data-chat-sticker-id]');
  var selectedSticker = root.querySelector('[data-chat-selected-sticker]');
  var stickerGrid = root.querySelector('[data-chat-custom-stickers]');
  var stickerStatus = root.querySelector('[data-chat-sticker-status]');
  var themeToggle = root.querySelector('[data-chat-theme-toggle]');
  var themePanel = root.querySelector('[data-chat-theme-panel]');
  var stickerConfirm = root.querySelector('[data-sticker-confirm]');
  var packManager = root.querySelector('[data-chat-pack-manager]');
  var packList = root.querySelector('[data-chat-pack-list]');
  var packStrip = root.querySelector('[data-chat-pack-strip]');
  var confirmQueue = [];
  var pendingStickerFile = null;
  var pendingPackId = '';
  var lastId = parseInt(root.dataset.lastId || '0', 10) || 0;
  var sending = false;
  var mediaPinned = false;
  var hoverTimer = null;
  var mediaTransitionToken = 0;

  function csrf() {
    var match = document.cookie.match(/(?:^|; )makonbook_csrftoken_v35=([^;]+)/) || document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }
  function escapeHtml(value) { var div = document.createElement('div'); div.textContent = value == null ? '' : String(value); return div.innerHTML; }
  function safeLocalGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function safeLocalSet(key, value) { try { localStorage.setItem(key, value); return true; } catch (e) { return false; } }
  function safeLocalRemove(key) { try { localStorage.removeItem(key); } catch (e) {} }
  function jsonResponse(response) {
    if (response.redirected && /\/login\/?(?:\?|$)/.test(response.url || '')) throw new Error('Your session needs attention. Refresh once before signing in again.');
    return response.json().then(function (payload) { return {ok: response.ok, payload: payload}; });
  }

  var themeScope = (root.dataset.chatUserId || 'user') + '.' + (root.dataset.classroomId || 'room');
  var chatThemeKey = 'makonbook.chat.theme.v5261.' + themeScope;
  var chatBackgroundKey = 'makonbook.chat.background.v5261.' + themeScope;
  function currentCustomConfig() {
    var baseInput=root.querySelector('[data-chat-custom-base]'),accentInput=root.querySelector('[data-chat-custom-accent]'),patternInput=root.querySelector('[data-chat-custom-pattern]');
    return {name:'custom',base:baseInput?baseInput.value:'#f5f1ff',accent:accentInput?accentInput.value:'#7c3aed',pattern:patternInput?patternInput.value:'dots'};
  }
  function applyTheme(config) {
    var parsed = config;
    if (typeof config === 'string') { try { parsed = JSON.parse(config); } catch (e) { parsed = {name: config}; } }
    parsed = parsed || {name:'makon'};
    var personalBackground=safeLocalGet(chatBackgroundKey)||'';
    root.dataset.chatTheme = parsed.name || 'makon';
    root.dataset.chatCustomPattern = parsed.name==='custom'&&personalBackground ? 'image' : (parsed.pattern || 'dots');
    root.style.removeProperty('--v525-chat-custom-base');
    root.style.removeProperty('--v525-chat-custom-accent');
    root.style.removeProperty('--v526-chat-custom-image');
    if (parsed.name === 'custom') {
      root.style.setProperty('--v525-chat-custom-base', parsed.base || '#f5f1ff');
      root.style.setProperty('--v525-chat-custom-accent', parsed.accent || '#7c3aed');
      if(personalBackground) root.style.setProperty('--v526-chat-custom-image','url("'+personalBackground+'")');
    }
    var baseInput=root.querySelector('[data-chat-custom-base]'),accentInput=root.querySelector('[data-chat-custom-accent]'),patternInput=root.querySelector('[data-chat-custom-pattern]'),backgroundStatus=root.querySelector('[data-chat-custom-background-status]');
    if(baseInput&&parsed.base)baseInput.value=parsed.base;if(accentInput&&parsed.accent)accentInput.value=parsed.accent;if(patternInput&&parsed.pattern)patternInput.value=parsed.pattern;
    if(backgroundStatus)backgroundStatus.textContent=personalBackground?'Personal background active.':'No personal background uploaded.';
    root.querySelectorAll('[data-chat-theme]').forEach(function(btn){ btn.classList.toggle('is-active', btn.dataset.chatTheme === parsed.name); });
  }
  applyTheme(safeLocalGet(chatThemeKey) || JSON.stringify({name:'makon'}));

  function scrollBottom(smooth) { if (list) list.scrollTo({top:list.scrollHeight, behavior:smooth ? 'smooth' : 'auto'}); }
  function render(message) {
    if (!list || !message || root.querySelector('[data-message-id="' + message.id + '"]')) return;
    var article = document.createElement('article');
    article.className = 'v523-chat-message' + (message.is_mine ? ' is-mine' : '');
    article.dataset.messageId = message.id;
    var fileHtml = message.file_url ? '<a class="v523-chat-file" href="'+escapeHtml(message.file_url)+'" target="_blank" rel="noopener"><i class="bi bi-paperclip"></i>'+escapeHtml(message.file_name || 'Attachment')+'</a>' : '';
    var stickerHtml = message.sticker_url ? '<img class="v523-chat-sticker-message" src="'+escapeHtml(message.sticker_url)+'" alt="'+escapeHtml(message.sticker_title || 'Sticker')+'">' : '';
    article.innerHTML = '<span class="v523-chat-bubble-avatar">'+escapeHtml(message.initials || '?')+'</span><div><small>'+escapeHtml(message.author || 'User')+' · '+escapeHtml((message.created_at || '').split(' ').pop())+'</small>'+(message.text ? '<p>'+escapeHtml(message.text).replace(/\n/g,'<br>')+'</p>' : '')+stickerHtml+fileHtml+'</div>';
    list.appendChild(article);
    lastId = Math.max(lastId, parseInt(message.id || 0,10) || 0);
    root.dataset.lastId = lastId;
  }

  function setSelectedSticker(id, url, title) {
    if (!stickerId || !selectedSticker) return;
    stickerId.value = id || '';
    if (!id) { selectedSticker.hidden = true; selectedSticker.innerHTML = ''; return; }
    selectedSticker.hidden = false;
    selectedSticker.innerHTML = '<img src="'+escapeHtml(url || '')+'" alt=""><span>'+escapeHtml(title || 'Sticker selected')+'</span><button type="button" aria-label="Remove sticker" data-chat-clear-sticker><i class="bi bi-x"></i></button>';
  }

  function positionMediaPreview() {
    if (!media || !mediaToggle || mediaPinned || window.innerWidth <= 860) return;
    var rect = mediaToggle.getBoundingClientRect();
    var width = Math.min(360, Math.max(300, window.innerWidth - 24));
    var availableAbove = Math.max(280, rect.top - 22);
    var height = Math.min(520, availableAbove);
    var left = Math.max(12, Math.min(rect.left - 8, window.innerWidth - width - 12));
    var top = Math.max(12, rect.top - height - 10);
    root.style.setProperty('--v5265-media-preview-left', Math.round(left) + 'px');
    root.style.setProperty('--v5265-media-preview-top', Math.round(top) + 'px');
    root.style.setProperty('--v5265-media-preview-width', Math.round(width) + 'px');
    root.style.setProperty('--v5265-media-preview-height', Math.round(height) + 'px');
  }

  function openMedia(pinned) {
    if (!media) return;
    window.clearTimeout(hoverTimer);
    mediaTransitionToken += 1;
    if (pinned) mediaPinned = true;
    if (!mediaPinned) positionMediaPreview();
    media.hidden = false;
    media.classList.remove('is-closing');
    root.classList.toggle('is-media-docked', mediaPinned);
    root.classList.toggle('is-media-preview', !mediaPinned);
    requestAnimationFrame(function(){ requestAnimationFrame(function(){ media.classList.add('is-open'); }); });
  }
  function closeMedia(force) {
    if (!media || (mediaPinned && !force) || media.hidden) return;
    window.clearTimeout(hoverTimer);
    mediaPinned = false;
    var token=++mediaTransitionToken;
    media.classList.add('is-closing');
    media.classList.remove('is-open');
    window.setTimeout(function(){
      if(token!==mediaTransitionToken)return;
      root.classList.remove('is-media-docked','is-media-preview');
      media.classList.remove('is-closing');
      media.hidden = true;
    }, 350);
  }
  function scheduleHoverClose() { window.clearTimeout(hoverTimer); hoverTimer = window.setTimeout(function(){ if (!mediaPinned) closeMedia(true); }, 320); }

  if (mediaToggle && media) {
    mediaToggle.addEventListener('mouseenter', function(){ window.clearTimeout(hoverTimer); hoverTimer = window.setTimeout(function(){ if(!mediaPinned)openMedia(false); }, 120); });
    mediaToggle.addEventListener('mouseleave', scheduleHoverClose);
    mediaToggle.addEventListener('click', function(event){ event.preventDefault(); mediaPinned ? closeMedia(true) : openMedia(true); });
    media.addEventListener('mouseenter', function(){ window.clearTimeout(hoverTimer); });
    media.addEventListener('mouseleave', function(){ if (!mediaPinned) scheduleHoverClose(); });
  }
  root.querySelectorAll('[data-chat-sticker-panel-close]').forEach(function(button){ button.addEventListener('click', function(){ closeMedia(true); }); });

  window.addEventListener('resize', function(){ if (media && !media.hidden && !mediaPinned) positionMediaPreview(); });
  window.addEventListener('scroll', function(){ if (media && !media.hidden && !mediaPinned) positionMediaPreview(); }, true);
  root.querySelectorAll('[data-chat-media-undock]').forEach(function(button){ button.addEventListener('click', function(){ if(!media||media.hidden)return;mediaPinned=false;positionMediaPreview();root.classList.remove('is-media-docked');root.classList.add('is-media-preview'); }); });

  function activateMediaTab(name) {
    root.querySelectorAll('[data-chat-media-tab]').forEach(function(btn){ btn.classList.toggle('is-active', btn.dataset.chatMediaTab === name); });
    root.querySelectorAll('[data-chat-media-pane]').forEach(function(pane){ var active=pane.dataset.chatMediaPane===name; pane.hidden=!active; pane.classList.toggle('is-active',active); });
    var title = root.querySelector('[data-chat-media-title]'); if (title) title.textContent = name === 'gif' ? 'GIF' : name.charAt(0).toUpperCase()+name.slice(1);
    if (packManager) packManager.hidden = true;
  }
  root.querySelectorAll('[data-chat-media-tab]').forEach(function(btn){ btn.addEventListener('click', function(){ activateMediaTab(btn.dataset.chatMediaTab); }); });

  var emojiSearch=root.querySelector('[data-chat-emoji-search]');
  if(emojiSearch)emojiSearch.addEventListener('input',function(){
    var query=(emojiSearch.value||'').trim().toLowerCase();
    root.querySelectorAll('[data-emoji-group]').forEach(function(group){
      var visible=0;
      group.querySelectorAll('[data-emoji-key]').forEach(function(button){var show=!query||(button.dataset.emojiKey||'').indexOf(query)!==-1;button.hidden=!show;if(show)visible++;});
      group.hidden=visible===0;
    });
  });

  root.querySelectorAll('[data-chat-sticker]').forEach(function(button){ button.addEventListener('click', function(){ if(!text)return; text.value += button.dataset.chatSticker; text.dispatchEvent(new Event('input',{bubbles:true})); text.focus(); }); });

  function customStickerMarkup(sticker) {
    var wrap=document.createElement('div'); wrap.className='v523-custom-sticker'; wrap.dataset.customStickerWrap=sticker.id; wrap.dataset.packId=sticker.pack_id || 'loose'; wrap.dataset.isGif=sticker.is_gif ? '1' : '0';
    wrap.innerHTML='<button type="button" data-chat-custom-sticker="'+escapeHtml(sticker.id)+'" data-sticker-url="'+escapeHtml(sticker.url)+'" data-sticker-title="'+escapeHtml(sticker.title || '')+'"><img src="'+escapeHtml(sticker.url)+'" alt="'+escapeHtml(sticker.title || 'Custom sticker')+'"></button><button type="button" class="v523-sticker-delete" data-chat-sticker-delete="'+escapeHtml(sticker.id)+'" aria-label="Delete sticker"><i class="bi bi-x"></i></button>';
    return wrap;
  }
  function refreshGifGrid() {
    var gifGrid=root.querySelector('[data-chat-gif-grid]'), empty=root.querySelector('[data-chat-gif-empty]'); if(!gifGrid)return;
    gifGrid.innerHTML='';
    root.querySelectorAll('[data-custom-sticker-wrap][data-is-gif="1"]').forEach(function(sticker){ var clone=sticker.querySelector('[data-chat-custom-sticker]').cloneNode(true); clone.className='v525-gif-item'; gifGrid.appendChild(clone); });
    if(empty) empty.hidden=gifGrid.children.length>0;
  }
  refreshGifGrid();

  root.addEventListener('click', function(event){
    var clear=event.target.closest('[data-chat-clear-sticker]'); if(clear){setSelectedSticker('','','');return;}
    var custom=event.target.closest('[data-chat-custom-sticker]'); if(custom){setSelectedSticker(custom.dataset.chatCustomSticker,custom.dataset.stickerUrl,custom.dataset.stickerTitle); if(!mediaPinned)closeMedia(true); return;}
    var remove=event.target.closest('[data-chat-sticker-delete]'); if(!remove)return;
    event.preventDefault(); event.stopPropagation(); var id=remove.dataset.chatStickerDelete, template=root.dataset.stickerDeleteTemplate || ''; if(!id||!template)return;
    remove.disabled=true;
    fetch(template.replace('__id__',encodeURIComponent(id)),{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}})
      .then(jsonResponse).then(function(result){if(!result.ok)throw new Error(result.payload.error||'Could not delete sticker.');var wrap=root.querySelector('[data-custom-sticker-wrap="'+id+'"]');if(wrap)wrap.remove();if(stickerId&&stickerId.value===String(id))setSelectedSticker('','','');if(stickerStatus)stickerStatus.textContent='Sticker removed.';refreshGifGrid();})
      .catch(function(error){if(stickerStatus)stickerStatus.textContent=error.message||'Could not delete sticker.';remove.disabled=false;});
  });

  root.addEventListener('click',function(event){
    var button=event.target.closest('[data-chat-pack-filter]');if(!button||!root.contains(button))return;
    var value=button.dataset.chatPackFilter;
    root.querySelectorAll('[data-chat-pack-filter]').forEach(function(x){x.classList.toggle('is-active',x===button);});
    root.querySelectorAll('[data-custom-sticker-wrap]').forEach(function(item){item.hidden=value!=='all'&&item.dataset.packId!==value;});
  });

  function showStickerConfirm(uploaded, packId) {
    if(!uploaded||!stickerConfirm)return;
    pendingStickerFile=uploaded; pendingPackId=packId || '';
    var preview=stickerConfirm.querySelector('[data-sticker-confirm-preview]'), titleField=stickerConfirm.querySelector('[data-sticker-confirm-title]'), packField=stickerConfirm.querySelector('[data-sticker-confirm-pack]');
    if(preview){if(preview.dataset.objectUrl)URL.revokeObjectURL(preview.dataset.objectUrl);var objectUrl=URL.createObjectURL(uploaded);preview.src=objectUrl;preview.dataset.objectUrl=objectUrl;}
    if(titleField)titleField.value=uploaded.name.replace(/\.[^.]+$/,'').slice(0,80);
    if(packField)packField.value=pendingPackId;
    stickerConfirm.hidden=false;requestAnimationFrame(function(){stickerConfirm.classList.add('is-open');});
  }
  function closeStickerConfirm(clearQueue) {
    if(!stickerConfirm)return; stickerConfirm.classList.remove('is-open'); stickerConfirm.hidden=true;
    var preview=stickerConfirm.querySelector('[data-sticker-confirm-preview]'); if(preview&&preview.dataset.objectUrl){URL.revokeObjectURL(preview.dataset.objectUrl);preview.dataset.objectUrl='';}
    pendingStickerFile=null; pendingPackId=''; root.querySelectorAll('[data-chat-sticker-upload]').forEach(function(input){input.value='';});
    if(clearQueue) confirmQueue=[];
  }
  root.querySelectorAll('[data-chat-sticker-upload]').forEach(function(input){ input.addEventListener('change',function(){var uploaded=input.files&&input.files[0];if(uploaded)showStickerConfirm(uploaded,'');}); });
  root.addEventListener('change',function(event){var input=event.target.closest('[data-chat-pack-upload]');if(!input)return;confirmQueue=Array.prototype.slice.call(input.files||[]).map(function(file){return {file:file,packId:input.dataset.chatPackUpload};});var next=confirmQueue.shift();if(next)showStickerConfirm(next.file,next.packId);});

  if(stickerConfirm){
    stickerConfirm.querySelectorAll('[data-sticker-confirm-cancel]').forEach(function(btn){btn.addEventListener('click',function(){closeStickerConfirm(true);});});
    var confirmSave=stickerConfirm.querySelector('[data-sticker-confirm-save]');
    if(confirmSave)confirmSave.addEventListener('click',function(){
      if(!pendingStickerFile)return;confirmSave.disabled=true;if(stickerStatus)stickerStatus.textContent='Uploading…';
      var data=new FormData();data.append('sticker',pendingStickerFile);var titleField=stickerConfirm.querySelector('[data-sticker-confirm-title]'),packField=stickerConfirm.querySelector('[data-sticker-confirm-pack]');if(titleField)data.append('title',titleField.value||'');if(packField&&packField.value)data.append('pack_id',packField.value);
      fetch(root.dataset.stickerUploadUrl,{method:'POST',body:data,credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}}).then(jsonResponse)
        .then(function(result){if(!result.ok)throw new Error(result.payload.error||'Could not upload sticker.');var empty=root.querySelector('[data-chat-sticker-empty]');if(empty)empty.remove();if(stickerGrid)stickerGrid.prepend(customStickerMarkup(result.payload.sticker));setSelectedSticker(result.payload.sticker.id,result.payload.sticker.url,result.payload.sticker.title);if(stickerStatus)stickerStatus.textContent='Sticker added and selected.';refreshGifGrid();closeStickerConfirm(false);var next=confirmQueue.shift();if(next)setTimeout(function(){showStickerConfirm(next.file,next.packId);},120);})
        .catch(function(error){if(stickerStatus)stickerStatus.textContent=error.message||'Could not upload sticker.';})
        .finally(function(){confirmSave.disabled=false;});
    });
  }

  function openPackManager(){if(!packManager)return;root.querySelectorAll('[data-chat-media-pane]').forEach(function(p){p.hidden=true;});packManager.hidden=false;var title=root.querySelector('[data-chat-media-title]');if(title)title.textContent='Sticker packs';}
  function closePackManager(){if(!packManager)return;packManager.hidden=true;activateMediaTab('stickers');}
  root.querySelectorAll('[data-chat-pack-manager-open]').forEach(function(btn){btn.addEventListener('click',openPackManager);});
  root.querySelectorAll('[data-chat-pack-manager-close]').forEach(function(btn){btn.addEventListener('click',closePackManager);});

  var packCreateModal=root.querySelector('[data-chat-pack-create-modal]'),packForm=root.querySelector('[data-chat-pack-create]'),packName=root.querySelector('[data-chat-pack-create-name]'),packFiles=root.querySelector('[data-chat-pack-create-files]'),packCount=root.querySelector('[data-chat-pack-create-count]');
  function setPackCreate(open){if(!packCreateModal)return;if(open){packCreateModal.hidden=false;requestAnimationFrame(function(){packCreateModal.classList.add('is-open');});if(packName)setTimeout(function(){packName.focus();},80);}else{packCreateModal.classList.remove('is-open');setTimeout(function(){if(!packCreateModal.classList.contains('is-open'))packCreateModal.hidden=true;},190);}}
  root.querySelectorAll('[data-chat-pack-create-open]').forEach(function(btn){btn.addEventListener('click',function(){setPackCreate(true);});});
  root.querySelectorAll('[data-chat-pack-create-close]').forEach(function(btn){btn.addEventListener('click',function(){setPackCreate(false);});});
  if(packFiles)packFiles.addEventListener('change',function(){var count=packFiles.files?packFiles.files.length:0;if(packCount)packCount.textContent=count?count+' image'+(count===1?'':'s')+' selected. Each image will be confirmed before upload.':'No images selected. You can also add them later.';});
  function appendPackUi(pack){
    var empty=root.querySelector('[data-chat-pack-empty]');if(empty)empty.remove();
    if(packList){var row=document.createElement('article');row.dataset.chatPackRow=pack.id;row.innerHTML='<span><i class="bi bi-collection-fill"></i></span><div><strong>'+escapeHtml(pack.title)+'</strong><small>0 stickers</small></div><label title="Add images"><i class="bi bi-plus-lg"></i><input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif" hidden data-chat-pack-upload="'+pack.id+'"></label><button type="button" data-chat-pack-delete="'+pack.id+'" title="Remove pack"><i class="bi bi-trash3"></i></button>';packList.appendChild(row);}
    if(packStrip){var b=document.createElement('button');b.type='button';b.dataset.chatPackFilter=pack.id;b.textContent=pack.title;packStrip.appendChild(b);}
    var select=stickerConfirm&&stickerConfirm.querySelector('[data-sticker-confirm-pack]');if(select){var opt=document.createElement('option');opt.value=pack.id;opt.textContent=pack.title;select.appendChild(opt);}
  }
  if(packForm)packForm.addEventListener('submit',function(event){
    event.preventDefault();var title=(packName&&packName.value||'').trim();if(!title)return;
    var files=Array.prototype.slice.call(packFiles&&packFiles.files||[]),submit=packForm.querySelector('button[type="submit"]');if(submit)submit.disabled=true;
    var data=new FormData();data.append('title',title);
    fetch(root.dataset.packCreateUrl,{method:'POST',body:data,credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}}).then(jsonResponse).then(function(result){
      if(!result.ok)throw new Error(result.payload.error||'Could not create pack.');var pack=result.payload.pack;appendPackUi(pack);if(packName)packName.value='';if(packFiles)packFiles.value='';if(packCount)packCount.textContent='No images selected. You can also add them later.';setPackCreate(false);
      if(files.length){confirmQueue=files.map(function(uploaded){return {file:uploaded,packId:String(pack.id)};});var next=confirmQueue.shift();if(next)setTimeout(function(){showStickerConfirm(next.file,next.packId);},210);}
    }).catch(function(error){if(stickerStatus)stickerStatus.textContent=error.message||'Could not create pack.';}).finally(function(){if(submit)submit.disabled=false;});
  });

  root.addEventListener('click',function(event){var btn=event.target.closest('[data-chat-pack-delete]');if(!btn)return;var id=btn.dataset.chatPackDelete,template=root.dataset.packDeleteTemplate||'';if(!id||!template)return;fetch(template.replace('__id__',encodeURIComponent(id)),{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}}).then(jsonResponse).then(function(result){if(!result.ok)throw new Error(result.payload.error||'Could not remove pack.');var row=root.querySelector('[data-chat-pack-row="'+id+'"]');if(row)row.remove();var filter=root.querySelector('[data-chat-pack-filter="'+id+'"]');if(filter)filter.remove();root.querySelectorAll('[data-custom-sticker-wrap][data-pack-id="'+id+'"]').forEach(function(item){item.dataset.packId='loose';});var option=stickerConfirm&&stickerConfirm.querySelector('[data-sticker-confirm-pack] option[value="'+id+'"]');if(option)option.remove();}).catch(function(error){if(stickerStatus)stickerStatus.textContent=error.message;});});

  if(file)file.addEventListener('change',function(){if(fileName)fileName.textContent=file.files&&file.files[0]?file.files[0].name:'';});
  if(themeToggle&&themePanel)themeToggle.addEventListener('click',function(){var open=themePanel.hidden;themePanel.hidden=!open;themePanel.classList.toggle('is-open',open);});
  root.querySelectorAll('[data-chat-theme-close]').forEach(function(btn){btn.addEventListener('click',function(){if(themePanel){themePanel.classList.remove('is-open');setTimeout(function(){themePanel.hidden=true;},180);}});});
  root.querySelectorAll('[data-chat-theme]').forEach(function(btn){btn.addEventListener('click',function(){var value={name:btn.dataset.chatTheme};safeLocalSet(chatThemeKey,JSON.stringify(value));applyTheme(value);});});
  var customTheme=root.querySelector('[data-chat-theme-custom]');if(customTheme)customTheme.addEventListener('click',function(){var value=currentCustomConfig();safeLocalSet(chatThemeKey,JSON.stringify(value));applyTheme(value);});

  function compressBackground(uploaded,done,fail){
    if(!uploaded||!/^image\/(?:jpeg|png|webp)$/.test(uploaded.type||'')){fail('Choose a JPG, PNG or WEBP image.');return;}
    if(uploaded.size>8*1024*1024){fail('Background image must be 8 MB or smaller.');return;}
    var reader=new FileReader();reader.onerror=function(){fail('Could not read that image.');};reader.onload=function(){var image=new Image();image.onerror=function(){fail('Could not decode that image.');};image.onload=function(){var maxW=1600,maxH=1200,scale=Math.min(1,maxW/image.width,maxH/image.height),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));var ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,canvas.width,canvas.height);var dataUrl=canvas.toDataURL('image/webp',.8);if(dataUrl.length>1900000)dataUrl=canvas.toDataURL('image/jpeg',.68);if(dataUrl.length>2300000){fail('This image is still too large after optimization. Try a smaller image.');return;}done(dataUrl);};image.src=reader.result;};reader.readAsDataURL(uploaded);
  }
  var backgroundInput=root.querySelector('[data-chat-custom-background]'),backgroundStatus=root.querySelector('[data-chat-custom-background-status]'),backgroundClear=root.querySelector('[data-chat-custom-background-clear]');
  if(backgroundInput)backgroundInput.addEventListener('change',function(){var uploaded=backgroundInput.files&&backgroundInput.files[0];if(!uploaded)return;if(backgroundStatus)backgroundStatus.textContent='Optimizing background…';compressBackground(uploaded,function(dataUrl){if(!safeLocalSet(chatBackgroundKey,dataUrl)){if(backgroundStatus)backgroundStatus.textContent='Browser storage is full. Remove another custom background first.';return;}var value=currentCustomConfig();safeLocalSet(chatThemeKey,JSON.stringify(value));applyTheme(value);if(backgroundStatus)backgroundStatus.textContent='Personal background saved for this classroom.';backgroundInput.value='';},function(message){if(backgroundStatus)backgroundStatus.textContent=message;backgroundInput.value='';});});
  if(backgroundClear)backgroundClear.addEventListener('click',function(){safeLocalRemove(chatBackgroundKey);applyTheme(safeLocalGet(chatThemeKey)||JSON.stringify(currentCustomConfig()));if(backgroundStatus)backgroundStatus.textContent='Personal background removed.';});


  var filter=root.querySelector('[data-chat-filter]');if(filter)filter.addEventListener('input',function(){var query=filter.value.trim().toLowerCase();root.querySelectorAll('[data-chat-room]').forEach(function(room){room.hidden=!!query&&((room.dataset.search||'').indexOf(query)===-1);});});

  if(form){
    form.addEventListener('submit',function(event){event.preventDefault();if(sending)return;var data=new FormData(form),hasText=!!String(data.get('message')||'').trim(),hasFile=!!(file&&file.files&&file.files[0]),hasSticker=!!String(data.get('sticker_id')||'').trim();if(!hasText&&!hasFile&&!hasSticker)return;sending=true;form.classList.add('is-sending');fetch(root.dataset.sendUrl,{method:'POST',body:data,credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}}).then(jsonResponse).then(function(result){if(!result.ok)throw new Error(result.payload.error||'Send failed');if(result.payload.message)render(result.payload.message);form.reset();setSelectedSticker('','','');if(fileName)fileName.textContent='';if(text)text.style.height='auto';scrollBottom(true);}).catch(function(error){form.classList.add('has-error');if(stickerStatus)stickerStatus.textContent=error.message||'Could not send message.';setTimeout(function(){form.classList.remove('has-error');},600);}).finally(function(){sending=false;form.classList.remove('is-sending');});});
    if(text){text.addEventListener('input',function(){text.style.height='auto';text.style.height=Math.min(text.scrollHeight,130)+'px';});text.addEventListener('keydown',function(event){if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();if(form.requestSubmit)form.requestSubmit();else form.submit();}});}
  }

  var pollTimer=null;
  function schedulePoll(delay){if(pollTimer)clearTimeout(pollTimer);pollTimer=setTimeout(poll,delay);}
  function poll(){if(!root.dataset.fetchUrl)return;if(document.hidden){schedulePoll(15000);return;}fetch(root.dataset.fetchUrl+'?last_id='+encodeURIComponent(lastId),{credentials:'same-origin',cache:'no-store',headers:{'X-Requested-With':'XMLHttpRequest'}}).then(function(response){if(response.redirected&&/\/login\/?/.test(response.url||''))throw new Error('auth');if(!response.ok)throw new Error('poll');return response.json();}).then(function(payload){var had=(payload.messages||[]).length;(payload.messages||[]).forEach(render);if(had)scrollBottom(true);}).catch(function(){}).finally(function(){schedulePoll(5000);});}
  document.addEventListener('visibilitychange',function(){if(!document.hidden&&root.dataset.fetchUrl)schedulePoll(150);});
  if(list)scrollBottom(false);if(root.dataset.fetchUrl)schedulePoll(2200);
})();
