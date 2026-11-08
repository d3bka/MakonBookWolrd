(function(){
  'use strict';
  function qs(s,r){return (r||document).querySelector(s)}
  function qsa(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  qsa('[data-sf29-view-toggle]').forEach(function(toggle){
    var target=qs(toggle.getAttribute('data-sf29-target'));
    if(!target)return;
    var key='makonbook.staff.view.'+(toggle.getAttribute('data-sf29-view-toggle')||'directory');
    function set(mode){target.classList.toggle('is-grid',mode==='grid');target.classList.toggle('is-list',mode!=='grid');qsa('button',toggle).forEach(function(b){b.classList.toggle('is-active',b.dataset.view===mode)});try{localStorage.setItem(key,mode)}catch(e){}}
    qsa('button',toggle).forEach(function(b){b.addEventListener('click',function(){set(b.dataset.view||'list')})});
    var saved='list';try{saved=localStorage.getItem(key)||'list'}catch(e){}set(saved);
  });
  var accessModal=qs('[data-sf29-access-modal]');
  qsa('[data-sf29-access-open]').forEach(function(btn){btn.addEventListener('click',function(){if(!accessModal)return;qs('[data-sf29-access-title]',accessModal).textContent=btn.dataset.title||'Access settings';qs('[data-sf29-access-copy]',accessModal).textContent=btn.dataset.copy||'';qs('[data-sf29-access-go]',accessModal).href=btn.dataset.url||'#';accessModal.classList.add('is-open');accessModal.setAttribute('aria-hidden','false')})});
  qsa('[data-sf29-access-close]').forEach(function(btn){btn.addEventListener('click',function(){if(accessModal){accessModal.classList.remove('is-open');accessModal.setAttribute('aria-hidden','true')}})});
  qsa('[data-sf29-assess-open]').forEach(function(btn){btn.addEventListener('click',function(){var modal=qs('[data-sf29-assess-modal="'+btn.dataset.student+'"]');if(modal){modal.classList.add('is-open');modal.setAttribute('aria-hidden','false')}})});
  qsa('[data-sf29-assess-close]').forEach(function(btn){btn.addEventListener('click',function(){var modal=btn.closest('[data-sf29-assess-modal]');if(modal){modal.classList.remove('is-open');modal.setAttribute('aria-hidden','true')}})});
  function moveAssessment(modal,dir){if(!modal)return;var id=dir==='next'?modal.dataset.next:modal.dataset.prev;if(!id)return;modal.classList.remove('is-open');modal.setAttribute('aria-hidden','true');var next=qs('[data-sf29-assess-modal="'+id+'"]');if(next){next.classList.add('is-open');next.setAttribute('aria-hidden','false')}}
  qsa('[data-sf29-assess-next]').forEach(function(b){b.addEventListener('click',function(){moveAssessment(b.closest('[data-sf29-assess-modal]'),'next')})});
  qsa('[data-sf29-assess-prev]').forEach(function(b){b.addEventListener('click',function(){moveAssessment(b.closest('[data-sf29-assess-modal]'),'prev')})});
  qsa('[data-sf29-assess-modal]').forEach(function(modal){var startX=null;modal.addEventListener('touchstart',function(e){startX=e.touches&&e.touches[0]?e.touches[0].clientX:null},{passive:true});modal.addEventListener('touchend',function(e){if(startX===null)return;var end=e.changedTouches&&e.changedTouches[0]?e.changedTouches[0].clientX:startX;var delta=end-startX;if(Math.abs(delta)>70)moveAssessment(modal,delta<0?'next':'prev');startX=null},{passive:true})});
  if(new URLSearchParams(window.location.search).get('create')==='1'){var opener=qs('[data-sf28-modal-open="homework"]');if(opener)setTimeout(function(){opener.click()},80);}
  qsa('[data-sf29-resource-type]').forEach(function(select){function sync(){var form=select.closest('form');if(!form)return;var file=qs('[data-sf29-resource-file]',form),url=qs('[data-sf29-resource-url]',form);var isLink=select.value==='link';if(file){file.hidden=isLink;var input=qs('input',file);if(input)input.disabled=isLink}if(url){url.hidden=!isLink;var input2=qs('input',url);if(input2)input2.disabled=!isLink}}select.addEventListener('change',sync);sync()});
})();
