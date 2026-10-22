(function(){
  'use strict';
  const root=document.querySelector('[data-v554-homework-root]');
  if(!root)return;
  const tabs=[...root.querySelectorAll('[data-v554-homework-tab]')];
  const panels=[...root.querySelectorAll('[data-v554-homework-panel]')];
  const viewInput=root.querySelector('[data-v554-view-input]');
  const heroCount=root.querySelector('[data-v554-hero-count]');
  const heroLabel=root.querySelector('[data-v554-hero-label]');
  function activate(name,persist){
    if(!panels.some(p=>p.dataset.v554HomeworkPanel===name))return;
    tabs.forEach(t=>{const on=t.dataset.v554HomeworkTab===name;t.classList.toggle('is-active',on);t.setAttribute('aria-selected',String(on));});
    panels.forEach(p=>{const on=p.dataset.v554HomeworkPanel===name;p.hidden=!on;p.classList.toggle('is-active',on);});
    if(viewInput)viewInput.value=name;
    const active=tabs.find(t=>t.dataset.v554HomeworkTab===name);const count=active?active.querySelector('strong')?.textContent.trim():'0';
    if(heroCount)heroCount.textContent=count||'0';if(heroLabel)heroLabel.textContent=name==='completed'?'submitted':'to do';
    if(persist){try{sessionStorage.setItem('makonbook:homework-tab',name)}catch(_e){};try{const u=new URL(location.href);u.searchParams.set('view',name);history.replaceState(null,'',u)}catch(_e){}}
  }
  tabs.forEach(t=>t.addEventListener('click',()=>activate(t.dataset.v554HomeworkTab,true)));
  let initial=root.dataset.initialView||'todo';try{const saved=sessionStorage.getItem('makonbook:homework-tab');if(saved&&panels.some(p=>p.dataset.v554HomeworkPanel===saved))initial=saved}catch(_e){}
  activate(initial,false);
  root.addEventListener('click',e=>{const link=e.target.closest('[data-v554-assignment-link]');if(!link||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;if(link.classList.contains('is-deadline-closed'))return;link.classList.add('is-opening');link.setAttribute('aria-busy','true');const text=link.querySelector('[data-v554-cta-text]');if(text)text.textContent=link.dataset.assignmentType==='sat_test'?'Preparing test…':'Opening assignment…';const icon=link.querySelector('.v554-cta-play');if(icon){icon.className='v554-cta-play bi bi-arrow-repeat';}});
})();