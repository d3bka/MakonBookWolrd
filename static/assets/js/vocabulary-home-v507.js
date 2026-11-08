(()=>{
  const root=document.querySelector('[data-vocab-home]');
  if(!root)return;
  const dialog=root.querySelector('[data-vocab-deck-dialog]');
  const title=root.querySelector('[data-mode-title]');
  const kicker=root.querySelector('[data-mode-kicker]');
  const choices=[...root.querySelectorAll('[data-vocab-deck-choice]')];
  const config={
    memory:['Memory Layers','memoryUrl'],
    animated:['Animated Immersion','animatedUrl'],
    bounce:['Word Bounce','bounceUrl'],
    meaning:['Meaning Match','meaningUrl'],
  };
  function tap(el){
    if(!el)return;
    el.classList.remove('is-pressed');
    void el.offsetWidth;
    el.classList.add('is-pressed');
    window.setTimeout(()=>el.classList.remove('is-pressed'),190);
  }
  function openMode(mode,trigger){
    tap(trigger);
    const item=config[mode]||config.memory;
    if(title) title.textContent=`Choose a deck for ${item[0]}`;
    if(kicker) kicker.textContent=item[0];
    choices.forEach(link=>{link.href=link.dataset[item[1]]||'#';});
    if(dialog?.showModal){
      const card=dialog.querySelector('.vh506-dialog-card');
      card?.classList.remove('is-opening');
      dialog.showModal();
      if(card){void card.offsetWidth;card.classList.add('is-opening');window.setTimeout(()=>card.classList.remove('is-opening'),230);}
    }
  }
  root.querySelectorAll('[data-vocab-mode]').forEach(btn=>btn.addEventListener('click',()=>openMode(btn.dataset.vocabMode,btn)));
  root.querySelectorAll('[data-vocab-dialog-close]').forEach(btn=>btn.addEventListener('click',()=>{tap(btn);window.setTimeout(()=>dialog?.close(),70);}));
  dialog?.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
})();
