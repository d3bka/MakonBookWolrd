(function(){
  'use strict';
  function debounce(fn, wait){var t;return function(){var a=arguments,c=this;clearTimeout(t);t=setTimeout(function(){fn.apply(c,a)},wait);};}
  document.querySelectorAll('[data-v50210-live-form]').forEach(function(form){
    var submit=debounce(function(){if(form.requestSubmit){form.requestSubmit();}else{form.submit();}},280);
    form.querySelectorAll('input[type="search"],select').forEach(function(el){
      el.addEventListener(el.tagName==='SELECT'?'change':'input',submit);
    });
  });
  document.querySelectorAll('[data-v50210-submit-on-change]').forEach(function(el){el.addEventListener('change',function(){if(el.form)el.form.requestSubmit?el.form.requestSubmit():el.form.submit();});});
  document.querySelectorAll('[data-v50210-dropzone]').forEach(function(zone){
    var input=zone.querySelector('input[type=file]'), label=zone.querySelector('[data-v50210-file-name]')||zone.querySelector('strong'); if(!input)return;
    var defaultLabel=label?label.textContent:'Drop a file here or choose one';
    function setName(){if(label)label.textContent=input.files&&input.files[0]?input.files[0].name:defaultLabel;}
    ['dragenter','dragover'].forEach(function(e){zone.addEventListener(e,function(ev){ev.preventDefault();zone.classList.add('is-dragover');});});
    ['dragleave','drop'].forEach(function(e){zone.addEventListener(e,function(){zone.classList.remove('is-dragover');});});
    zone.addEventListener('drop',function(ev){ev.preventDefault();if(ev.dataTransfer&&ev.dataTransfer.files.length){input.files=ev.dataTransfer.files;setName();input.dispatchEvent(new Event('change',{bubbles:true}));}});
    input.addEventListener('change',setName);
  });
  document.querySelectorAll('[data-v50210-resource-form]').forEach(function(form){
    var type=form.querySelector('[name=resource_type]'); if(!type)return;
    function sync(){var v=type.value;form.querySelectorAll('[data-resource-field]').forEach(function(el){var allowed=(el.getAttribute('data-resource-field')||'').split(',');el.hidden=allowed.indexOf(v)<0;});syncScoreDate();}
    function syncScoreDate(){var vis=form.querySelector('[data-v50210-score-visibility]'),date=form.querySelector('[data-v50210-score-date]');if(date){date.hidden=type.value!=='test'||!vis||vis.value!=='scheduled';}}
    var vis=form.querySelector('[data-v50210-score-visibility]');if(vis)vis.addEventListener('change',syncScoreDate);
    type.addEventListener('change',sync);sync();
  });

  // Homework cards are replaced by live search/delete refreshes, so Edit must
  // use event delegation instead of binding only to the initial DOM snapshot.
  function openHomeworkEdit(btn){
    var modal=document.querySelector('[data-v50210-homework-edit-modal]'); if(!modal)return;
    function set(name,val){var el=modal.querySelector('[name="'+name+'"]');if(el)el.value=val==null?'':val;}
    ['assignment_id','classroom','assignment_type','title','instructions','due_at','test','required_test_mode','required_integrity_mode','vocabulary_unit','vocabulary_mode','vocabulary_quiz_mode','question_count','is_active'].forEach(function(k){set(k,btn.getAttribute('data-'+k.replace(/_/g,'-')));});
    var type=modal.querySelector('[name=assignment_type]'); if(type)type.dispatchEvent(new Event('change',{bubbles:true}));
    modal.setAttribute('aria-hidden','false'); modal.classList.add('is-open');
    var title=modal.querySelector('[name=title]'); if(title){window.setTimeout(function(){title.focus();title.select();},0);}
  }
  document.addEventListener('click',function(e){
    var btn=e.target.closest('[data-v50210-edit-homework]');
    if(!btn)return;
    e.preventDefault();
    openHomeworkEdit(btn);
  });
  document.querySelectorAll('[data-v50210-modal-close]').forEach(function(btn){btn.addEventListener('click',function(){var layer=btn.closest('.sf28-modal-layer');if(layer){layer.setAttribute('aria-hidden','true');layer.classList.remove('is-open');}});});
  document.querySelectorAll('[data-v50210-access-open]').forEach(function(btn){btn.addEventListener('click',function(){var id=btn.getAttribute('data-v50210-access-open');var modal=document.querySelector('[data-v50210-access-modal="'+id+'"]');if(modal){modal.setAttribute('aria-hidden','false');modal.classList.add('is-open');}});});

  document.querySelectorAll('[data-v50210-local-filter]').forEach(function(input){
    input.addEventListener('input',function(){var key=input.getAttribute('data-v50210-local-filter'),list=document.querySelector('[data-v50210-filter-list="'+key+'"]');if(!list)return;var q=(input.value||'').trim().toLowerCase();list.querySelectorAll('[data-v50210-filter-item]').forEach(function(row){row.hidden=q&&((row.getAttribute('data-v50210-filter-item')||'').indexOf(q)<0);});});
  });
  try{var openKey=new URLSearchParams(window.location.search).get('open');if(openKey){var openModal=document.querySelector('[data-v50210-access-modal="'+openKey+'"]');if(openModal){openModal.setAttribute('aria-hidden','false');openModal.classList.add('is-open');}}}catch(ignore){}
  document.querySelectorAll('[data-v50210-assessment-deck]').forEach(function(layer){
    var panels=Array.from(layer.querySelectorAll('[data-v50210-assess-panel]')), index=0, x0=null;
    function show(i){if(!panels.length)return;index=Math.max(0,Math.min(i,panels.length-1));panels.forEach(function(p,n){p.hidden=n!==index;});layer.querySelectorAll('[data-v50210-deck-index]').forEach(function(el){el.textContent=(index+1)+' / '+panels.length;});var prev=layer.querySelector('[data-v50210-deck-prev]'),next=layer.querySelector('[data-v50210-deck-next]');if(prev)prev.disabled=index===0;if(next)next.disabled=index===panels.length-1;}
    var prevBtn=layer.querySelector('[data-v50210-deck-prev]'),nextBtn=layer.querySelector('[data-v50210-deck-next]');if(prevBtn)prevBtn.addEventListener('click',function(){show(index-1);});if(nextBtn)nextBtn.addEventListener('click',function(){show(index+1);});
    panels.forEach(function(panel){panel.querySelectorAll('input,textarea').forEach(function(el){el.addEventListener('input',function(){var inc=panel.querySelector('[data-v50210-include]');if(inc)inc.value='1';});});});
    layer.addEventListener('touchstart',function(e){x0=e.touches&&e.touches[0]?e.touches[0].clientX:null;},{passive:true});layer.addEventListener('touchend',function(e){if(x0===null||!e.changedTouches[0])return;var d=e.changedTouches[0].clientX-x0;if(Math.abs(d)>55)show(index+(d<0?1:-1));x0=null;},{passive:true});
    document.querySelectorAll('[data-v50210-deck-open]').forEach(function(btn){btn.addEventListener('click',function(){var id=btn.getAttribute('data-v50210-deck-open'),targetIndex=panels.findIndex(function(panel){return panel.getAttribute('data-student-id')===id;});show(targetIndex>=0?targetIndex:0);layer.setAttribute('aria-hidden','false');layer.classList.add('is-open');});});
    show(0);
  });
  document.querySelectorAll('[data-v50210-single-submit]').forEach(function(form){form.addEventListener('submit',function(){var btn=form.querySelector('button[type=submit]');if(btn&&!btn.disabled){btn.disabled=true;btn.dataset.originalText=btn.innerHTML;btn.innerHTML='<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Saving…';}});});
})();
