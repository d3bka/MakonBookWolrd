/* Minimal shared navigation language control for public secondary pages.
   Data-driven content remains authored by Django; don't translate student data. */
(function(){
  'use strict';
  const box=document.querySelector('[data-mb645-public-locale]');
  if(!box) return;
  const trigger=box.querySelector('[data-mb63-lang-trigger]');
  const current=box.querySelector('[data-mb63-lang-current]');
  const choices=Array.from(box.querySelectorAll('[data-mb63-lang-option]'));
  const langs=['en','ru','uz'];
  const dict={
    en:['Platform','Results','Parents','FAQ','Mock exams','Log in'],
    ru:['Платформа','Результаты','Родителям','Вопросы и ответы','Пробные экзамены','Войти'],
    uz:['Platforma','Natijalar','Ota-onalarga','Savol-javob','Sinov imtihonlari','Kirish']
  };
  let saved='';
  try {saved=localStorage.getItem('makonbook.public.language.v62')||'';}catch(_){ }
  const browser=((navigator.languages&&navigator.languages[0])||navigator.language||'en').toLowerCase().split('-')[0];
  let lang=langs.includes(saved)?saved:langs.includes(browser)?browser:'en';
  function apply(){
    document.documentElement.lang=lang;
    current.textContent=lang.toUpperCase();
    choices.forEach(choice=>{
      const selected=choice.dataset.mb63LangOption===lang;
      choice.setAttribute('aria-selected',String(selected));choice.tabIndex=selected?0:-1;
    });
    const names=dict[lang];
    document.querySelectorAll('.mb56-nav-links a').forEach((link,i)=>{if(i<4)link.textContent=names[i]});
    const mock=document.querySelector('.mb56-nav-wrap .mb56-btn-quiet');
    if(mock)mock.textContent=names[4];
    const login=document.querySelector('.mb56-nav-wrap .mb56-btn-login');
    if(login){
      let node=Array.from(login.childNodes).find(n=>n.nodeType===Node.TEXT_NODE);
      if(!node){node=document.createTextNode('');login.prepend(node)}
      node.nodeValue=names[5]+' ';
    }
    try {localStorage.setItem('makonbook.public.language.v62',lang)}catch(_){ }
  }
  function close(){box.classList.remove('is-open');trigger.setAttribute('aria-expanded','false')}
  trigger.addEventListener('click',event=>{event.stopPropagation();const open=!box.classList.contains('is-open');box.classList.toggle('is-open',open);trigger.setAttribute('aria-expanded',String(open))});
  choices.forEach(choice=>choice.addEventListener('click',()=>{
    const next=choice.dataset.mb63LangOption;
    close();if(next===lang||!langs.includes(next))return;
    const commit=()=>{lang=next;apply()};
    const fx=window.MakonBookLandingTransition;
    if(fx)fx.run(commit).catch(commit);else commit();
  }));
  document.addEventListener('pointerdown',event=>{if(!box.contains(event.target))close()});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
  apply();
})();
