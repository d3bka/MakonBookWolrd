(function(){
  'use strict';
  function csrf(){
    var field=document.querySelector('input[name="csrfmiddlewaretoken"]');
    if(field&&field.value)return field.value;
    var cookies={};
    document.cookie.split(';').forEach(function(part){var bits=part.trim().split('=');if(!bits[0])return;cookies[bits.shift()]=decodeURIComponent(bits.join('=')||'');});
    if(cookies.makonbook_csrftoken_v35)return cookies.makonbook_csrftoken_v35;
    if(cookies.csrftoken)return cookies.csrftoken;
    var name=Object.keys(cookies).find(function(key){return key.toLowerCase().indexOf('csrftoken')!==-1;});
    return name?cookies[name]:'';
  }
  function toast(message,type){
    var stack=document.querySelector('[data-v524-toast-stack]');
    if(!stack){stack=document.createElement('div');stack.className='v524-toast-stack';stack.setAttribute('data-v524-toast-stack','');stack.setAttribute('aria-live','polite');document.body.appendChild(stack);}
    var el=document.createElement('div');el.className='v524-toast '+(type||'success')+' v50211-toast-enter';
    el.innerHTML='<i class="bi bi-'+(type==='error'?'exclamation-octagon-fill':'check-circle-fill')+'"></i><span></span><button type="button"><i class="bi bi-x"></i></button>';
    el.querySelector('span').textContent=message; stack.appendChild(el);
    requestAnimationFrame(function(){el.classList.add('is-visible');});
    function close(){el.classList.add('is-leaving');setTimeout(function(){el.remove();},260);}
    el.querySelector('button').addEventListener('click',close);setTimeout(close,4400);
  }
  window.makonToast=toast;

  function syncModalState(){
    var hasStaffContentModal=!!document.querySelector('.sf28-modal-layer.is-open');
    document.body.classList.toggle('v50211-modal-open',hasStaffContentModal);
    var hasAnyModal=hasStaffContentModal||!!document.querySelector('.mb50-notice-layer.is-open,.mb50-command-layer.is-open,.mb50-more-layer.is-open,.mb50-customize-layer.is-open');
    document.documentElement.classList.toggle('mb50-modal-open',hasAnyModal);
  }
  function openLayer(layer){
    if(!layer)return;
    layer._v50211LastFocus=document.activeElement;
    layer.classList.add('is-open');layer.setAttribute('aria-hidden','false');syncModalState();
    setTimeout(function(){var target=layer.querySelector('input:not([type=hidden]):not([disabled]),select:not([disabled]),textarea:not([disabled]),button:not([data-v50211-modal-close]):not([disabled])');if(target)target.focus({preventScroll:true});},35);
  }
  function resetDangerForms(scope){
    (scope||document).querySelectorAll('form[data-v50212-danger-confirm]').forEach(function(form){
      delete form.dataset.v50212Armed;
      if(form._v50212DangerTimer){clearTimeout(form._v50212DangerTimer);form._v50212DangerTimer=null;}
      var button=form.querySelector('[data-v50212-danger-button]');
      if(!button)return;
      button.classList.remove('is-confirming');
      var label=button.querySelector('span');if(label&&button.dataset.v50212OriginalLabel)label.textContent=button.dataset.v50212OriginalLabel;
      button.removeAttribute('title');
    });
  }
  function closeLayer(layer){
    if(!layer)return;
    resetDangerForms(layer);
    layer.classList.remove('is-open');layer.setAttribute('aria-hidden','true');syncModalState();
    var previous=layer._v50211LastFocus;if(previous&&previous.isConnected&&typeof previous.focus==='function')previous.focus({preventScroll:true});
  }
  // Keep modal/sidebar stacking correct even for older staff widgets that
  // toggle .is-open themselves instead of calling the shared helper.
  document.querySelectorAll('.sf28-modal-layer').forEach(function(layer){
    new MutationObserver(syncModalState).observe(layer,{attributes:true,attributeFilter:['class','aria-hidden']});
  });
  syncModalState();
  document.querySelectorAll('[data-v50211-modal-open]').forEach(function(btn){btn.addEventListener('click',function(){openLayer(document.querySelector('[data-v50211-modal="'+btn.dataset.v50211ModalOpen+'"]'));});});
  document.querySelectorAll('[data-v50211-modal-close]').forEach(function(btn){btn.addEventListener('click',function(){closeLayer(btn.closest('.sf28-modal-layer'));});});
  document.addEventListener('keydown',function(e){if(e.key!=='Escape')return;var open=document.querySelector('.sf28-modal-layer.is-open[data-v50211-modal],.sf28-modal-layer.is-open[data-v50211-homework-delete-modal]');if(open)closeLayer(open);});

  // Destructive E-class actions use an intentional two-step confirmation inside
  // the editor instead of the browser's rough native confirm dialog.
  document.addEventListener('submit',function(e){
    var form=e.target.closest&&e.target.closest('form[data-v50212-danger-confirm]');if(!form)return;
    if(form.dataset.v50212Armed==='1')return;
    e.preventDefault();
    form.dataset.v50212Armed='1';
    var button=form.querySelector('[data-v50212-danger-button]');
    if(button){
      var label=button.querySelector('span');
      if(label&&!button.dataset.v50212OriginalLabel)button.dataset.v50212OriginalLabel=label.textContent.trim();
      if(label)label.textContent='Confirm delete';
      button.classList.add('is-confirming');
      button.title=form.dataset.v50212DangerConfirm||'Confirm permanent deletion';
      button.focus({preventScroll:true});
    }
    form._v50212DangerTimer=setTimeout(function(){resetDangerForms(form);},4500);
  });

  // Server-backed live filters without a full document reload.
  var timers=new WeakMap();
  function liveFetch(form,url){
    var regionId=form.dataset.v50211Region,region=regionId?document.querySelector('[data-v50211-live-region="'+regionId+'"]'):null;if(!region)return;
    region.classList.add('is-loading');
    fetch(url,{credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'}}).then(function(r){if(!r.ok)throw new Error();return r.text();}).then(function(html){
      var doc=new DOMParser().parseFromString(html,'text/html');var fresh=doc.querySelector('[data-v50211-live-region="'+regionId+'"]');if(!fresh)throw new Error();
      region.innerHTML=fresh.innerHTML;region.classList.remove('is-loading');history.replaceState({},'',url);bindRegionPagination(form,region);restoreViewToggles(region);
      var countFresh=doc.querySelector('[data-v50211-result-count]'),countCurrent=document.querySelector('[data-v50211-result-count]');if(countFresh&&countCurrent)countCurrent.textContent=countFresh.textContent;
    }).catch(function(){region.classList.remove('is-loading');toast('Could not refresh these results.','error');});
  }
  function formActionUrl(form){
    var raw=form.getAttribute('action')||window.location.pathname;
    return new URL(raw,window.location.href).href;
  }
  function schedule(form){clearTimeout(timers.get(form));timers.set(form,setTimeout(function(){var qs=new URLSearchParams(new FormData(form));qs.delete('page');liveFetch(form,formActionUrl(form).split('?')[0]+'?'+qs.toString());},240));}
  function bindRegionPagination(form,region){region.querySelectorAll('a[href*="page="]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();liveFetch(form,a.href);});});}
  function restoreViewToggles(scope){(scope||document).querySelectorAll('[data-sf29-view-toggle]').forEach(function(control){var key=control.dataset.sf29ViewToggle||'default',view='list';try{view=localStorage.getItem('makonbook.directory.'+key)||'list';}catch(_e){}var target=document.querySelector(control.dataset.sf29Target||'');if(!target)return;target.classList.toggle('is-grid',view==='grid');target.classList.toggle('is-list',view!=='grid');control.querySelectorAll('button[data-view]').forEach(function(x){x.classList.toggle('is-active',x.dataset.view===view);});});}
  document.querySelectorAll('form[data-v50211-live-form]').forEach(function(form){
    form.querySelectorAll('input[type=search]').forEach(function(x){x.addEventListener('input',function(){schedule(form);});});
    form.querySelectorAll('select').forEach(function(x){x.addEventListener('change',function(){schedule(form);});});
    var region=document.querySelector('[data-v50211-live-region="'+form.dataset.v50211Region+'"]');if(region)bindRegionPagination(form,region);
  });

  // Homework deletion uses a real modal and AJAX; no browser confirm and no page reload.
  var deleteLayer=document.querySelector('[data-v50211-homework-delete-modal]');
  document.addEventListener('click',function(e){
    var btn=e.target.closest('[data-v50211-homework-delete]');if(!btn||!deleteLayer)return;
    deleteLayer.querySelector('[name=assignment_id]').value=btn.dataset.assignmentId||'';
    var title=deleteLayer.querySelector('[data-v50211-delete-title]');if(title)title.textContent=btn.dataset.title||'this assignment';openLayer(deleteLayer);
  });
  function homeworkDeleteRequest(url,form){
    return fetch(url,{method:'POST',body:new FormData(form),credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}}).then(function(r){return r.text().then(function(text){var payload={},parsed=false;try{payload=text?JSON.parse(text):{};parsed=true;}catch(_e){}return {ok:r.ok&&parsed&&payload.ok!==false,j:payload,status:r.status,parsed:parsed,url:url};});});
  }
  if(deleteLayer){var form=deleteLayer.querySelector('form');if(form)form.addEventListener('submit',function(e){
    e.preventDefault();var submit=form.querySelector('button[type=submit]');if(submit)submit.disabled=true;
    homeworkDeleteRequest(formActionUrl(form),form).then(function(x){
      if(!x.ok){var msg=x.parsed&&(x.j.error||x.j.message);if(!msg)msg='Delete request failed ('+x.status+').';throw new Error(msg);}
      var filterForm=document.querySelector('form[data-v50211-live-form][data-v50211-region="teacher-homework"]');
      if(filterForm){var qs=new URLSearchParams(new FormData(filterForm));liveFetch(filterForm,formActionUrl(filterForm).split('?')[0]+'?'+qs.toString());}
      else{var card=document.querySelector('[data-homework-card-id="'+x.j.assignment_id+'"]');if(card)card.remove();}
      closeLayer(deleteLayer);toast(x.j.message||'Homework deleted.');
    }).catch(function(err){toast(err.message||'Could not delete homework.','error');}).finally(function(){if(submit)submit.disabled=false;});
  });}

  // Notifications: opening the center marks only the notices actually shown.
  // The explicit Read all action still clears every unread notification.
  document.querySelectorAll('[data-workspace-notice-layer]').forEach(function(layer){
    var busy=false,lastOpen=false;
    function updateUnreadUi(payload){
      layer.querySelectorAll('.is-unread,.mb50-notice-item.is-unread').forEach(function(n){n.classList.remove('is-unread');});
      layer.querySelectorAll('.mb50-unread-dot').forEach(function(dot){dot.remove();});
      var remaining=Math.max(0,Number(payload&&payload.unread)||0);
      document.querySelectorAll('[data-workspace-notice-badge]').forEach(function(b){b.textContent=String(remaining);b.hidden=remaining===0;});
    }
    function markRead(visibleOnly){
      if(busy)return;var url=layer.dataset.readUrl;if(!url)return;
      var body=null;
      if(visibleOnly){
        body=new URLSearchParams();
        layer.querySelectorAll('[data-notice-id]').forEach(function(item){if(item.dataset.noticeId)body.append('ids',item.dataset.noticeId);});
        if(!body.toString())return;
      }
      busy=true;layer.querySelectorAll('[data-v50211-read-all]').forEach(function(btn){btn.disabled=true;});
      fetch(url,{method:'POST',body:body,credentials:'same-origin',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}})
        .then(function(r){return r.text().then(function(text){var payload={};try{payload=text?JSON.parse(text):{};}catch(_e){throw new Error();}if(!r.ok||payload.ok===false)throw new Error();return payload;});})
        .then(updateUnreadUi).catch(function(){}).finally(function(){busy=false;layer.querySelectorAll('[data-v50211-read-all]').forEach(function(btn){btn.disabled=false;});});
    }
    function syncOpen(){var open=layer.classList.contains('is-open')||layer.getAttribute('aria-hidden')==='false';if(open&&!lastOpen)setTimeout(function(){markRead(true);},40);lastOpen=open;}
    new MutationObserver(syncOpen).observe(layer,{attributes:true,attributeFilter:['class','aria-hidden']});
    syncOpen();
    document.querySelectorAll('[data-workspace-command="notifications"]').forEach(function(btn){btn.addEventListener('click',function(){setTimeout(syncOpen,40);});});
    layer.querySelectorAll('[data-v50211-read-all]').forEach(function(btn){btn.addEventListener('click',function(e){e.preventDefault();markRead(false);});});
  });

  // View toggles inside live regions must keep working after AJAX replacement.
  document.addEventListener('click',function(e){
    var btn=e.target.closest('[data-sf29-view-toggle] button[data-view]'); if(!btn)return;
    var control=btn.closest('[data-sf29-view-toggle]'),target=document.querySelector(control.dataset.sf29Target||''); if(!target)return;
    var view=btn.dataset.view==='grid'?'grid':'list'; target.classList.toggle('is-grid',view==='grid');target.classList.toggle('is-list',view!=='grid');
    control.querySelectorAll('button[data-view]').forEach(function(x){x.classList.toggle('is-active',x===btn);});
    try{localStorage.setItem('makonbook.directory.'+(control.dataset.sf29ViewToggle||'default'),view);}catch(_e){}
  });
})();
